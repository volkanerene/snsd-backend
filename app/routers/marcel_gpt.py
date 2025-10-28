"""
MarcelGPT - HeyGen Video Generation API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from typing import Optional, List
from datetime import datetime

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user, require_permission
from app.services.heygen_service import get_heygen_service

router = APIRouter()


# =========================================================================
# Catalog Endpoints
# =========================================================================

@router.get("/avatars")
async def list_avatars(
    user=Depends(get_current_user),
    force_refresh: bool = Query(False, description="Force refresh cache"),
):
    """
    List available HeyGen avatars

    Returns cached results (24h TTL) unless force_refresh=true
    """
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    try:
        avatars = await heygen.list_avatars(force_refresh=force_refresh)
        return {"avatars": avatars, "count": len(avatars)}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch avatars: {str(e)}")


@router.get("/voices")
async def list_voices(
    user=Depends(get_current_user),
    force_refresh: bool = Query(False, description="Force refresh cache"),
    language: Optional[str] = Query(None, description="Filter by language"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
):
    """
    List available HeyGen voices with optional filters

    Returns cached results (24h TTL) unless force_refresh=true
    """
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    try:
        voices = await heygen.list_voices(force_refresh=force_refresh)

        # Apply filters
        if language:
            voices = [v for v in voices if v.get("language") == language]
        if gender:
            voices = [v for v in voices if v.get("gender") == gender]

        return {"voices": voices, "count": len(voices)}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch voices: {str(e)}")


# =========================================================================
# Brand Preset Endpoints
# =========================================================================

@router.get("/presets")
async def list_presets(
    user=Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List brand presets for current tenant"""
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    query = supabase.table("brand_presets") \
        .select("*") \
        .eq("tenant_id", tenant_id) \
        .range(offset, offset + limit - 1) \
        .order("created_at", desc=True)

    res = query.execute()
    return {"presets": ensure_response(res), "count": len(res.data) if res.data else 0}


@router.post("/presets")
async def create_preset(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """Create new brand preset"""
    require_permission(user, "marcel_gpt.manage_presets")

    tenant_id = user.get("tenant_id")
    user_id = user.get("id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Validate required fields
    required = ["name", "avatar_id", "voice_id"]
    for field in required:
        if not payload.get(field):
            raise HTTPException(400, f"Missing required field: {field}")

    preset_data = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "name": payload["name"],
        "description": payload.get("description"),
        "avatar_id": payload["avatar_id"],
        "avatar_style": payload.get("avatar_style", "normal"),
        "voice_id": payload["voice_id"],
        "language": payload.get("language", "en"),
        "tts_speed": payload.get("tts_speed", 1.0),
        "bg_type": payload.get("bg_type", "color"),
        "bg_value": payload.get("bg_value"),
        "overlay_logo_url": payload.get("overlay_logo_url"),
        "overlay_logo_position": payload.get("overlay_logo_position", "bottom-right"),
        "enable_subtitles": payload.get("enable_subtitles", False),
        "subtitle_format": payload.get("subtitle_format", "srt"),
        "video_width": payload.get("video_width", 1920),
        "video_height": payload.get("video_height", 1080),
        "aspect_ratio": payload.get("aspect_ratio", "16:9"),
        "is_default": payload.get("is_default", False),
    }

    res = supabase.table("brand_presets").insert(preset_data).execute()
    return ensure_response(res)[0] if res.data else None


@router.get("/presets/{preset_id}")
async def get_preset(
    preset_id: int,
    user=Depends(get_current_user),
):
    """Get preset details"""
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")

    res = supabase.table("brand_presets") \
        .select("*") \
        .eq("id", preset_id) \
        .eq("tenant_id", tenant_id) \
        .limit(1) \
        .execute()

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Preset not found")

    return data[0]


@router.delete("/presets/{preset_id}")
async def delete_preset(
    preset_id: int,
    user=Depends(get_current_user),
):
    """Delete preset"""
    require_permission(user, "marcel_gpt.manage_presets")

    tenant_id = user.get("tenant_id")

    res = supabase.table("brand_presets") \
        .delete() \
        .eq("id", preset_id) \
        .eq("tenant_id", tenant_id) \
        .execute()

    return {"message": "Preset deleted successfully"}


# =========================================================================
# Video Generation Endpoints
# =========================================================================

@router.post("/generate")
async def generate_video(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Generate video using HeyGen API

    Request body:
    {
        "title": "Video title",
        "input_text": "Text for avatar to speak",
        "avatar_id": "avatar_id",
        "voice_id": "voice_id",
        "engine": "v2" | "av4" | "template",
        "preset_id": 123,  # Optional
        "config": {  # Optional advanced settings
            "speed": 1.0,
            "avatar_style": "normal",
            "width": 1920,
            "height": 1080,
            "background": {...}
        }
    }
    """
    require_permission(user, "marcel_gpt.create_video")

    tenant_id = user.get("tenant_id")
    user_id = user.get("id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Validate required fields
    if not payload.get("input_text"):
        raise HTTPException(400, "input_text is required")
    if not payload.get("avatar_id"):
        raise HTTPException(400, "avatar_id is required")
    if not payload.get("voice_id"):
        raise HTTPException(400, "voice_id is required")

    engine = payload.get("engine", "v2")
    if engine not in ["v2", "av4", "template"]:
        raise HTTPException(400, "Invalid engine. Must be v2, av4, or template")

    # Get HeyGen service
    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    # Build callback URL
    from app.config import settings
    callback_url = f"{settings.API_URL}/marcel-gpt/webhook"

    # Create job record first
    job_data = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "preset_id": payload.get("preset_id"),
        "title": payload.get("title"),
        "engine": engine,
        "status": "pending",
        "input_text": payload["input_text"],
        "input_config": payload.get("config", {}),
    }

    job_res = supabase.table("video_jobs").insert(job_data).execute()
    job = ensure_response(job_res)[0]

    try:
        # Generate callback URL with job ID
        full_callback_url = f"{callback_url}?job_id={job['id']}"

        # Call HeyGen API based on engine
        config = payload.get("config", {})

        if engine == "v2":
            heygen_response = await heygen.create_video_v2(
                input_text=payload["input_text"],
                avatar_id=payload["avatar_id"],
                voice_id=payload["voice_id"],
                callback_url=full_callback_url,
                title=payload.get("title"),
                **config
            )
        elif engine == "av4":
            heygen_response = await heygen.create_video_av4(
                input_text=payload["input_text"],
                avatar_id=payload["avatar_id"],
                voice_id=payload["voice_id"],
                callback_url=full_callback_url,
                **config
            )
        else:
            raise HTTPException(400, "Template engine not yet implemented")

        # Extract video_id from response
        video_id = heygen_response.get("data", {}).get("video_id")

        if not video_id:
            raise HTTPException(500, "HeyGen API did not return video_id")

        # Update job with HeyGen video ID
        supabase.table("video_jobs") \
            .update({
                "heygen_job_id": video_id,
                "status": "queued",
                "queued_at": datetime.now().isoformat(),
                "callback_url": full_callback_url
            }) \
            .eq("id", job["id"]) \
            .execute()

        return {
            "job_id": job["id"],
            "heygen_job_id": video_id,
            "status": "queued",
            "message": "Video generation started"
        }

    except Exception as e:
        # Update job as failed
        supabase.table("video_jobs") \
            .update({
                "status": "failed",
                "error_message": str(e),
                "failed_at": datetime.now().isoformat()
            }) \
            .eq("id", job["id"]) \
            .execute()

        raise HTTPException(500, f"Video generation failed: {str(e)}")


# =========================================================================
# Job Management Endpoints
# =========================================================================

@router.get("/jobs")
async def list_jobs(
    user=Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List video generation jobs for current tenant"""
    require_permission(user, "marcel_gpt.view_jobs")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    query = supabase.table("video_jobs") \
        .select("*") \
        .eq("tenant_id", tenant_id)

    if status:
        query = query.eq("status", status)

    query = query.range(offset, offset + limit - 1) \
        .order("created_at", desc=True)

    res = query.execute()
    return {"jobs": ensure_response(res), "count": len(res.data) if res.data else 0}


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: int,
    user=Depends(get_current_user),
):
    """Get job details with artifacts"""
    require_permission(user, "marcel_gpt.view_jobs")

    tenant_id = user.get("tenant_id")

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

    # Get artifacts
    artifact_res = supabase.table("video_artifacts") \
        .select("*") \
        .eq("job_id", job_id) \
        .execute()

    job["artifacts"] = ensure_response(artifact_res)

    return job


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    user=Depends(get_current_user),
):
    """Cancel pending/queued job"""
    require_permission(user, "marcel_gpt.cancel_job")

    tenant_id = user.get("tenant_id")

    # Check job status
    job_res = supabase.table("video_jobs") \
        .select("status") \
        .eq("id", job_id) \
        .eq("tenant_id", tenant_id) \
        .limit(1) \
        .execute()

    job_data = ensure_response(job_res)
    if not job_data:
        raise HTTPException(404, "Job not found")

    current_status = job_data[0]["status"]
    if current_status not in ["pending", "queued"]:
        raise HTTPException(400, f"Cannot cancel job with status: {current_status}")

    # Update status
    supabase.table("video_jobs") \
        .update({"status": "cancelled"}) \
        .eq("id", job_id) \
        .execute()

    return {"message": "Job cancelled successfully"}


@router.get("/jobs/{job_id}/status")
async def check_job_status(
    job_id: int,
    user=Depends(get_current_user),
):
    """
    Check job status from HeyGen API
    Manually poll for updates (useful for debugging)
    """
    require_permission(user, "marcel_gpt.view_jobs")

    tenant_id = user.get("tenant_id")

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
        status_response = await heygen.get_video_status(heygen_job_id)
        return status_response
    except Exception as e:
        raise HTTPException(500, f"Failed to check status: {str(e)}")


# =========================================================================
# Asset Management Endpoints
# =========================================================================

@router.get("/assets")
async def list_assets(
    user=Depends(get_current_user),
    asset_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List uploaded assets for current tenant"""
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    query = supabase.table("marcel_assets") \
        .select("*") \
        .eq("tenant_id", tenant_id)

    if asset_type:
        query = query.eq("type", asset_type)

    query = query.range(offset, offset + limit - 1) \
        .order("created_at", desc=True)

    res = query.execute()
    return {"assets": ensure_response(res), "count": len(res.data) if res.data else 0}


@router.post("/assets")
async def create_asset(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Register asset (after upload to S3/Spaces)

    Request body:
    {
        "name": "Asset name",
        "type": "logo" | "background_image" | "background_video",
        "url": "https://...",
        "storage_key": "path/to/file",
        "file_size": 12345,
        "mime_type": "image/png"
    }
    """
    require_permission(user, "marcel_gpt.upload_assets")

    tenant_id = user.get("tenant_id")
    user_id = user.get("id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    asset_data = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "type": payload["type"],
        "name": payload["name"],
        "source": payload.get("source", "upload"),
        "url": payload["url"],
        "storage_key": payload.get("storage_key"),
        "file_size": payload.get("file_size"),
        "mime_type": payload.get("mime_type"),
        "meta": payload.get("meta", {})
    }

    res = supabase.table("marcel_assets").insert(asset_data).execute()
    return ensure_response(res)[0] if res.data else None
