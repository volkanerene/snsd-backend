"""
Marcel GPT Library - Premade Videos and Worker Assignments
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
import re
import json
import logging

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from app.config import settings
from app.db.supabase_client import supabase
from app.routers.deps import ensure_response, require_library_admin
from app.utils.auth import get_current_user, require_permission
from app.services.category_classifier import (
    classify_script_categories,
    VIDEO_CATEGORY_GROUPS,
    YOUTUBE_CATEGORY_KEY,
)

router = APIRouter()
logger = logging.getLogger(__name__)

CHANNEL_ID_PATTERN = re.compile(r'["\']channelId["\']\s*:\s*["\'](UC[0-9A-Za-z_\-]{20,})["\']')
BROWSE_ID_PATTERN = re.compile(r'["\']browseId["\']\s*:\s*["\'](UC[0-9A-Za-z_\-]{20,})["\']')
EXTERNAL_ID_PATTERN = re.compile(r'["\']externalChannelId["\']\s*:\s*["\'](UC[0-9A-Za-z_\-]{20,})["\']')
_CHANNEL_HANDLE_CACHE: dict[str, str] = {}


class AssignmentDocumentInput(BaseModel):
    file_name: str
    public_url: Optional[str] = None
    storage_key: Optional[str] = None
    content_type: Optional[str] = None
    file_size: Optional[int] = None


class AssignVideosRequest(BaseModel):
    video_ids: List[str]
    worker_ids: List[str]
    notes: Optional[str] = None
    documents: Optional[List[AssignmentDocumentInput]] = None


class ImportPremadeVideoRequest(BaseModel):
    title: str
    video_url: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    category: Optional[str] = "External"
    tags: Optional[List[str]] = None
    training_questions: Optional[List[Dict[str, Any]]] = None


class YoutubeVideo(BaseModel):
    video_id: str
    title: str
    url: str
    published_at: str
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    main_category: Optional[str] = None
    category_tags: Optional[List[str]] = None
    category_metadata: Optional[Dict[str, Any]] = None


# =========================================================================
# Premade Videos Endpoints
# =========================================================================

@router.get("/premade-videos")
async def list_premade_videos(
    user=Depends(get_current_user),
    category: Optional[str] = None,
    is_active: bool = True
):
    """List all premade training videos for the tenant (Library Admins only)"""
    require_library_admin(user)
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
    """Get a specific premade video (Library Admins only)"""
    require_library_admin(user)
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
    """Upsert an external video into the tenant's premade library (Library Admins only)"""
    require_library_admin(user)
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
        "training_questions": payload.training_questions or [],
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
    """Fetch latest YouTube videos for SnSD Consultants channel (Library Admins only)"""
    require_library_admin(user)
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
            # Use full namespace URI format for consistency
            video_id_elem = entry.find("{http://www.youtube.com/xml/schemas/2015}videoId")
            title_elem = entry.find("{http://www.w3.org/2005/Atom}title")
            published_elem = entry.find("{http://www.w3.org/2005/Atom}published")
            link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
            media_group = entry.find("{http://search.yahoo.com/mrss/}group")

            description_elem = media_group.find("{http://search.yahoo.com/mrss/}description") if media_group is not None else None

            # Use 'is None' check instead of 'not' to avoid XML Element truth value issues
            if video_id_elem is None or title_elem is None:
                print(f"[YouTube] Skipping entry: missing video_id_elem={video_id_elem is not None} or title_elem={title_elem is not None}")
                continue

            video_id_text = video_id_elem.text

            # Extract thumbnail URL with fallback logic
            thumbnail_url = None
            if media_group is not None:
                # Try media:thumbnail from media:group using full namespace URI
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

            combined_text = f"{title_elem.text or ''}\n{description_elem.text or ''}"
            classification = await classify_script_categories(combined_text, use_openai=False)

            youtube_metadata: Dict[str, Any] = classification.copy() if isinstance(classification, dict) else {}
            youtube_info = VIDEO_CATEGORY_GROUPS.get(YOUTUBE_CATEGORY_KEY, {})
            youtube_metadata["main_category"] = YOUTUBE_CATEGORY_KEY
            youtube_metadata["main_category_label"] = youtube_info.get("label", "SnSD YouTube Channel")
            youtube_metadata["main_category_emoji"] = youtube_info.get("emoji", "🟦")
            youtube_metadata.setdefault("tags", [])
            youtube_metadata.setdefault("tag_labels", [])
            youtube_metadata.setdefault("source", (classification or {}).get("source", "youtube_feed"))

            videos.append(
                YoutubeVideo(
                    video_id=video_id_text,
                    title=title_elem.text,
                    url=url,
                    published_at=published_elem.text if published_elem is not None else "",
                    thumbnail_url=thumbnail_url,
                    description=description_elem.text if description_elem is not None else None,
                    main_category=YOUTUBE_CATEGORY_KEY,
                    category_tags=youtube_metadata.get("tags"),
                    category_metadata=youtube_metadata
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
    (Library Admins only)
    """
    require_library_admin(user)
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

    assignment_rows = []
    try:
        fetch_res = supabase.table("marcel_gpt_video_assignments") \
            .select("id, assigned_to") \
            .eq("tenant_id", tenant_id) \
            .eq("video_id", payload.video_ids[0]) \
            .in_("assigned_to", payload.worker_ids) \
            .execute()
        assignment_rows = ensure_response(fetch_res) or []
    except Exception as fetch_error:
        logger.warning(f"[AssignVideos] Failed to fetch assignments for attachments: {fetch_error}")

    if payload.documents and assignment_rows:
        assignment_ids = [row["id"] for row in assignment_rows]
        try:
            supabase.table("marcel_gpt_assignment_documents") \
                .delete() \
                .in_("assignment_id", assignment_ids) \
                .execute()
        except Exception as delete_error:
            logger.warning(f"[AssignVideos] Failed clearing old documents: {delete_error}")

        documents_payload = []
        for assignment in assignment_rows:
            for doc in payload.documents or []:
                documents_payload.append({
                    "assignment_id": assignment["id"],
                    "file_name": doc.file_name,
                    "storage_key": doc.storage_key,
                    "public_url": doc.public_url,
                    "content_type": doc.content_type,
                    "file_size": doc.file_size
                })
        if documents_payload:
            try:
                supabase.table("marcel_gpt_assignment_documents").insert(documents_payload).execute()
            except Exception as doc_error:
                logger.warning(f"[AssignVideos] Failed inserting documents: {doc_error}")

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
                duration_seconds, category, training_questions
            ),
            assigned_by_user:assigned_by (
                id, full_name, email
            ),
            documents:marcel_gpt_assignment_documents(*)
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
    """Get assignment statistics for admins (Library Admins only)"""
    require_library_admin(user)
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


@router.get("/all-assignments")
async def get_all_assignments(
    user=Depends(get_current_user),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get all video assignments for the tenant (Library Admins only).
    Returns detailed assignment information including video and worker details.
    """
    require_library_admin(user)
    require_permission(user, "marcel_gpt.view_library")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Build query
    query = supabase.table("marcel_gpt_video_assignments") \
        .select(
            "id, status, created_at, video_id, assigned_to, "
            "assigned_by, notes, viewed_at, completed_at, quiz_score, quiz_completed_at, "
            "video:video_id(id, title, video_url, description, "
            "duration_seconds, thumbnail_url, category, training_questions), "
            "assigned_to_user:assigned_to(id, email, full_name), "
            "assigned_by_user:assigned_by(id, email, full_name), "
            "documents:marcel_gpt_assignment_documents(*)"
        ) \
        .eq("tenant_id", tenant_id)

    # Filter by status if provided
    if status:
        query = query.eq("status", status)

    # Get total count
    count_res = supabase.table("marcel_gpt_video_assignments") \
        .select("id", count="exact") \
        .eq("tenant_id", tenant_id)
    if status:
        count_res = count_res.eq("status", status)
    count_res = count_res.execute()
    total = count_res.count or 0

    # Execute query with pagination
    try:
        res = query \
            .order("created_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        assignments = res.data or []
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch assignments: {str(e)}")

    return {
        "data": assignments,
        "total": total,
        "offset": offset,
        "limit": limit
    }


@router.get("/training-results")
async def get_training_results(
    user=Depends(get_current_user),
    status: Optional[str] = Query(None)
):
    """Aggregated training results for admins (Company Admin / HSE Specialist)"""
    require_library_admin(user)
    require_permission(user, "marcel_gpt.view_library")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    query = supabase.table("marcel_gpt_video_assignments") \
        .select(
            "id, status, created_at, video_id, assigned_to, "
            "assigned_by, notes, viewed_at, completed_at, quiz_score, quiz_completed_at, "
            "video:video_id(id, title, video_url, description, "
            "duration_seconds, thumbnail_url, category, training_questions), "
            "assigned_to_user:assigned_to(id, email, full_name), "
            "assigned_by_user:assigned_by(id, email, full_name), "
            "documents:marcel_gpt_assignment_documents(*)"
        ) \
        .eq("tenant_id", tenant_id) \
        .order("created_at", desc=True)

    if status:
        query = query.eq("status", status)

    res = query.execute()
    assignments = ensure_response(res) or []

    total = len(assignments)
    completed = len([a for a in assignments if a.get("status") == "completed"])
    viewed = len([a for a in assignments if a.get("status") == "viewed"])
    pending = len([a for a in assignments if a.get("status") == "pending"])
    scores = [a.get("quiz_score") for a in assignments if isinstance(a.get("quiz_score"), (int, float))]
    avg_score = round(sum(scores) / len(scores), 2) if scores else None
    quiz_completed = len([a for a in assignments if a.get("quiz_completed_at")])
    quiz_completion_rate = (quiz_completed / total * 100) if total else 0

    summary = {
        "total_assignments": total,
        "pending_assignments": pending,
        "viewed_assignments": viewed,
        "completed_assignments": completed,
        "avg_quiz_score": avg_score,
        "quiz_completion_rate": round(quiz_completion_rate, 2)
    }

    return {"summary": summary, "assignments": assignments}


@router.post("/submit-quiz")
async def submit_quiz(
    payload: dict = Body(...),
    user=Depends(get_current_user)
):
    """
    Submit quiz answers and get scored results
    Stores answers and calculates score using AI evaluation for text answers
    """
    tenant_id = user.get("tenant_id")
    user_id = user.get("id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    assignment_id = payload.get("assignment_id")
    raw_video_id = payload.get("video_id")
    answers = payload.get("answers", [])

    if not assignment_id or not answers:
        raise HTTPException(400, "Missing required fields: assignment_id and answers")

    try:
        # Get the assignment and video to access training questions
        assignment_res = supabase.table("marcel_gpt_video_assignments") \
            .select("*") \
            .eq("id", assignment_id) \
            .eq("tenant_id", tenant_id) \
            .limit(1) \
            .execute()

        assignment_data = ensure_response(assignment_res)
        if not assignment_data:
            raise HTTPException(404, "Assignment not found")

        assignment_video_id = assignment_data[0].get("video_id")

        training_questions: List[Dict[str, Any]] = []
        if assignment_video_id:
            video_res = supabase.table("marcel_gpt_premade_videos") \
                .select("training_questions") \
                .eq("id", assignment_video_id) \
                .eq("tenant_id", tenant_id) \
                .limit(1) \
                .execute()
            video_data = ensure_response(video_res)
            if video_data:
                training_questions = video_data[0].get("training_questions", []) or []

        video_job_id: Optional[int] = None
        if raw_video_id is not None:
            try:
                video_job_id = int(raw_video_id)
            except (TypeError, ValueError):
                video_job_id = None

        if training_questions == [] and video_job_id is not None:
            video_job_res = supabase.table("video_jobs") \
                .select("training_questions") \
                .eq("id", video_job_id) \
                .eq("tenant_id", tenant_id) \
                .limit(1) \
                .execute()
            video_job_data = ensure_response(video_job_res)
            if video_job_data:
                training_questions = video_job_data[0].get("training_questions", []) or []

        if not training_questions:
            raise HTTPException(404, "Training questions not found for this video")

        # Score the answers
        from app.services.quiz_scoring_service import QuizScoringService
        scoring_service = QuizScoringService()
        scoring_result = await scoring_service.score_answers(answers, training_questions)

        score = scoring_result.get("score", 0)
        answered_questions = scoring_result.get("answers_with_scores", [])

        supabase.table("video_quiz_answers") \
            .delete() \
            .eq("assignment_id", assignment_id) \
            .eq("tenant_id", tenant_id) \
            .execute()

        question_lookup = {
            idx: (question or {})
            for idx, question in enumerate(training_questions)
        }

        # Store each answer in database
        for answer_data in answered_questions:
            q_index = answer_data.get("question_index")
            question_def = question_lookup.get(q_index, {})
            question_type = question_def.get("type")

            correct_display = answer_data.get("correct_answer")
            if question_type == "multiple_choice":
                options = question_def.get("options") or []
                correct_idx = question_def.get("correct_answer")
                if correct_display is None and isinstance(correct_idx, int) and 0 <= correct_idx < len(options):
                    correct_display = options[correct_idx]
            elif question_type == "text":
                correct_display = question_def.get("expected_answer") or correct_display

            answer_record = {
                "tenant_id": tenant_id,
                "assignment_id": assignment_id,
                "user_id": user_id,
                "video_id": video_job_id,
                "video_uuid": assignment_video_id,
                "question_index": answer_data.get("question_index"),
                "question_text": answer_data.get("question_text"),
                "question_type": answer_data.get("type"),
                "user_answer": answer_data.get("user_answer"),
                "correct_answer": correct_display,
                "is_correct": answer_data.get("is_correct"),
                "ai_score": answer_data.get("ai_score"),
                "points_earned": answer_data.get("points_earned")
            }

            supabase.table("video_quiz_answers").insert(answer_record).execute()

        # Update assignment with quiz completion
        update_res = supabase.table("marcel_gpt_video_assignments") \
            .update({
                "status": "completed",
                "completed_at": "now()",
                "quiz_completed_at": "now()",
                "quiz_score": score
            }) \
            .eq("id", assignment_id) \
            .execute()

        ensure_response(update_res)

        print(f"[MarcelGPT] Quiz submitted for assignment {assignment_id}: Score {score}%")

        return {
            "success": True,
            "score": score,
            "answers": answered_questions
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[MarcelGPT] Error submitting quiz: {str(e)}")
        raise HTTPException(500, f"Failed to submit quiz: {str(e)}")


@router.get("/quiz-responses")
async def get_quiz_responses(
    user=Depends(get_current_user),
    assignment_id: Optional[str] = Query(None),
    video_id: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get quiz responses (admin view)
    Groups answers per assignment so admins can review quiz performance.
    """
    require_library_admin(user)
    require_permission(user, "marcel_gpt.view_library")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    try:
        base_query = supabase.table("video_quiz_answers") \
            .select(
                "id, assignment_id, user_id, video_id, question_index, question_text, "
                "question_type, user_answer, correct_answer, is_correct, ai_score, "
                "points_earned, created_at"
            ) \
            .eq("tenant_id", tenant_id)

        if assignment_id:
            base_query = base_query.eq("assignment_id", assignment_id)
        if video_id:
            base_query = base_query.eq("video_id", video_id)

        answers_res = base_query \
            .order("created_at", desc=True) \
            .range(offset, offset + (limit * 3) - 1) \
            .execute()

        answers = ensure_response(answers_res) or []

        if not answers:
            return {
                "responses": [],
                "total": 0,
                "offset": offset,
                "limit": limit
            }

        assignment_ids = {
            answer.get("assignment_id") for answer in answers if answer.get("assignment_id")
        }

        assignments_map: Dict[str, Dict[str, Any]] = {}
        if assignment_ids:
            assignments_res = supabase.table("marcel_gpt_video_assignments") \
                .select(
                    "id, assigned_to, video_id, status, created_at, completed_at, "
                    "quiz_score, quiz_completed_at"
                ) \
                .in_("id", list(assignment_ids)) \
                .execute()
            assignment_rows = ensure_response(assignments_res) or []
            assignments_map = {row["id"]: row for row in assignment_rows if row.get("id")}

        video_ids = {
            assignment.get("video_id")
            for assignment in assignments_map.values()
            if assignment.get("video_id")
        }
        videos_map: Dict[str, Dict[str, Any]] = {}
        if video_ids:
            videos_res = supabase.table("marcel_gpt_premade_videos") \
                .select("id, title") \
                .in_("id", list(video_ids)) \
                .execute()
            video_rows = ensure_response(videos_res) or []
            videos_map = {row["id"]: row for row in video_rows if row.get("id")}

        profile_ids = {
            assignment.get("assigned_to")
            for assignment in assignments_map.values()
            if assignment.get("assigned_to")
        }
        profiles_map: Dict[str, Dict[str, Any]] = {}
        if profile_ids:
            profiles_res = supabase.table("profiles") \
                .select("id, email, full_name") \
                .in_("id", list(profile_ids)) \
                .execute()
            profile_rows = ensure_response(profiles_res) or []
            profiles_map = {row["id"]: row for row in profile_rows if row.get("id")}

        grouped: Dict[str, Dict[str, Any]] = {}
        for answer in answers:
            assignment_key = answer.get("assignment_id")
            if not assignment_key:
                continue

            assignment = assignments_map.get(assignment_key)
            if not assignment:
                continue

            entry = grouped.setdefault(assignment_key, {
                "id": assignment_key,
                "assignment_id": assignment_key,
                "video_id": assignment.get("video_id"),
                "video_title": videos_map.get(assignment.get("video_id"), {}).get("title") or "Untitled Video",
                "user_id": assignment.get("assigned_to"),
                "user_name": profiles_map.get(assignment.get("assigned_to"), {}).get("full_name") or "Team member",
                "user_email": profiles_map.get(assignment.get("assigned_to"), {}).get("email"),
                "completed_at": assignment.get("quiz_completed_at") or assignment.get("completed_at") or assignment.get("created_at"),
                "total_score": assignment.get("quiz_score"),
                "responses": []
            })

            entry["responses"].append({
                "question_index": answer.get("question_index"),
                "question_text": answer.get("question_text"),
                "question_type": answer.get("question_type"),
                "user_answer": answer.get("user_answer"),
                "correct_answer": answer.get("correct_answer"),
                "is_correct": answer.get("is_correct"),
                "ai_score": answer.get("ai_score"),
                "points_earned": answer.get("points_earned") or 0,
                "created_at": answer.get("created_at")
            })

        aggregated: List[Dict[str, Any]] = []
        for entry in grouped.values():
            responses = sorted(
                entry["responses"],
                key=lambda r: (r.get("question_index") if r.get("question_index") is not None else 0)
            )
            entry["responses"] = responses
            if entry.get("total_score") is None and responses:
                total_points = sum(resp.get("points_earned", 0) for resp in responses)
                entry["total_score"] = round(min(total_points, 100), 2)
            aggregated.append(entry)

        if min_score is not None:
            aggregated = [
                entry for entry in aggregated
                if (entry.get("total_score") or 0) >= min_score
            ]

        if video_id:
            aggregated = [
                entry for entry in aggregated
                if entry.get("video_id") == video_id
            ]

        aggregated.sort(
            key=lambda item: item.get("completed_at") or item.get("id"),
            reverse=True
        )

        total = len(aggregated)
        paginated = aggregated[offset: offset + limit]

        return {
            "responses": paginated,
            "total": total,
            "offset": offset,
            "limit": limit
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[MarcelGPT] Error fetching quiz responses: {str(e)}")
        raise HTTPException(500, f"Failed to fetch quiz responses: {str(e)}")


# =========================================================================
# Helper Functions
# =========================================================================

async def send_assignment_emails(workers: List[dict], videos: List[dict], assigned_by_name: str):
    """
    Send email notifications to workers about video assignments via Brevo SMTP
    """
    from app.services.email_service import EmailService, render_html_from_text

    for worker in workers:
        email = worker.get("email")
        if not email:
            continue

        # Prepare email content
        video_titles = ", ".join([v['title'] for v in videos])

        email_subject = f"Yeni Eğitim Videoları Atandı - {len(videos)} Video"
        email_body = f"""Merhaba {worker.get('full_name', '')},

{assigned_by_name} tarafından size {len(videos)} adet eğitim videosu atandı:

{video_titles}

Videoları görüntülemek için lütfen platformda oturum açın:
https://www.snsdconsultant.com/dashboard/marcel-gpt/library?tab=assigned

İyi çalışmalar,
SnSD Consultants"""

        email_html = render_html_from_text(email_body)

        # Send email via Brevo SMTP
        success, error_msg = EmailService.send_email(
            to_email=email,
            subject=email_subject,
            text_body=email_body,
            html_body=email_html
        )

        if success:
            print(f"[Email] Successfully sent video assignment email to {email}")
        else:
            print(f"[Email] Failed to send email to {email}: {error_msg}")
