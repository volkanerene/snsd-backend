"""
Marcel GPT Library - Premade Videos and Worker Assignments
"""
from datetime import datetime
from typing import List, Optional
import xml.etree.ElementTree as ET
import re
import json

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from app.config import settings
from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user, require_permission

router = APIRouter()

CHANNEL_ID_PATTERN = re.compile(r'["\']channelId["\']\s*:\s*["\'](UC[0-9A-Za-z_\-]{20,})["\']')
BROWSE_ID_PATTERN = re.compile(r'["\']browseId["\']\s*:\s*["\'](UC[0-9A-Za-z_\-]{20,})["\']')
EXTERNAL_ID_PATTERN = re.compile(r'["\']externalChannelId["\']\s*:\s*["\'](UC[0-9A-Za-z_\-]{20,})["\']')
_CHANNEL_HANDLE_CACHE: dict[str, str] = {}


class AssignVideosRequest(BaseModel):
    video_ids: List[str]
    worker_ids: List[str]
    notes: Optional[str] = None


class ImportPremadeVideoRequest(BaseModel):
    title: str
    video_url: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    category: Optional[str] = "External"
    tags: Optional[List[str]] = None


class YoutubeVideo(BaseModel):
    video_id: str
    title: str
    url: str
    published_at: str
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None


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


@router.post("/premade-videos/import")
async def import_premade_video(
    payload: ImportPremadeVideoRequest,
    user=Depends(get_current_user),
):
    """Upsert an external video into the tenant's premade library"""
    require_permission(user, "marcel_gpt.view_library")

    tenant_id = user.get("tenant_id")
    created_by = user.get("id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    existing = (
        supabase.table("marcel_gpt_premade_videos")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("video_url", payload.video_url)
        .limit(1)
        .execute()
    )

    video_row = None
    now_payload = {
        "title": payload.title,
        "description": payload.description,
        "video_url": payload.video_url,
        "thumbnail_url": payload.thumbnail_url,
        "duration_seconds": payload.duration_seconds,
        "category": payload.category or "External",
        "tags": payload.tags,
        "updated_at": datetime.utcnow().isoformat()
    }

    if existing.data:
        video_id = existing.data[0]["id"]
        res = (
            supabase.table("marcel_gpt_premade_videos")
            .update(now_payload)
            .eq("id", video_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        data = ensure_response(res)
        video_row = data[0] if isinstance(data, list) and data else data
    else:
        insert_payload = {
            **now_payload,
            "tenant_id": tenant_id,
            "created_by": created_by
        }
        res = supabase.table("marcel_gpt_premade_videos").insert(insert_payload).execute()
        data = ensure_response(res)
        video_row = data[0] if isinstance(data, list) and data else data

    return {"video": video_row}

async def _resolve_channel_id_from_handle(handle: str) -> Optional[str]:
    """
    Attempt to resolve a YouTube channel ID from a handle (e.g., @SnSDConsultants)
    so that feeds continue to work even if the legacy ?user= endpoint is unavailable.
    """
    if not handle:
        return None

    normalized = handle.lstrip("@").strip()
    if not normalized:
        return None

    cached = _CHANNEL_HANDLE_CACHE.get(normalized.lower())
    if cached:
        return cached

    url = f"https://www.youtube.com/@{normalized}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SnSDBot/1.0; +https://snsdconsultant.com)"
    }

    try:
        async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception as exc:
        print(f"[YouTube] Failed to resolve handle {handle}: {exc}")
        return None

    html = response.text
    match = (
        CHANNEL_ID_PATTERN.search(html)
        or BROWSE_ID_PATTERN.search(html)
        or EXTERNAL_ID_PATTERN.search(html)
    )

    if not match:
        marker = "ytInitialData"
        if marker in html:
            start_idx = html.find(marker)
            json_start = html.find("{", start_idx)
            json_end = html.find(";</script>", json_start)
            if json_start != -1 and json_end != -1:
                blob = html[json_start:json_end]
                try:
                    data = json.loads(blob)
                    data_str = json.dumps(data)
                    match = (
                        CHANNEL_ID_PATTERN.search(data_str)
                        or BROWSE_ID_PATTERN.search(data_str)
                        or EXTERNAL_ID_PATTERN.search(data_str)
                    )
                except Exception as parse_exc:
                    print(f"[YouTube] Failed to parse ytInitialData JSON: {parse_exc}")

    if match:
        channel_id = match.group(1)
        _CHANNEL_HANDLE_CACHE[normalized.lower()] = channel_id
        return channel_id

    print(f"[YouTube] Could not extract channelId from handle page: {handle}")
    return None


@router.get("/youtube")
async def list_youtube_videos(
    user=Depends(get_current_user),
    limit: int = Query(6, ge=1, le=20)
):
    """Fetch latest YouTube videos for SnSD Consultants channel"""
    require_permission(user, "marcel_gpt.view_library")

    channel_id = settings.YOUTUBE_CHANNEL_ID
    channel_handle = settings.YOUTUBE_CHANNEL_HANDLE or "SnSDConsultants"

    if not channel_id and not channel_handle:
        raise HTTPException(400, "YouTube channel not configured")

    resolved_channel_id = channel_id
    if not resolved_channel_id and channel_handle:
        resolved_channel_id = await _resolve_channel_id_from_handle(channel_handle)

    handle_for_feed = (channel_handle or "").lstrip("@") or "SnSDConsultants"

    if resolved_channel_id:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={resolved_channel_id}"
    else:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?user={handle_for_feed}"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SnSDBot/1.0; +https://snsdconsultant.com)",
            "Accept": "application/atom+xml"
        }
        async with httpx.AsyncClient(timeout=10, headers=headers, follow_redirects=True) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
    except Exception as e:
        print(f"[YouTube] Failed to fetch feed from {feed_url}: {e}")
        # Return graceful fallback so UI can still render
        return {"videos": [], "warning": f"Failed to fetch YouTube feed: {str(e)}"}

    try:
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
            "media": "http://search.yahoo.com/mrss/"
        }
        root = ET.fromstring(response.text)
        print(f"[YouTube] Feed root tag: {root.tag}, attribs: {root.attrib}")

        videos: List[YoutubeVideo] = []

        # Try multiple entry search patterns
        entries = root.findall("atom:entry", ns)
        print(f"[YouTube] Found {len(entries)} entries using atom:entry")

        # If no entries found with namespace, try without namespace prefix
        if len(entries) == 0:
            entries = root.findall("{http://www.w3.org/2005/Atom}entry")
            print(f"[YouTube] Found {len(entries)} entries using full namespace URI")

        # If still no entries, try direct children
        if len(entries) == 0:
            entries = root.findall("entry")
            print(f"[YouTube] Found {len(entries)} entries without namespace")

        for entry in entries[:limit]:
            video_id_elem = entry.find("yt:videoId", ns)
            if video_id_elem is None:
                video_id_elem = entry.find("{http://www.youtube.com/xml/schemas/2015}videoId")

            title_elem = entry.find("atom:title", ns)
            if title_elem is None:
                title_elem = entry.find("{http://www.w3.org/2005/Atom}title")

            published_elem = entry.find("atom:published", ns)
            if published_elem is None:
                published_elem = entry.find("{http://www.w3.org/2005/Atom}published")

            link_elem = entry.find("atom:link", ns)
            if link_elem is None:
                link_elem = entry.find("{http://www.w3.org/2005/Atom}link")

            media_group = entry.find("media:group", ns)
            if media_group is None:
                media_group = entry.find("{http://search.yahoo.com/mrss/}group")

            description_elem = media_group.find("media:description", ns) if media_group is not None else None
            if description_elem is None and media_group is not None:
                description_elem = media_group.find("{http://search.yahoo.com/mrss/}description")

            if not video_id_elem or not title_elem:
                print(f"[YouTube] Skipping entry: missing video_id_elem={video_id_elem is not None} or title_elem={title_elem is not None}")
                continue

            video_id_text = video_id_elem.text

            # Extract thumbnail URL with fallback logic
            thumbnail_url = None
            if media_group is not None:
                # Try media:thumbnail from media:group
                thumbnail_elem = media_group.find("media:thumbnail", ns)
                if thumbnail_elem is None:
                    thumbnail_elem = media_group.find("{http://search.yahoo.com/mrss/}thumbnail")

                if thumbnail_elem is not None:
                    thumbnail_url = thumbnail_elem.get("url")
                    print(f"[YouTube] Found thumbnail from media:thumbnail: {thumbnail_url[:50]}...")

            # Fallback: construct standard YouTube thumbnail URLs
            if not thumbnail_url and video_id_text:
                # Try maxresdefault first (highest quality), then fall back to hqdefault
                thumbnail_url = f"https://i.ytimg.com/vi/{video_id_text}/maxresdefault.jpg"
                print(f"[YouTube] Using constructed thumbnail: {thumbnail_url}")

            url = link_elem.get("href") if link_elem is not None else f"https://www.youtube.com/watch?v={video_id_text}"

            videos.append(
                YoutubeVideo(
                    video_id=video_id_text,
                    title=title_elem.text,
                    url=url,
                    published_at=published_elem.text if published_elem is not None else "",
                    thumbnail_url=thumbnail_url,
                    description=description_elem.text if description_elem is not None else None
                )
            )

        print(f"[YouTube] Successfully parsed {len(videos)} videos from feed")
        return {"videos": [video.dict() for video in videos]}
    except Exception as e:
        print(f"[YouTube] Error parsing feed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Failed to parse YouTube feed: {str(e)}")


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
https://app.snsdconsultant.com/dashboard/marcel-gpt/library?tab=assigned

İyi çalışmalar,
SnSD Consultants
"""

        # Log the email (for development)
        print(f"[Email] To: {email}")
        print(f"[Email] Subject: {email_subject}")
        print(f"[Email] Body: {email_body}")

        # TODO: Actually send the email
        # await email_service.send_email(to=email, subject=email_subject, body=email_body)
