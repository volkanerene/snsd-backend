"""
Marcel GPT Library - Premade Videos and Worker Assignments
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user, require_permission

router = APIRouter()


class AssignVideosRequest(BaseModel):
    video_ids: List[str]
    worker_ids: List[str]
    notes: Optional[str] = None


# =========================================================================
# Premade Videos Endpoints
# =========================================================================

@router.get("/premade-videos")
async def list_premade_videos(
    user=Depends(get_current_user),
    category: Optional[str] = None,
    is_active: bool = True
):
    """List all premade training videos for the tenant"""
    require_permission(user, "marcel_gpt.view_library")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    query = supabase.table("marcel_gpt_premade_videos") \
        .select("*") \
        .eq("tenant_id", tenant_id) \
        .eq("is_active", is_active)

    if category:
        query = query.eq("category", category)

    query = query.order("created_at", desc=True)

    res = query.execute()
    return {
        "videos": ensure_response(res),
        "count": len(res.data) if res.data else 0
    }


@router.get("/premade-videos/{video_id}")
async def get_premade_video(
    video_id: str,
    user=Depends(get_current_user)
):
    """Get a specific premade video"""
    require_permission(user, "marcel_gpt.view_library")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    res = supabase.table("marcel_gpt_premade_videos") \
        .select("*") \
        .eq("id", video_id) \
        .eq("tenant_id", tenant_id) \
        .single() \
        .execute()

    if not res.data:
        raise HTTPException(404, "Video not found")

    return res.data


# =========================================================================
# Video Assignment Endpoints
# =========================================================================

@router.post("/assign-videos")
async def assign_videos_to_workers(
    payload: AssignVideosRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """
    Assign premade videos to workers
    Sends email notifications to assigned workers
    """
    require_permission(user, "marcel_gpt.assign_videos")

    tenant_id = user.get("tenant_id")
    user_id = user.get("id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Validate videos exist
    videos_res = supabase.table("marcel_gpt_premade_videos") \
        .select("id, title") \
        .eq("tenant_id", tenant_id) \
        .in_("id", payload.video_ids) \
        .execute()

    if not videos_res.data or len(videos_res.data) != len(payload.video_ids):
        raise HTTPException(400, "One or more videos not found")

    # Validate workers exist and get their emails
    workers_res = supabase.table("profiles") \
        .select("id, full_name, email, role_id") \
        .eq("tenant_id", tenant_id) \
        .in_("id", payload.worker_ids) \
        .execute()

    if not workers_res.data or len(workers_res.data) != len(payload.worker_ids):
        raise HTTPException(400, "One or more workers not found")

    # Only allow assigning to workers (role_id >= 6 or specific worker roles)
    # Adjust role_id check based on your role structure
    # For now, allow any role

    # Create assignments
    assignments = []
    for video_id in payload.video_ids:
        for worker_id in payload.worker_ids:
            assignment = {
                "video_id": video_id,
                "tenant_id": tenant_id,
                "assigned_to": worker_id,
                "assigned_by": user_id,
                "status": "pending",
                "notes": payload.notes,
                "email_sent_at": datetime.now().isoformat()
            }
            assignments.append(assignment)

    # Insert assignments (upsert to handle duplicates)
    try:
        res = supabase.table("marcel_gpt_video_assignments").upsert(
            assignments,
            on_conflict="video_id,assigned_to"
        ).execute()
    except Exception as e:
        raise HTTPException(500, f"Failed to create assignments: {str(e)}")

    # Send emails in background
    background_tasks.add_task(
        send_assignment_emails,
        workers_res.data,
        videos_res.data,
        user.get("full_name", "Administrator")
    )

    return {
        "success": True,
        "assignments_created": len(assignments),
        "workers_notified": len(payload.worker_ids)
    }


@router.get("/my-assignments")
async def get_my_video_assignments(
    user=Depends(get_current_user),
    status: Optional[str] = None
):
    """Get video assignments for the current user (worker view)"""

    user_id = user.get("id")

    query = supabase.table("marcel_gpt_video_assignments") \
        .select("""
            *,
            video:video_id (
                id, title, description, video_url, thumbnail_url,
                duration_seconds, category
            ),
            assigned_by_user:assigned_by (
                id, full_name, email
            )
        """) \
        .eq("assigned_to", user_id)

    if status:
        query = query.eq("status", status)

    query = query.order("created_at", desc=True)

    res = query.execute()
    return {
        "assignments": ensure_response(res),
        "count": len(res.data) if res.data else 0
    }


@router.patch("/assignments/{assignment_id}/mark-viewed")
async def mark_assignment_viewed(
    assignment_id: str,
    user=Depends(get_current_user)
):
    """Mark a video assignment as viewed"""

    user_id = user.get("id")

    # Update assignment
    res = supabase.table("marcel_gpt_video_assignments") \
        .update({
            "status": "viewed",
            "viewed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }) \
        .eq("id", assignment_id) \
        .eq("assigned_to", user_id) \
        .execute()

    if not res.data:
        raise HTTPException(404, "Assignment not found")

    return {"success": True}


@router.patch("/assignments/{assignment_id}/mark-completed")
async def mark_assignment_completed(
    assignment_id: str,
    user=Depends(get_current_user)
):
    """Mark a video assignment as completed"""

    user_id = user.get("id")

    res = supabase.table("marcel_gpt_video_assignments") \
        .update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }) \
        .eq("id", assignment_id) \
        .eq("assigned_to", user_id) \
        .execute()

    if not res.data:
        raise HTTPException(404, "Assignment not found")

    return {"success": True}


@router.get("/assignment-stats")
async def get_assignment_stats(
    user=Depends(get_current_user)
):
    """Get assignment statistics for admins"""
    require_permission(user, "marcel_gpt.view_library")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Get all assignments for tenant
    res = supabase.table("marcel_gpt_video_assignments") \
        .select("status") \
        .eq("tenant_id", tenant_id) \
        .execute()

    assignments = res.data or []

    stats = {
        "total": len(assignments),
        "pending": len([a for a in assignments if a['status'] == 'pending']),
        "viewed": len([a for a in assignments if a['status'] == 'viewed']),
        "completed": len([a for a in assignments if a['status'] == 'completed'])
    }

    return stats


# =========================================================================
# Helper Functions
# =========================================================================

async def send_assignment_emails(workers: List[dict], videos: List[dict], assigned_by_name: str):
    """
    Send email notifications to workers about video assignments
    This is a placeholder - implement with your email service
    """
    # TODO: Integrate with actual email service (SendGrid, AWS SES, etc.)

    for worker in workers:
        email = worker.get("email")
        if not email:
            continue

        # Prepare email content
        video_titles = ", ".join([v['title'] for v in videos])

        email_subject = f"Yeni Eğitim Videoları Atandı - {len(videos)} Video"
        email_body = f"""
Merhaba {worker.get('full_name', '')},

{assigned_by_name} tarafından size {len(videos)} adet eğitim videosu atandı:

{video_titles}

Videoları görüntülemek için lütfen platformda oturum açın:
https://app.snsdconsultant.com/dashboard/marcel-gpt/my-videos

İyi çalışmalar,
SnSD Consultants
"""

        # Log the email (for development)
        print(f"[Email] To: {email}")
        print(f"[Email] Subject: {email_subject}")
        print(f"[Email] Body: {email_body}")

        # TODO: Actually send the email
        # await email_service.send_email(to=email, subject=email_subject, body=email_body)
