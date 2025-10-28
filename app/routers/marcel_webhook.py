"""
MarcelGPT Webhook - HeyGen Callback Handler
"""
from fastapi import APIRouter, Request, HTTPException, Query
from datetime import datetime
import hmac
import hashlib

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response

router = APIRouter()


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
            await handle_processing(job_id, event_data)

        elif event_type == "video.success":
            await handle_success(job_id, event_data)

        elif event_type == "video.failed":
            await handle_failure(job_id, event_data)

        else:
            # Unknown event type, log but don't fail
            print(f"Unknown webhook event type: {event_type}")

        return {"status": "ok", "message": "Webhook processed"}

    except Exception as e:
        print(f"Webhook processing error: {str(e)}")
        raise HTTPException(500, f"Webhook processing failed: {str(e)}")


async def handle_processing(job_id: int, event_data: dict):
    """Handle video.processing event"""
    supabase.table("video_jobs") \
        .update({
            "status": "processing",
            "processing_at": datetime.now().isoformat()
        }) \
        .eq("id", job_id) \
        .execute()


async def handle_success(job_id: int, event_data: dict):
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
    video_url = event_data.get("video_url")
    duration = event_data.get("duration")

    # Update job status
    supabase.table("video_jobs") \
        .update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "actual_duration": duration
        }) \
        .eq("id", job_id) \
        .execute()

    # Create video artifact
    artifact_data = {
        "job_id": job_id,
        "heygen_url": video_url,
        "storage_key": f"videos/{job_id}/video.mp4",  # Will be uploaded to S3
        "duration": duration,
        "thumbnail_url": event_data.get("thumbnail_url"),
        "meta": {
            "gif_url": event_data.get("gif_url"),
            "caption_url": event_data.get("caption_url")
        }
    }

    supabase.table("video_artifacts") \
        .insert(artifact_data) \
        .execute()

    # TODO: Download video from HeyGen and upload to permanent storage (S3/Spaces)
    # HeyGen URLs expire after some time, so we need to copy them
    # This should be done asynchronously via a background task


async def handle_failure(job_id: int, event_data: dict):
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
