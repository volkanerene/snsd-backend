"""
MarcelGPT - HeyGen Video Generation API Routes
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File
from httpx import HTTPStatusError
from pydantic import BaseModel, Field

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user, require_permission
from app.services.heygen_service import get_heygen_service, get_fallback_heygen_service
from app.services.photo_avatar_service import PhotoAvatarService

router = APIRouter()


class AdvancedVideoConfigModel(BaseModel):
    backgroundType: str = Field(..., alias="backgroundType")
    backgroundColor: Optional[str] = Field(None, alias="backgroundColor")
    backgroundImageUrl: Optional[str] = Field(None, alias="backgroundImageUrl")
    language: str = Field("en", alias="language")
    speed: float = Field(1.0, alias="speed")
    tone: Optional[str] = Field(None, alias="tone")
    enableSubtitles: bool = Field(False, alias="enableSubtitles")
    subtitleLanguage: Optional[str] = Field(None, alias="subtitleLanguage")
    width: int = Field(1280, alias="width")
    height: int = Field(720, alias="height")
    aspectRatio: str = Field("16:9", alias="aspectRatio")
    avatarStyle: str = Field("normal", alias="avatarStyle")

    class Config:
        allow_population_by_field_name = True


class CreateLookRequest(BaseModel):
    name: str
    prompt: Optional[str] = None
    notes: Optional[str] = None
    voice_id: str = Field(..., alias="voiceId")
    config: AdvancedVideoConfigModel
    look_options: Optional[Dict[str, Any]] = Field(None, alias="lookOptions")
    base_avatar_id: Optional[str] = Field(None, alias="baseAvatarId")
    base_avatar_preview_url: Optional[str] = Field(None, alias="baseAvatarPreviewUrl")

    class Config:
        allow_population_by_field_name = True


def serialize_photo_avatar_look(record: Dict[str, Any]) -> Dict[str, Any]:
    config = record.get("config") or {}
    meta = record.get("meta") or {}
    return {
        "id": record.get("id"),
        "name": record.get("name"),
        "notes": record.get("prompt"),
        "status": record.get("status"),
        "avatarId": record.get("heygen_look_id"),
        "voiceId": record.get("voice_id"),
        "previewUrls": record.get("preview_urls") or [],
        "coverUrl": record.get("cover_url"),
        "generationId": record.get("heygen_generation_id"),
        "errorMessage": record.get("error_message"),
        "config": config,
        "meta": meta,
        "presetId": meta.get("brand_preset_id"),
        "source": meta.get("source"),
        "groupId": meta.get("group_id"),
        "groupName": meta.get("group_name"),
        "createdAt": record.get("created_at"),
        "updatedAt": record.get("updated_at")
    }


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
        import sys
        print(f"[MarcelGPT] Fetched {len(avatars)} avatars for tenant {tenant_id}", file=sys.stderr, flush=True)
        return {"avatars": avatars, "count": len(avatars), "debug": {"tenant_id": str(tenant_id), "avatar_count": len(avatars), "force_refresh": force_refresh}}
    except Exception as e:
        import sys
        print(f"[MarcelGPT] Error fetching avatars: {str(e)}", file=sys.stderr, flush=True)
        raise HTTPException(500, f"Failed to fetch avatars: {str(e)}")


@router.get("/voices")
async def list_voices(
    user=Depends(get_current_user),
    force_refresh: bool = Query(False, description="Force refresh cache"),
    language: Optional[str] = Query(None, description="Filter by language"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    limit: int = Query(50, ge=1, le=100, description="Number of voices to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
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

        # Apply pagination
        total = len(voices)
        voices = voices[offset:offset + limit]

        return {"voices": voices, "count": len(voices), "total": total, "offset": offset, "limit": limit}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch voices: {str(e)}")


@router.get("/avatar-groups")
async def list_avatar_groups(
    include_avatars: bool = Query(False, description="Include avatars for each group"),
    user=Depends(get_current_user),
):
    """List HeyGen avatar groups for current tenant"""
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    try:
        groups = await heygen.list_avatar_groups()
        serialized: List[Dict[str, Any]] = []

        for group in groups:
            group_id = (
                group.get("group_id")
                or group.get("avatar_group_id")
                or group.get("id")
            )
            if not group_id:
                continue

            item: Dict[str, Any] = {
                "id": group_id,
                "name": group.get("name"),
                "numLooks": group.get("num_looks")
                or group.get("look_count")
                or group.get("num_avatars")
                or group.get("avatar_count")
                or 0,
                "previewImage": group.get("preview_image")
                or group.get("preview_image_url")
                or group.get("cover_url"),
                "meta": group,
            }

            if include_avatars and item["numLooks"]:
                avatars = await heygen.list_avatars_in_group(str(group_id))
                item["avatars"] = avatars

            serialized.append(item)

        return {"groups": serialized, "count": len(serialized)}
    except Exception as e:
        raise HTTPException(500, f"Failed to fetch avatar groups: {str(e)}")


@router.get("/avatar-groups-v2")
async def list_avatar_groups_v2(
    include_avatars: bool = Query(False, description="Include avatars for each group"),
    user=Depends(get_current_user),
):
    """
    List virtual avatar groups based on fetched avatars from HeyGen
    Groups avatars by their base name (Adrian, Abigail, etc.)
    This bypasses the avatar_group.list API which has auth issues
    """
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    try:
        # Fetch all avatars from HeyGen
        all_avatars = await heygen.list_avatars()

        # Group avatars by base name (first word of avatar_name)
        groups_dict: Dict[str, Dict[str, Any]] = {}

        for avatar in all_avatars:
            avatar_name = avatar.get("avatar_name", "Unknown")
            avatar_id = avatar.get("avatar_id", "")

            # Extract base name (first word)
            base_name = avatar_name.split()[0] if avatar_name else "Unknown"

            # Create group if not exists
            if base_name not in groups_dict:
                groups_dict[base_name] = {
                    "id": base_name.lower(),
                    "name": base_name,
                    "avatars": [],
                    "preview_image": avatar.get("preview_image_url"),
                    "num_looks": 0
                }

            # Add avatar to group
            groups_dict[base_name]["avatars"].append(avatar)
            groups_dict[base_name]["num_looks"] += 1

        # Convert to list and sort by name
        groups = sorted(
            groups_dict.values(),
            key=lambda g: g["name"]
        )

        # Filter to only return previews if not including avatars
        if not include_avatars:
            for group in groups:
                group.pop("avatars", None)

        return {"groups": groups, "count": len(groups)}
    except Exception as e:
        import sys
        print(f"[MarcelGPT] Error in list_avatar_groups_v2: {str(e)}", file=sys.stderr, flush=True)
        raise HTTPException(500, f"Failed to fetch avatar groups: {str(e)}")


@router.get("/avatar-groups/{group_id}/avatars")
async def get_custom_group_avatars(
    group_id: str,
    user=Depends(get_current_user),
):
    """
    Fetch avatars from a specific custom avatar group by ID

    This endpoint allows direct access to custom HeyGen avatar groups like Marcel
    by their group ID. Returns all avatars in the group with full details.

    Example: /avatar-groups/4280ce1878e74185bdb8471aaa3e13cc/avatars
    """
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    try:
        import sys
        print(f"[MarcelGPT] Fetching avatars for custom group: {group_id}", file=sys.stderr, flush=True)

        fallback_used = False

        try:
            avatars = await heygen.list_avatars_in_group(group_id)
        except HTTPStatusError as http_error:
            status = http_error.response.status_code if http_error.response else None
            print(f"[MarcelGPT] Primary HeyGen request failed for group {group_id} with status {status}", file=sys.stderr, flush=True)
            if status in {401, 403}:
                fallback_service = get_fallback_heygen_service()
                if not fallback_service:
                    raise HTTPException(502, "HeyGen denied access to this avatar group and no fallback API key is configured")
                print(f"[MarcelGPT] Retrying custom group {group_id} with fallback HeyGen API key", file=sys.stderr, flush=True)
                avatars = await fallback_service.list_avatars_in_group(group_id)
                fallback_used = True
            else:
                raise

        print(f"[MarcelGPT] Retrieved {len(avatars)} avatars from group {group_id} (fallback={fallback_used})", file=sys.stderr, flush=True)

        return {
            "avatars": avatars,
            "count": len(avatars),
            "group_id": group_id,
            "debug": {"usedFallbackApiKey": fallback_used}
        }
    except HTTPException:
        raise
    except Exception as e:
        import sys
        print(f"[MarcelGPT] Error fetching avatars from group {group_id}: {str(e)}", file=sys.stderr, flush=True)
        raise HTTPException(500, f"Failed to fetch avatars from group: {str(e)}")


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

# =========================================================================
# Photo Avatar Look Endpoints
# =========================================================================


@router.get("/photo-avatars/looks")
async def list_photo_avatar_looks(
    user=Depends(get_current_user),
    force_refresh: bool = Query(False, description="Force refresh cache"),
    limit: int = Query(50, ge=1, le=100, description="Number of looks to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List photo avatar looks for the current tenant"""
    import sys
    print(f"\n[MarcelGPT] list_photo_avatar_looks called | tenant={user.get('tenant_id')} | force_refresh={force_refresh}", file=sys.stderr, flush=True)

    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    service = PhotoAvatarService(str(tenant_id), str(user.get("id")))
    looks = await service.list_looks(force_refresh=force_refresh)

    print(f"[MarcelGPT] Service returned {len(looks)} looks", file=sys.stderr, flush=True)

    serialized_looks = [serialize_photo_avatar_look(look) for look in looks]

    print(f"[MarcelGPT] Serialized {len(serialized_looks)} looks", file=sys.stderr, flush=True)
    if serialized_looks:
        print(f"[MarcelGPT] First look: id={serialized_looks[0].get('id')}, name={serialized_looks[0].get('name')}, avatarId={serialized_looks[0].get('avatarId')}", file=sys.stderr, flush=True)

    # Apply pagination
    total = len(serialized_looks)
    paginated_looks = serialized_looks[offset:offset + limit]

    response = {
        "looks": paginated_looks,
        "count": len(paginated_looks),
        "total": total,
        "offset": offset,
        "limit": limit
    }

    print(f"[MarcelGPT] Returning response with {response['count']} looks (total: {total})\n", file=sys.stderr, flush=True)

    return response


@router.post("/photo-avatars/looks")
async def create_photo_avatar_look(
    payload: CreateLookRequest,
    user=Depends(get_current_user),
):
    """Create a new HeyGen photo avatar look and persist config"""
    require_permission(user, "marcel_gpt.manage_presets")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    service = PhotoAvatarService(str(tenant_id), str(user.get("id")))

    config_dict = payload.config.dict(by_alias=False)
    options_dict = payload.look_options or None

    look = await service.create_look(
        name=payload.name,
        prompt=payload.prompt,
        notes=payload.notes,
        config=config_dict,
        voice_id=payload.voice_id,
        look_options=options_dict,
        base_avatar_id=payload.base_avatar_id,
        base_avatar_preview_url=payload.base_avatar_preview_url
    )

    return {"look": serialize_photo_avatar_look(look)}


@router.get("/photo-avatars/looks/{look_id}")
async def get_photo_avatar_look(
    look_id: int,
    refresh: bool = Query(False, description="Refresh status from HeyGen"),
    user=Depends(get_current_user),
):
    """Fetch a specific photo avatar look"""
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    service = PhotoAvatarService(str(tenant_id), str(user.get("id")))
    look = await service.get_look(look_id, refresh=refresh)
    return {"look": serialize_photo_avatar_look(look)}


@router.post("/photo-avatars/looks/{look_id}/refresh")
async def refresh_photo_avatar_look(
    look_id: int,
    user=Depends(get_current_user),
):
    """Force refresh a look's status from HeyGen"""
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    service = PhotoAvatarService(str(tenant_id), str(user.get("id")))
    look = await service.refresh_look_status(look_id, auto=False)
    return {"look": serialize_photo_avatar_look(look)}


class GeneratePhotoAvatarLookRequest(BaseModel):
    image_url: str = Field(..., description="URL of avatar image (e.g., preview image from HeyGen)")
    group_id: str = Field(..., description="Avatar group ID (e.g., Marcel group ID)")
    prompt: str = Field(..., description="Description of the look to generate")
    style: str = Field(default="Realistic", description="Style: 'Realistic', 'Pixar', 'Cinematic', 'Vintage', 'Noir', 'Cyberpunk', 'Unspecified'")
    orientation: str = Field(default="square", description="Orientation: 'square', 'horizontal', 'vertical'")
    pose: str = Field(default="half_body", description="Pose: 'half_body', 'close_up', 'full_body'")


@router.post("/photo-avatars/looks/generate")
async def generate_photo_avatar_look(
    payload: GeneratePhotoAvatarLookRequest,
    user=Depends(get_current_user),
):
    """
    Generate new photo avatar looks using HeyGen's photo avatar generation API

    This endpoint generates 4 new look variations based on the provided image and parameters.
    Returns generation_id which can be used to track status and retrieve generated image_keys.

    Note: This is an async operation. Use the generation_id to poll the status.
    """
    require_permission(user, "marcel_gpt.manage_presets")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    try:
        import sys
        print(f"[MarcelGPT] Generating photo avatar looks | group={payload.group_id} | style={payload.style} | orientation={payload.orientation} | pose={payload.pose}", file=sys.stderr, flush=True)

        # Validate style, orientation, and pose values
        valid_styles = ["Realistic", "Pixar", "Cinematic", "Vintage", "Noir", "Cyberpunk", "Unspecified"]
        valid_orientations = ["square", "horizontal", "vertical"]
        valid_poses = ["half_body", "close_up", "full_body"]

        if payload.style not in valid_styles:
            raise HTTPException(400, f"Invalid style. Must be one of: {', '.join(valid_styles)}")
        if payload.orientation not in valid_orientations:
            raise HTTPException(400, f"Invalid orientation. Must be one of: {', '.join(valid_orientations)}")
        if payload.pose not in valid_poses:
            raise HTTPException(400, f"Invalid pose. Must be one of: {', '.join(valid_poses)}")

        # Call HeyGen API to generate looks
        generation_response = await heygen.generate_photo_avatar_looks(
            image_url=payload.image_url,
            group_id=payload.group_id,
            prompt=payload.prompt,
            style=payload.style,
            orientation=payload.orientation,
            pose=payload.pose
        )

        print(f"[MarcelGPT] Full generation response: {generation_response}", file=sys.stderr, flush=True)

        # Extract data - HeyGen returns response with data wrapper
        data = generation_response.get("data", generation_response)
        generation_id = data.get("generation_id")

        print(f"[MarcelGPT] generation_id={generation_id}, status=initiated (async)", file=sys.stderr, flush=True)

        return {
            "generation_id": generation_id,
            "status": "processing",
            "image_keys": [],
            "message": "Photo avatar generation initiated. Generation ID: " + str(generation_id)
        }

    except HTTPException:
        raise
    except Exception as e:
        import sys
        print(f"[MarcelGPT] Error generating photo avatar looks: {str(e)}", file=sys.stderr, flush=True)
        raise HTTPException(500, f"Failed to generate photo avatar looks: {str(e)}")


@router.get("/photo-avatars/generations/{generation_id}")
async def get_photo_avatar_generation_status(
    generation_id: str,
    user=Depends(get_current_user),
):
    """
    Check the status of a photo avatar generation job

    Returns the generation status and image_keys once complete.
    Status values: 'processing', 'success', 'failed'

    Note: HeyGen uses different status values:
    - 'in_progress' → we return 'processing'
    - 'completed' → we return 'success'
    - 'failed' → we return 'failed'
    """
    require_permission(user, "marcel_gpt.manage_presets")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    try:
        import sys
        print(f"[MarcelGPT] Checking generation status: {generation_id}", file=sys.stderr, flush=True)

        # Call HeyGen API to get generation status
        status_response = await heygen.get_photo_avatar_generation(generation_id)

        print(f"[MarcelGPT] Status response: {status_response}", file=sys.stderr, flush=True)

        # Extract data - HeyGen wraps response in "data" key
        data = status_response.get("data", status_response)

        # Get HeyGen's status and map it to our standard values
        heygen_status = data.get("status", "unknown")
        status_map = {
            "in_progress": "processing",
            "completed": "success",
            "failed": "failed"
        }
        status = status_map.get(heygen_status, heygen_status)

        # HeyGen returns image_key_list and image_url_list
        image_key_list = data.get("image_key_list") or []
        image_url_list = data.get("image_url_list") or []

        # Ensure they're lists
        if not isinstance(image_key_list, list):
            image_key_list = []
        if not isinstance(image_url_list, list):
            image_url_list = []

        print(f"[MarcelGPT] generation_id={generation_id}, heygen_status={heygen_status}, mapped_status={status}, image_keys_count={len(image_key_list)}", file=sys.stderr, flush=True)

        return {
            "generation_id": generation_id,
            "status": status,
            "image_keys": image_key_list,
            "image_urls": image_url_list,
            "message": f"Generation {status} - {len(image_key_list)} images available"
        }

    except Exception as e:
        import sys
        print(f"[MarcelGPT] Error checking generation status: {str(e)}", file=sys.stderr, flush=True)
        raise HTTPException(500, f"Failed to check generation status: {str(e)}")


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

    # Accept either avatar_id (standard avatars) or image_key (photo avatars)
    avatar_id = payload.get("avatar_id") or payload.get("image_key")
    if not avatar_id:
        raise HTTPException(400, "avatar_id or image_key is required")

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

        # Prepare HeyGen kwargs
        heygen_kwargs = dict(config)

        # For AV4 engine with photo avatars, pass image_key
        if engine == "av4" and payload.get("image_key"):
            heygen_kwargs["image_key"] = payload["image_key"]

        if engine == "v2":
            heygen_response = await heygen.create_video_v2(
                input_text=payload["input_text"],
                avatar_id=avatar_id,
                voice_id=payload["voice_id"],
                callback_url=full_callback_url,
                title=payload.get("title"),
                **heygen_kwargs
            )
        elif engine == "av4":
            heygen_response = await heygen.create_video_av4(
                input_text=payload["input_text"],
                avatar_id=avatar_id,
                voice_id=payload["voice_id"],
                callback_url=full_callback_url,
                video_title=payload.get("title") or payload.get("video_title"),
                **heygen_kwargs
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


# =========================================================================
# Script Generation Endpoints (ChatGPT Integration)
# =========================================================================

@router.post("/scripts/generate")
async def generate_script(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Generate video script using ChatGPT

    Request body:
    {
        "prompt": "Generate a script about...",
        "context": "Additional context (optional)",
        "max_tokens": 1000,
        "temperature": 0.7
    }
    """
    require_permission(user, "marcel_gpt.access")

    from app.services.openai_service import OpenAIService

    if not payload.get("prompt"):
        raise HTTPException(400, "prompt is required")

    try:
        openai_service = OpenAIService()
        script = await openai_service.generate_video_script(
            prompt=payload["prompt"],
            context=payload.get("context"),
            max_tokens=payload.get("max_tokens", 1000),
            temperature=payload.get("temperature", 0.7),
        )

        return {
            "script": script,
            "prompt": payload["prompt"],
            "generated_at": datetime.now().isoformat()
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Script generation failed: {str(e)}")


@router.post("/scripts/refine")
async def refine_script(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Refine/edit existing script using ChatGPT

    Request body:
    {
        "original_script": "Original script text",
        "refinement_instructions": "Make it more professional..."
    }
    """
    require_permission(user, "marcel_gpt.access")

    from app.services.openai_service import OpenAIService

    if not payload.get("original_script"):
        raise HTTPException(400, "original_script is required")
    if not payload.get("refinement_instructions"):
        raise HTTPException(400, "refinement_instructions is required")

    try:
        openai_service = OpenAIService()
        refined_script = await openai_service.refine_script(
            original_script=payload["original_script"],
            refinement_instructions=payload["refinement_instructions"],
        )

        return {
            "script": refined_script,
            "original_script": payload["original_script"],
            "refinement_instructions": payload["refinement_instructions"],
            "generated_at": datetime.now().isoformat()
        }

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Script refinement failed: {str(e)}")


# =========================================================================
# Incident Report Dialogues Endpoints
# =========================================================================

@router.get("/incident-reports")
async def list_incident_reports(
    user=Depends(get_current_user),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    department: Optional[str] = Query(None, description="Filter by department"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List incident report dialogues for script generation
    
    These are pre-written safety incident dialogues that can be used
    to quickly generate safety training videos
    """
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    query = supabase.table("incident_report_dialogues") \
        .select("*") \
        .eq("tenant_id", tenant_id)

    if category:
        query = query.eq("category", category)
    if severity:
        query = query.eq("severity", severity)
    if department:
        query = query.eq("department", department)

    query = query.range(offset, offset + limit - 1) \
        .order("created_at", desc=True)

    res = query.execute()
    return {"reports": ensure_response(res), "count": len(res.data) if res.data else 0}


@router.get("/incident-reports/{report_id}")
async def get_incident_report(
    report_id: int,
    user=Depends(get_current_user),
):
    """Get specific incident report dialogue"""
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")

    res = supabase.table("incident_report_dialogues") \
        .select("*") \
        .eq("id", report_id) \
        .eq("tenant_id", tenant_id) \
        .limit(1) \
        .execute()

    data = ensure_response(res)
    if not data:
        raise HTTPException(404, "Incident report not found")

    return data[0]


# =========================================================================
# Script Generation Endpoints
# =========================================================================

class GenerateScriptRequest(BaseModel):
    prompt: str
    context: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


class GenerateIncidentScriptRequest(BaseModel):
    what_happened: str
    why_did_it_happen: Optional[str] = None
    what_did_they_learn: Optional[str] = None
    ask_yourself_or_crew: Optional[str] = None


@router.post("/scripts/generate")
async def generate_script_from_topic(
    payload: GenerateScriptRequest,
    user=Depends(get_current_user),
):
    """Generate a video script from an educational topic"""
    require_permission(user, "modules.access_marcel_gpt")

    from app.services.script_generation_service import generate_script_from_topic

    result = await generate_script_from_topic(payload.prompt)

    if not result.get("success"):
        raise HTTPException(500, result.get("error", "Failed to generate script"))

    return result


@router.post("/scripts/from-pdf")
async def generate_script_from_pdf(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    """Generate a video script from a PDF file"""
    require_permission(user, "marcel_gpt.access")

    from app.services.script_generation_service import (
        generate_script_from_pdf,
        _extract_text_from_pdf
    )

    try:
        # Read PDF file
        pdf_bytes = await file.read()

        if not pdf_bytes:
            raise HTTPException(400, "PDF file is empty")

        # Extract text from PDF
        pdf_text = _extract_text_from_pdf(pdf_bytes)

        if not pdf_text.strip():
            raise HTTPException(400, "Could not extract text from PDF")

        # Generate script
        result = await generate_script_from_pdf(pdf_text)

        if not result.get("success"):
            raise HTTPException(500, result.get("error", "Failed to generate script from PDF"))

        return {**result, "filename": file.filename}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF Script Gen] Error: {str(e)}")
        raise HTTPException(500, f"Error processing PDF: {str(e)}")


@router.post("/scripts/from-incident")
async def generate_script_from_incident(
    payload: GenerateIncidentScriptRequest,
    user=Depends(get_current_user),
):
    """
    Generate a video script from incident details.
    AI will find similar incidents in database and use them for context.
    """
    require_permission(user, "modules.access_marcel_gpt")

    tenant_id = user.get("tenant_id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    from app.services.script_generation_service import generate_script_from_incident

    result = await generate_script_from_incident(
        what_happened=payload.what_happened,
        why_did_it_happen=payload.why_did_it_happen,
        what_did_they_learn=payload.what_did_they_learn,
        ask_yourself_or_crew=payload.ask_yourself_or_crew,
        tenant_id=tenant_id
    )

    if not result.get("success"):
        raise HTTPException(500, result.get("error", "Failed to generate script"))

    return result
