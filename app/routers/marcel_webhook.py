"""
MarcelGPT Webhook - HeyGen Callback Handler
"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query, Depends
from datetime import datetime
import hmac
import hashlib

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user, require_permission
from app.services.heygen_service import get_heygen_service
from app.services.email_service import EmailService, render_html_from_text

router = APIRouter()
logger = logging.getLogger(__name__)


async def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """
    Verify HeyGen webhook signature

    Args:
        payload: Raw request body
        signature: X-Heygen-Signature header
        secret: Webhook secret from tenant config

    Returns:
        True if valid, False otherwise
    """
    if not secret:
        return True  # Skip verification if no secret configured

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@router.post("/webhook")
async def heygen_webhook(
    request: Request,
    job_id: int = Query(..., description="Our internal job ID"),
):
    """
    Handle HeyGen webhook callbacks

    HeyGen sends events:
    - video.processing: Video generation started
    - video.success: Video generation completed
    - video.failed: Video generation failed

    Event payload:
    {
        "event_type": "video.success",
        "event_data": {
            "video_id": "abc123",
            "video_url": "https://...",
            "duration": 30,
            "thumbnail_url": "https://..."
        },
        "timestamp": "2025-10-27T12:00:00Z"
    }
    """
    # Get raw body for signature verification
    body = await request.body()

    # Parse JSON
    try:
        event = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")

    # Get job from database
    job_res = supabase.table("video_jobs") \
        .select("*, tenants!inner(heygen_webhook_secret)") \
        .eq("id", job_id) \
        .limit(1) \
        .execute()

    job_data = ensure_response(job_res)
    if not job_data:
        raise HTTPException(404, "Job not found")

    job = job_data[0]

    # Verify signature
    signature = request.headers.get("X-Heygen-Signature", "")
    webhook_secret = job.get("tenants", {}).get("heygen_webhook_secret")

    if webhook_secret and not verify_webhook_signature(body, signature, webhook_secret):
        raise HTTPException(401, "Invalid webhook signature")

    # Extract event data
    event_type = event.get("event_type")
    event_data = event.get("event_data", {})
    video_id = event_data.get("video_id")

    # Verify video_id matches
    if video_id and video_id != job.get("heygen_job_id"):
        raise HTTPException(400, "Video ID mismatch")

    # Handle different event types
    try:
        if event_type == "video.processing":
            await handle_processing(job)

        elif event_type == "video.success":
            await handle_success(job, event_data)

        elif event_type == "video.failed":
            await handle_failure(job, event_data)

        else:
            # Unknown event type, log but don't fail
            print(f"Unknown webhook event type: {event_type}")

        return {"status": "ok", "message": "Webhook processed"}

    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        raise HTTPException(500, f"Webhook processing failed: {str(e)}")


async def handle_processing(job: dict):
    """Handle video.processing event"""
    supabase.table("video_jobs") \
        .update({
            "status": "processing",
            "processing_at": datetime.now().isoformat()
        }) \
        .eq("id", job["id"]) \
        .execute()


async def handle_success(job: dict, event_data: dict):
    """
    Handle video.success event

    Event data:
    {
        "video_id": "abc123",
        "video_url": "https://resource.heygen.com/...",
        "duration": 30.5,
        "thumbnail_url": "https://...",
        "gif_url": "https://..."
    }
    """
    job_id = job["id"]
    tenant_id = job.get("tenant_id")
    heygen_job_id = job.get("heygen_job_id")

    video_url = event_data.get("video_url")
    duration = event_data.get("duration")
    thumbnail_url = event_data.get("thumbnail_url")
    gif_url = event_data.get("gif_url")
    caption_url = event_data.get("caption_url")

    if (not video_url or not thumbnail_url or not duration) and tenant_id:
        heygen_service = get_heygen_service(tenant_id)
        if heygen_service and heygen_job_id:
            try:
                status_payload = await heygen_service.get_video_status(heygen_job_id)
                data = status_payload.get("data", {})
                video_url = video_url or data.get("video_url")
                thumbnail_url = thumbnail_url or data.get("thumbnail_url") or data.get("cover_url")
                duration = duration or data.get("duration")
                caption_url = caption_url or data.get("subtitle_url")
            except Exception as fetch_error:
                logger.warning(
                    "[MarcelWebhook] Unable to fetch video metadata for job %s: %s",
                    job_id,
                    fetch_error
                )

    # Update job status
    supabase.table("video_jobs") \
        .update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "actual_duration": duration
        }) \
        .eq("id", job_id) \
        .execute()

    if video_url:
        # Remove previous artifacts for this job to avoid duplicates
        supabase.table("video_artifacts") \
            .delete() \
            .eq("job_id", job_id) \
            .execute()

        storage_key = video_url or f"videos/{job_id}/video.mp4"
        artifact_data = {
            "job_id": job_id,
            "heygen_url": video_url,
            "storage_key": storage_key,
            "signed_url": video_url,
            "duration": duration,
            "thumbnail_url": thumbnail_url,
            "meta": {
                "gif_url": gif_url,
                "caption_url": caption_url
            }
        }

        supabase.table("video_artifacts") \
            .insert(artifact_data) \
            .execute()

    await _notify_creator_video_ready(job, video_url)

    # TODO: Download video from HeyGen and upload to permanent storage (S3/Spaces)
    # HeyGen URLs expire after some time, so we need to copy them
    # This should be done asynchronously via a background task


async def handle_failure(job: dict, event_data: dict):
    """
    Handle video.failed event

    Event data:
    {
        "video_id": "abc123",
        "error": "Error message from HeyGen"
    }
    """
    error_message = event_data.get("error", "Video generation failed")

    # Get current job to check retry count
    job_id = job["id"]

    job_res = supabase.table("video_jobs") \
        .select("retry_count, max_retries") \
        .eq("id", job_id) \
        .limit(1) \
        .execute()

    job_data = ensure_response(job_res)
    if not job_data:
        return

    job = job_data[0]
    retry_count = job.get("retry_count", 0)
    max_retries = job.get("max_retries", 3)

    # Update job
    update_data = {
        "error_message": error_message,
        "retry_count": retry_count + 1,
    }

    # If we've exhausted retries, mark as failed
    if retry_count >= max_retries:
        update_data["status"] = "failed"
        update_data["failed_at"] = datetime.now().isoformat()
    else:
        # TODO: Implement retry logic
        # For now, just mark as failed
        update_data["status"] = "failed"
        update_data["failed_at"] = datetime.now().isoformat()

    supabase.table("video_jobs") \
        .update(update_data) \
        .eq("id", job_id) \
        .execute()


async def _notify_creator_video_ready(job: dict, video_url: Optional[str]):
    """Send email notification to the job creator when a video completes."""
    user_id = job.get("user_id")
    if not user_id:
        return

    try:
        profile_res = (
            supabase.table("profiles")
            .select("email, full_name")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        profile_data = ensure_response(profile_res)
        if not profile_data:
            return

        profile = profile_data[0]
        recipient = profile.get("email")
        if not recipient:
            return

        full_name = profile.get("full_name") or "there"
        title = job.get("title") or "Your MarcelGPT Training"
        watch_link = "https://www.snsdconsultant.com/dashboard/marcel-gpt/library"
        subject = "Your MarcelGPT video is ready"

        body_lines = [
            f"Hi {full_name},",
            "",
            f"Your video \"{title}\" has finished processing and is ready to review.",
            "",
            f"Library: {watch_link}",
        ]
        if video_url:
            body_lines.append(f"Direct link: {video_url}")
        body_lines.extend(
            [
                "",
                "You can always revisit your trainings from the Training Builder Library.",
                "",
                "– SnSD MarcelGPT",
            ]
        )

        text_body = "\n".join(body_lines)
        html_body = render_html_from_text(text_body)

        success, err = EmailService.send_email(
            to_email=recipient,
            subject=subject,
            text_body=text_body,
            html_body=html_body
        )
        if not success:
            logger.warning(
                "[MarcelWebhook] Failed to send completion email to %s: %s",
                recipient,
                err
            )
    except Exception as notify_error:
        logger.warning(
            "[MarcelWebhook] Error notifying creator for job %s: %s",
            job.get("id"),
            notify_error
        )


@router.post("/jobs/{job_id}/sync-status")
async def sync_job_status(
    job_id: int,
    user=Depends(get_current_user),
):
    """
    Manually sync job status from HeyGen API

    This endpoint queries HeyGen for the current status of a video job
    and updates the database accordingly. Use this if the webhook isn't
    being called by HeyGen.
    """
    require_permission(user, "modules.access_marcel_gpt")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Get job
    job_res = supabase.table("video_jobs") \
        .select("*") \
        .eq("id", job_id) \
        .eq("tenant_id", tenant_id) \
        .limit(1) \
        .execute()

    job_data = ensure_response(job_res)
    if not job_data:
        raise HTTPException(404, "Job not found")

    job = job_data[0]
    heygen_job_id = job.get("heygen_job_id")

    if not heygen_job_id:
        raise HTTPException(400, "Job not yet submitted to HeyGen")

    # Get HeyGen service
    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured")

    try:
        # Get status from HeyGen
        status_response = await heygen.get_video_status(heygen_job_id)

        # Extract video info
        video_id = status_response.get("data", {}).get("video_id")
        heygen_status = status_response.get("data", {}).get("status", "unknown")
        video_url = status_response.get("data", {}).get("video_url")
        duration = status_response.get("data", {}).get("duration")
        thumbnail_url = status_response.get("data", {}).get("thumbnail_url")

        # Map HeyGen status to our status
        status_map = {
            "processing": "processing",
            "completed": "completed",
            "failed": "failed"
        }
        our_status = status_map.get(heygen_status, heygen_status)

        # Update job status
        update_data = {"status": our_status}

        if our_status == "completed":
            update_data["completed_at"] = datetime.now().isoformat()
            update_data["actual_duration"] = duration

            # Check if artifacts already exist
            artifact_res = supabase.table("video_artifacts") \
                .select("id") \
                .eq("job_id", job_id) \
                .limit(1) \
                .execute()

            artifacts = ensure_response(artifact_res)

            # Create artifact if it doesn't exist
            if not artifacts and video_url:
                artifact_data = {
                    "job_id": job_id,
                    "heygen_url": video_url,
                    "storage_key": f"videos/{job_id}/video.mp4",
                    "duration": duration,
                    "thumbnail_url": thumbnail_url,
                    "meta": {}
                }
                supabase.table("video_artifacts") \
                    .insert(artifact_data) \
                    .execute()

        elif our_status == "failed":
            update_data["failed_at"] = datetime.now().isoformat()
            error_msg = status_response.get("data", {}).get("error", "Video generation failed")
            update_data["error_message"] = error_msg

        supabase.table("video_jobs") \
            .update(update_data) \
            .eq("id", job_id) \
            .execute()

        return {
            "status": "synced",
            "job_id": job_id,
            "heygen_status": heygen_status,
            "our_status": our_status,
            "updated": update_data
        }

    except Exception as e:
        import sys
        print(f"[Webhook] Error syncing status for job {job_id}: {str(e)}", file=sys.stderr, flush=True)
        raise HTTPException(500, f"Failed to sync status: {str(e)}")
