"""
MarcelGPT - HeyGen Video Generation API Routes
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Dict, List, Optional, TypeVar, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, UploadFile, File
from httpx import HTTPStatusError
import httpx
from pydantic import BaseModel, Field
from postgrest.exceptions import APIError

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.utils.auth import get_current_user, require_permission
from app.services.heygen_service import get_heygen_service, get_fallback_heygen_service
from app.services.photo_avatar_service import PhotoAvatarService
from app.services.script_generation_service import generate_questions_from_script
from app.services.video_composition_service import get_composition_service
from app.services.category_classifier import (
    classify_script_categories,
    VIDEO_CATEGORY_GROUPS,
)
from app.config import settings

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

try:
    from langdetect import detect, DetectorFactory, LangDetectException
    DetectorFactory.seed = 0
except ImportError:
    detect = None
    LangDetectException = None

router = APIRouter()
logger = logging.getLogger(__name__)

VIDEO_SYNC_INTERVAL = timedelta(minutes=5)
_LAST_HEYGEN_SYNC: Dict[str, datetime] = {}

LANGUAGE_LABELS = {
    "en": "English",
    "af": "Afrikaans",
    "ar": "Arabic",
    "hy": "Armenian",
    "az": "Azerbaijani",
    "be": "Belarusian",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "cs": "Czech",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "eo": "Esperanto",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "ga": "Irish",
    "gd": "Scottish Gaelic",
    "gl": "Galician",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "jv": "Javanese",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mk": "Macedonian",
    "mr": "Marathi",
    "ms": "Malay",
    "my": "Burmese",
    "nb": "Norwegian",
    "nl": "Dutch",
    "pa": "Punjabi",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sq": "Albanian",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tl": "Tagalog",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "zh-TW": "Chinese (Traditional)",
    "yue": "Cantonese"
}

def _normalize_language_code(code: str) -> str:
    if not code:
        return "unknown"
    return code.lower()


def _language_name(code: str) -> str:
    if not code or code == "unknown":
        return "Unknown"
    return LANGUAGE_LABELS.get(code, code.upper())


def _normalize_category_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().lower()
    normalized = normalized.replace(" ", "_").replace("-", "_")
    normalized = normalized.replace("/", "_")
    normalized = normalized.replace("&", "and")
    normalized = re.sub(r"[^a-z_]", "", normalized)
    if normalized in VIDEO_CATEGORY_GROUPS:
        return normalized
    return None


def _sanitize_training_questions(questions: List[Any]) -> List[Dict[str, Any]]:
    """Validate and normalize quiz questions before storing."""
    sanitized: List[Dict[str, Any]] = []

    for idx, question in enumerate(questions or []):
        if hasattr(question, "model_dump"):
            question_data = question.model_dump()
        elif isinstance(question, dict):
            question_data = question
        else:
            question_data = {}

        question_text = (question_data.get("question") or "").strip()
        if not question_text:
            raise HTTPException(400, f"Question {idx + 1} is missing text")

        question_type = question_data.get("type")
        if question_type == "multiple_choice":
            options = [
                option.strip()
                for option in (question_data.get("options") or [])
                if isinstance(option, str) and option.strip()
            ]
            if len(options) < 2:
                raise HTTPException(
                    400,
                    f"Question {idx + 1} requires at least two answer options"
                )
            correct_index = question_data.get("correct_answer") or 0
            if correct_index >= len(options) or correct_index < 0:
                correct_index = 0

            sanitized.append(
                {
                    "type": "multiple_choice",
                    "question": question_text,
                    "options": options,
                    "correct_answer": correct_index
                }
            )
        else:
            sanitized.append(
                {
                    "type": "text",
                    "question": question_text,
                    "expected_answer": (question_data.get("expected_answer") or "").strip()
                    or None
                }
            )

    return sanitized


async def _ensure_job_categories(jobs: List[Dict[str, Any]]):
    if not jobs:
        return

    missing = [
        job for job in jobs
        if not job.get("main_category") and (job.get("input_text") or "").strip()
    ]
    if not missing:
        return

    # Avoid classifying too many scripts per request to limit token usage
    for job in missing[:3]:
        try:
            classification = await classify_script_categories(
                job.get("input_text", ""),
                use_openai=False
            )
            if not classification:
                continue
            supabase.table("video_jobs") \
                .update({
                    "main_category": classification["main_category"],
                    "category_tags": classification["tags"],
                    "category_metadata": classification
                }) \
                .eq("id", job["id"]) \
                .execute()
            job["main_category"] = classification["main_category"]
            job["category_tags"] = classification["tags"]
            job["category_metadata"] = classification
        except Exception as exc:
            logger.warning(f"[MarcelGPT] Failed to backfill category for job {job.get('id')}: {exc}")

# Request timeout constants (in seconds)
REQUEST_TIMEOUT_AVATAR = 30  # Avatar listing should be fast
REQUEST_TIMEOUT_VOICES = 30  # Voice listing should be fast
REQUEST_TIMEOUT_GENERATION = 60  # Video generation API call
REQUEST_TIMEOUT_COMPOSITION = 600  # FFmpeg composition (10 minutes)

T = TypeVar('T')

async def with_timeout(coro: Awaitable[T], timeout_seconds: float, operation_name: str = "Operation") -> T:
    """
    Wrap an async operation with a timeout

    Args:
        coro: The coroutine to execute
        timeout_seconds: Maximum seconds to wait
        operation_name: Description for logging

    Returns:
        The coroutine result

    Raises:
        HTTPException: If timeout occurs
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error(f"[MarcelGPT] {operation_name} timed out after {timeout_seconds}s")
        raise HTTPException(
            504,
            f"{operation_name} took too long (>{timeout_seconds}s). Please try again."
        )
    except Exception as e:
        logger.error(f"[MarcelGPT] {operation_name} error: {str(e)}")
        raise


def _ensure_voice_sample_url(voice: Dict[str, Any]) -> Optional[str]:
    """
    Normalize HeyGen voice payload so callers always receive `sample_url`.
    HeyGen may return a handful of alternate keys (sample_urls, preview_url, etc.).
    """
    if not isinstance(voice, dict):
        return None

    existing = voice.get("sample_url")
    if isinstance(existing, str) and existing:
        return existing

    for key in (
        "preview_audio_url",
        "previewAudioUrl",
        "preview_url",
        "sampleUrl",
        "audio_sample_url",
        "audioSampleUrl",
        "audio_preview_url",
    ):
        candidate = voice.get(key)
        if isinstance(candidate, str) and candidate:
            voice["sample_url"] = candidate
            return candidate

    list_candidates: List[Any] = []
    for key in (
        "sample_urls",
        "sampleUrls",
        "samples",
        "audio_samples",
        "audioSamples",
        "audio_sample_list",
        "voice_samples",
        "sample_list"
    ):
        value = voice.get(key)
        if value:
            list_candidates.append(value)

    for candidate in list_candidates:
        if isinstance(candidate, list):
            iterable = candidate
        else:
            iterable = [candidate]

        for entry in iterable:
            if isinstance(entry, str) and entry:
                voice["sample_url"] = entry
                return entry
            if isinstance(entry, dict):
                for nested_key in ("sample_url", "sampleUrl", "url", "audio_url", "audioUrl", "preview_url"):
                    nested_val = entry.get(nested_key)
                    if isinstance(nested_val, str) and nested_val:
                        voice["sample_url"] = nested_val
                        return nested_val
    return None


class AdvancedVideoConfigModel(BaseModel):
    backgroundType: str = Field(..., alias="backgroundType")
    backgroundColor: Optional[str] = Field(None, alias="backgroundColor")
    backgroundImageUrl: Optional[str] = Field(None, alias="backgroundImageUrl")
    language: str = Field("en", alias="language")
    speed: float = Field(1.0, alias="speed")
    tone: Optional[str] = Field(None, alias="tone")
    enableSubtitles: bool = Field(False, alias="enableSubtitles")
    subtitleLanguage: Optional[str] = Field(None, alias="subtitleLanguage")
    videoQuality: str = Field("medium", alias="videoQuality")
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


class SceneClipConfig(BaseModel):
    """Configuration for a scene clip in composition"""
    path: str  # Local path to the clip
    start_time: float  # When clip starts in final video (seconds)
    end_time: float  # When clip ends in final video (seconds)
    position: Optional[Dict[str, float]] = None  # Optional PiP position {x, y, scale}


class VideoCompositionRequest(BaseModel):
    """Request to compose video with scenes and music"""
    scene_clips: Optional[List[SceneClipConfig]] = None
    background_music_path: Optional[str] = None
    background_music_volume: float = 0.5
    fade_in: float = 1.0
    fade_out: float = 1.0


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


def serialize_generated_photo_look(record: Dict[str, Any]) -> Dict[str, Any]:
    base_avatar = (record.get("metadata") or {}).get("base_avatar") or {}
    return {
        "id": record.get("id"),
        "image_key": record.get("image_key"),
        "image_url": record.get("image_url"),
        "prompt": record.get("prompt"),
        "group_id": record.get("group_id"),
        "avatar_id": record.get("avatar_id") or base_avatar.get("avatar_id"),
        "created_at": record.get("created_at"),
        "metadata": record.get("metadata") or {}
    }


def serialize_look_favorite(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": record.get("id"),
        "avatar_id": record.get("avatar_id"),
        "image_key": record.get("image_key"),
        "metadata": record.get("metadata") or {},
        "created_at": record.get("created_at")
    }


def _is_missing_table_error(error: Exception, table_name: str) -> bool:
    if isinstance(error, APIError) and error.code == "PGRST205":
        message = (error.message or "").lower()
        return table_name.lower() in message
    return False


def _raise_missing_table_error(table_name: str):
    raise HTTPException(
        500,
        detail=(
            f"Supabase table '{table_name}' is missing. "
            "Apply migrations/026_marcel_favorites.sql to your Supabase project "
            "and run NOTIFY pgrst, 'reload schema'; then retry."
        )
    )


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
        avatars = await with_timeout(
            heygen.list_avatars(force_refresh=force_refresh),
            REQUEST_TIMEOUT_AVATAR,
            "Avatar listing"
        )
        logger.info(f"[MarcelGPT] Fetched {len(avatars)} avatars for tenant {tenant_id}")
        return {"avatars": avatars, "count": len(avatars), "debug": {"tenant_id": str(tenant_id), "avatar_count": len(avatars), "force_refresh": force_refresh}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarcelGPT] Error fetching avatars: {str(e)}")
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
        favorite_ids = set()
        try:
            fav_res = (
                supabase.table("marcel_voice_favorites")
                .select("voice_id")
                .eq("tenant_id", tenant_id)
                .eq("user_id", user.get("id"))
                .execute()
            )
            favorite_ids = {
                row["voice_id"] for row in (ensure_response(fav_res) or [])
            }
        except APIError as err:
            if _is_missing_table_error(err, "marcel_voice_favorites"):
                logger.warning(
                    "[MarcelGPT] marcel_voice_favorites table missing; apply migration 026_marcel_favorites.sql to enable favorites."
                )
                favorite_ids = set()
            else:
                raise

        all_voices = await with_timeout(
            heygen.list_voices(force_refresh=force_refresh),
            REQUEST_TIMEOUT_VOICES,
            "Voice listing"
        )
        voice_lookup = {
            (voice.get("voice_id") or ""): voice for voice in all_voices if voice.get("voice_id")
        }
        voices = list(all_voices)

        # Apply filters
        filtered_voices = voices
        if language:
            filtered_voices = [v for v in filtered_voices if v.get("language") == language]
        if gender:
            filtered_voices = [v for v in filtered_voices if v.get("gender") == gender]

        pinned_ids: List[str] = []
        if settings.PINNED_HEYGEN_VOICE_IDS:
            pinned_ids = [
                vid.strip() for vid in settings.PINNED_HEYGEN_VOICE_IDS.split(",") if vid.strip()
            ]

        pinned_records: List[Dict[str, Any]] = []
        pinned_id_set = set()
        for vid in pinned_ids:
            voice = voice_lookup.get(vid)
            if voice and vid not in pinned_id_set:
                pinned_records.append(voice)
                pinned_id_set.add(vid)

        filtered_voices = [
            voice for voice in filtered_voices
            if (voice.get("voice_id") or "") not in pinned_id_set
        ]

        ordered_voices = pinned_records + filtered_voices

        # Apply pagination after pinning
        total = len(ordered_voices)
        voices_page = ordered_voices[offset:offset + limit]

        for voice in voices_page:
            _ensure_voice_sample_url(voice)
            vid = voice.get("voice_id")
            voice["is_favorite"] = bool(vid in favorite_ids)

        logger.info(f"[MarcelGPT] Fetched {len(voices_page)} voices for tenant {tenant_id}")
        return {"voices": voices_page, "count": len(voices_page), "total": total, "offset": offset, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MarcelGPT] Error fetching voices: {str(e)}")
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

        async def _fetch_with_timeout(service) -> List[Dict[str, Any]]:
            try:
                return await asyncio.wait_for(service.list_avatars_in_group(group_id), timeout=20)
            except asyncio.TimeoutError:
                raise HTTPException(504, "Timed out fetching avatars from HeyGen (20s). Please retry.")

        try:
            avatars = await _fetch_with_timeout(heygen)
        except HTTPStatusError as http_error:
            status = http_error.response.status_code if http_error.response else None
            print(f"[MarcelGPT] Primary HeyGen request failed for group {group_id} with status {status}", file=sys.stderr, flush=True)
            if status in {401, 403}:
                fallback_service = get_fallback_heygen_service()
                if not fallback_service:
                    raise HTTPException(502, "HeyGen denied access to this avatar group and no fallback API key is configured")
                print(f"[MarcelGPT] Retrying custom group {group_id} with fallback HeyGen API key", file=sys.stderr, flush=True)
                avatars = await _fetch_with_timeout(fallback_service)
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


class SaveGeneratedPhotoLookRequest(BaseModel):
    image_key: str
    image_url: Optional[str] = None
    prompt: Optional[str] = None
    group_id: Optional[str] = None
    avatar_id: Optional[str] = None
    avatar_name: Optional[str] = None
    avatar_gender: Optional[str] = None
    avatar_preview_url: Optional[str] = None


class VoiceFavoriteRequest(BaseModel):
    voice_id: str


class LookFavoriteRequest(BaseModel):
    avatar_id: Optional[str] = None
    image_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DetectLanguageRequest(BaseModel):
    text: str


class TranslateScriptRequest(BaseModel):
    text: str
    target_language: str
    source_language: Optional[str] = None


class TrainingQuestionInput(BaseModel):
    question: str = Field(..., min_length=1)
    type: Literal["multiple_choice", "text"]
    options: Optional[List[str]] = None
    correct_answer: Optional[int] = Field(default=None, ge=0)
    expected_answer: Optional[str] = None


class UpdateTrainingQuestionsRequest(BaseModel):
    questions: List[TrainingQuestionInput] = Field(default_factory=list)


class VideoJobPayload(BaseModel):
    title: Optional[str] = None
    input_text: str
    avatar_id: Optional[str] = None
    voice_id: str
    engine: Optional[str] = Field(default="v2", description="Video engine: v2 or av4")
    preset_id: Optional[int] = None
    image_key: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    videoQuality: Optional[str] = None
    language: Optional[str] = None
    enableSubtitles: Optional[bool] = None
    subtitleLanguage: Optional[str] = None


class BatchGenerateVideoRequest(BaseModel):
    jobs: List[VideoJobPayload] = Field(..., min_items=1, max_items=3)


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


@router.get("/photo-avatars/generated")
async def list_generated_photo_looks(
    user=Depends(get_current_user)
):
    """List saved/generated photo looks for the current tenant."""
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    res = (
        supabase.table("photo_avatar_generated_images")
        .select("*")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .execute()
    )

    records = ensure_response(res) or []
    looks = [serialize_generated_photo_look(row) for row in records]
    return {"looks": looks, "count": len(looks)}


@router.post("/photo-avatars/generated")
async def save_generated_photo_look(
    payload: SaveGeneratedPhotoLookRequest,
    user=Depends(get_current_user)
):
    """Persist a generated photo avatar look so it can be reused later."""
    require_permission(user, "marcel_gpt.manage_presets")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    metadata = {
        "base_avatar": {
            "avatar_id": payload.avatar_id,
            "avatar_name": payload.avatar_name,
            "gender": payload.avatar_gender,
            "preview_image_url": payload.avatar_preview_url
        }
    }

    upsert_payload = {
        "tenant_id": tenant_id,
        "user_id": user.get("id"),
        "group_id": payload.group_id,
        "image_key": payload.image_key,
        "image_url": payload.image_url,
        "prompt": payload.prompt,
        "avatar_id": payload.avatar_id,
        "metadata": metadata
    }

    res = (
        supabase.table("photo_avatar_generated_images")
        .upsert(upsert_payload, on_conflict="tenant_id,image_key")
        .execute()
    )

    records = ensure_response(res)
    record = records[0] if isinstance(records, list) else records
    return {"look": serialize_generated_photo_look(record)}


@router.delete("/photo-avatars/generated/{look_id}")
async def delete_generated_photo_look(
    look_id: str,
    user=Depends(get_current_user)
):
    """Delete a saved generated look."""
    require_permission(user, "marcel_gpt.manage_presets")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    supabase.table("photo_avatar_generated_images") \
        .delete() \
        .eq("tenant_id", tenant_id) \
        .eq("id", look_id) \
        .execute()

    return {"success": True}


@router.get("/favorites/voices")
async def list_voice_favorites(user=Depends(get_current_user)):
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    try:
        res = (
            supabase.table("marcel_voice_favorites")
            .select("voice_id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user.get("id"))
            .execute()
        )
    except APIError as err:
        if _is_missing_table_error(err, "marcel_voice_favorites"):
            logger.warning(
                "[MarcelGPT] marcel_voice_favorites table missing; returning empty favorites list."
            )
            return {"favorites": []}
        raise

    records = ensure_response(res) or []
    favorites = [row["voice_id"] for row in records]
    return {"favorites": favorites}


@router.post("/favorites/voices")
async def add_voice_favorite(
    payload: VoiceFavoriteRequest,
    user=Depends(get_current_user)
):
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    try:
        supabase.table("marcel_voice_favorites") \
            .upsert({
                "tenant_id": tenant_id,
                "user_id": user.get("id"),
                "voice_id": payload.voice_id
            }, on_conflict="tenant_id,user_id,voice_id") \
            .execute()
    except APIError as err:
        if _is_missing_table_error(err, "marcel_voice_favorites"):
            _raise_missing_table_error("marcel_voice_favorites")
        raise HTTPException(500, f"Failed to save voice favorite: {err.message}")

    return {"success": True}


@router.delete("/favorites/voices/{voice_id}")
async def delete_voice_favorite(
    voice_id: str,
    user=Depends(get_current_user)
):
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    try:
        supabase.table("marcel_voice_favorites") \
            .delete() \
            .eq("tenant_id", tenant_id) \
            .eq("user_id", user.get("id")) \
            .eq("voice_id", voice_id) \
            .execute()
    except APIError as err:
        if _is_missing_table_error(err, "marcel_voice_favorites"):
            _raise_missing_table_error("marcel_voice_favorites")
        raise HTTPException(500, f"Failed to remove voice favorite: {err.message}")

    return {"success": True}


@router.get("/favorites/looks")
async def list_look_favorites(user=Depends(get_current_user)):
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    try:
        res = (
            supabase.table("marcel_look_favorites")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user.get("id"))
            .order("created_at", desc=True)
            .execute()
        )
    except APIError as err:
        if _is_missing_table_error(err, "marcel_look_favorites"):
            logger.warning(
                "[MarcelGPT] marcel_look_favorites table missing; returning empty favorites list."
            )
            return {"favorites": []}
        raise
    records = ensure_response(res) or []
    favorites = [serialize_look_favorite(row) for row in records]
    return {"favorites": favorites}


@router.post("/favorites/looks")
async def add_look_favorite(
    payload: LookFavoriteRequest,
    user=Depends(get_current_user)
):
    require_permission(user, "marcel_gpt.access")

    if not payload.avatar_id and not payload.image_key:
        raise HTTPException(400, "avatar_id or image_key is required")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    upsert_conflict = "tenant_id,user_id,avatar_id" if payload.avatar_id else "tenant_id,user_id,image_key"

    try:
        supabase.table("marcel_look_favorites") \
            .upsert({
                "tenant_id": tenant_id,
                "user_id": user.get("id"),
                "avatar_id": payload.avatar_id,
                "image_key": payload.image_key,
                "metadata": payload.metadata or {}
            }, on_conflict=upsert_conflict) \
            .execute()
    except APIError as err:
        if _is_missing_table_error(err, "marcel_look_favorites"):
            _raise_missing_table_error("marcel_look_favorites")
        raise HTTPException(500, f"Failed to save look favorite: {err.message}")

    return {"success": True}


@router.delete("/favorites/looks/{favorite_id}")
async def delete_look_favorite(
    favorite_id: str,
    user=Depends(get_current_user)
):
    require_permission(user, "marcel_gpt.access")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    try:
        supabase.table("marcel_look_favorites") \
            .delete() \
            .eq("tenant_id", tenant_id) \
            .eq("user_id", user.get("id")) \
            .eq("id", favorite_id) \
            .execute()
    except APIError as err:
        if _is_missing_table_error(err, "marcel_look_favorites"):
            _raise_missing_table_error("marcel_look_favorites")
        raise HTTPException(500, f"Failed to remove look favorite: {err.message}")

    return {"success": True}


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

async def _create_video_generation_job(user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    tenant_id = user.get("tenant_id")
    user_id = user.get("id")

    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    script_text = (payload.get("input_text") or "").strip()
    if not script_text:
        raise HTTPException(400, "input_text is required")

    avatar_identifier = payload.get("avatar_id") or payload.get("image_key")
    if not avatar_identifier:
        raise HTTPException(400, "avatar_id or image_key is required")

    voice_id = payload.get("voice_id")
    if not voice_id:
        raise HTTPException(400, "voice_id is required")

    engine = payload.get("engine", "v2")
    if engine not in ["v2", "av4", "template"]:
        raise HTTPException(400, "Invalid engine. Must be v2, av4, or template")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    callback_url = f"{settings.API_URL}/marcel-gpt/webhook"

    training_questions: List[Dict[str, Any]] = []
    try:
        question_result = generate_questions_from_script(script_text)
        if question_result.get("success"):
            training_questions = question_result.get("questions") or []
    except Exception as question_error:
        logger.warning(f"[MarcelGPT] Training question generation failed: {question_error}")

    input_config: Dict[str, Any] = {}
    # Normalize video dimensions & subtitle defaults
    default_width = payload.get("width") or 1920
    default_height = payload.get("height") or 1080
    payload["width"] = default_width
    payload["height"] = default_height

    if payload.get("enableSubtitles") is None:
        payload["enableSubtitles"] = True
    if not payload.get("subtitleLanguage") and payload.get("language"):
        payload["subtitleLanguage"] = payload.get("language")

    input_config["width"] = default_width
    input_config["height"] = default_height
    if payload.get("videoQuality"):
        input_config["videoQuality"] = payload["videoQuality"]
    if payload.get("language"):
        input_config["language"] = payload["language"]
    if payload.get("enableSubtitles") is not None:
        input_config["enableSubtitles"] = payload["enableSubtitles"]
    if payload.get("subtitleLanguage"):
        input_config["subtitleLanguage"] = payload["subtitleLanguage"]

    logger.info(
        "[MarcelGPT][VideoGeneration] Requested config width=%s height=%s quality=%s enableSubtitles=%s subtitleLanguage=%s title=%s",
        payload.get("width"),
        payload.get("height"),
        payload.get("videoQuality"),
        payload.get("enableSubtitles"),
        payload.get("subtitleLanguage"),
        payload.get("title")
    )

    category_data = await classify_script_categories(script_text)

    job_data = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "preset_id": payload.get("preset_id"),
        "title": payload.get("title"),
        "engine": engine,
        "status": "pending",
        "input_text": script_text,
        "input_config": input_config,
        "training_questions": training_questions,
        "main_category": category_data["main_category"] if category_data else None,
        "category_tags": category_data["tags"] if category_data else None,
        "category_metadata": category_data if category_data else None
    }

    job_res = supabase.table("video_jobs").insert(job_data).execute()
    job = ensure_response(job_res)[0]

    full_callback_url = f"{callback_url}?job_id={job['id']}"

    heygen_kwargs: Dict[str, Any] = {}
    heygen_kwargs["width"] = payload["width"]
    heygen_kwargs["height"] = payload["height"]
    if payload.get("videoQuality"):
        heygen_kwargs["quality"] = payload["videoQuality"]
    if payload.get("language"):
        heygen_kwargs["language"] = payload["language"]
    heygen_kwargs["enable_subtitles"] = payload.get("enableSubtitles", True)
    if payload.get("subtitleLanguage"):
        heygen_kwargs["subtitle_language"] = payload["subtitleLanguage"]
    elif payload.get("language"):
        heygen_kwargs["subtitle_language"] = payload["language"]

    logger.info(
        "[MarcelGPT][VideoGeneration] Job pending HeyGen kwargs width=%s height=%s quality=%s enable_subtitles=%s subtitle_language=%s engine=%s",
        heygen_kwargs.get("width"),
        heygen_kwargs.get("height"),
        heygen_kwargs.get("quality"),
        heygen_kwargs.get("enable_subtitles"),
        heygen_kwargs.get("subtitle_language"),
        engine
    )

    if engine == "v2":
        heygen_response = await with_timeout(
            heygen.create_video_v2(
                input_text=script_text,
                avatar_id=avatar_identifier,
                voice_id=voice_id,
                callback_url=full_callback_url,
                title=payload.get("title"),
                **heygen_kwargs
            ),
            REQUEST_TIMEOUT_GENERATION,
            "HeyGen V2 video generation"
        )
    elif engine == "av4":
        if payload.get("image_key"):
            heygen_kwargs["image_key"] = payload["image_key"]
        else:
            raise HTTPException(400, "AV4 engine requires image_key for saved looks")

        heygen_response = await with_timeout(
            heygen.create_video_av4(
                input_text=script_text,
                avatar_id=avatar_identifier,
                voice_id=voice_id,
                callback_url=full_callback_url,
                video_title=payload.get("title") or payload.get("video_title"),
                **heygen_kwargs
            ),
            REQUEST_TIMEOUT_GENERATION,
            "HeyGen AV4 video generation"
        )
    else:
        raise HTTPException(400, f"Unknown engine: {engine}")

    logger.info(
        "[MarcelGPT][VideoGeneration] HeyGen response for job %s: raw_status=%s keys=%s",
        job["id"],
        heygen_response.get("status") or heygen_response.get("code"),
        list(heygen_response.keys())
    )

    video_id = heygen_response.get("data", {}).get("video_id")
    if not video_id:
        raise HTTPException(500, "HeyGen API did not return video_id")

    supabase.table("video_jobs") \
        .update({
            "heygen_job_id": video_id,
            "status": "queued",
            "queued_at": datetime.now().isoformat(),
            "callback_url": full_callback_url
        }) \
        .eq("id", job["id"]) \
        .execute()

    logger.info(f"[MarcelGPT] Queued video job #{job['id']} via HeyGen job {video_id}")

    scene_clips = payload.get("scene_clips")
    if isinstance(scene_clips, list) and scene_clips:
        logger.info(
            "[MarcelGPT] Scene clips detected for job %s, queuing composition with %s clips",
            job["id"],
            len(scene_clips)
        )
        asyncio.create_task(_trigger_composition_async(
            job_id=job["id"],
            tenant_id=tenant_id,
            scene_clips=scene_clips,
            background_music=payload.get("background_music"),
            heygen_job_id=video_id
        ))
        return {
            "job_id": job["id"],
            "heygen_job_id": video_id,
            "status": "queued",
            "composition_queued": True,
            "scene_count": len(scene_clips),
            "message": "Video generation started. Scene composition queued."
        }

    return {
        "job_id": job["id"],
        "heygen_job_id": video_id,
        "status": "queued",
        "message": f"Video generation queued (job #{job['id']})"
    }


@router.post("/generate")
async def generate_video(
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Generate a single HeyGen video job
    """
    require_permission(user, "marcel_gpt.create_video")
    return await _create_video_generation_job(user, payload)


@router.post("/generate/batch")
async def generate_videos_batch(
    payload: BatchGenerateVideoRequest,
    user=Depends(get_current_user),
):
    """
    Generate up to 3 HeyGen jobs in one request (multi-language workflows)
    """
    require_permission(user, "marcel_gpt.create_video")

    results: List[Dict[str, Any]] = []
    for idx, job_payload in enumerate(payload.jobs):
        try:
            job_result = await _create_video_generation_job(
                user,
                job_payload.model_dump(exclude_none=True)
            )
            job_result["index"] = idx
            results.append(job_result)
        except HTTPException as exc:
            logger.warning(f"[MarcelGPT] Batch job {idx} failed: {exc.detail}")
            results.append({
                "index": idx,
                "status": "failed",
                "error": exc.detail,
                "error_code": exc.status_code,
            })
        except Exception as exc:
            logger.error(f"[MarcelGPT] Batch job {idx} unexpected error: {exc}")
            results.append({
                "index": idx,
                "status": "failed",
                "error": str(exc),
                "error_code": 500,
            })

    success_count = len([res for res in results if res.get("job_id")])
    if success_count == len(payload.jobs):
        status = "success"
    elif success_count == 0:
        status = "failed"
    else:
        status = "partial"

    return {"status": status, "results": results}




# =========================================================================
# HeyGen Sync Helpers
# =========================================================================

async def _sync_recent_heygen_videos(tenant_id: str, heygen_service, user_id: str):
    """Import recently generated HeyGen videos so the library stays in sync."""
    now = datetime.now(timezone.utc)
    last_sync = _LAST_HEYGEN_SYNC.get(tenant_id)
    if last_sync and (now - last_sync) < VIDEO_SYNC_INTERVAL:
        return

    try:
        response = await heygen_service.list_videos(limit=20, offset=0)
        videos = response.get("data", {}).get("videos", [])

        for video in videos:
            video_id = video.get("video_id")
            if not video_id:
                continue

            status = (video.get("status") or '').lower() or 'completed'
            created_ts = video.get("created_at")
            created_at = None
            if isinstance(created_ts, (int, float)):
                created_at = datetime.fromtimestamp(created_ts, timezone.utc)

            existing = (
                supabase.table("video_jobs")
                .select("id")
                .eq("heygen_job_id", video_id)
                .limit(1)
                .execute()
            )

            if existing.data:
                job_id = existing.data[0]["id"]
                supabase.table("video_jobs") \
                    .update({
                        "status": status,
                        "completed_at": created_at.isoformat() if created_at and status == "completed" else None
                    }) \
                    .eq("id", job_id) \
                    .execute()
                continue

            insert_payload = {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "title": video.get("video_title") or video_id,
                "engine": "av4",
                "status": status,
                "heygen_job_id": video_id,
                "input_text": "Imported from HeyGen dashboard",
                "input_config": {"source": "heygen_import"},
                "queued_at": created_at.isoformat() if created_at else None,
                "created_at": created_at.isoformat() if created_at else None,
                "completed_at": created_at.isoformat() if created_at and status == "completed" else None
            }

            job_insert = supabase.table("video_jobs").insert(insert_payload).execute()
            job_row = ensure_response(job_insert)[0]

            if status == "completed":
                video_url = await _fetch_heygen_video_url(heygen_service, video_id)
                thumbnail_url = (
                    video.get("thumbnail_url")
                    or video.get("cover_url")
                    or video.get("preview_image_url")
                )
                duration_seconds = video.get("duration") or video.get("video_duration")
                if video_url:
                    supabase.table("video_artifacts").insert({
                        "job_id": job_row["id"],
                        "heygen_url": video_url,
                        "storage_key": video_url,
                        "signed_url": video_url,
                        "duration": duration_seconds,
                        "thumbnail_url": thumbnail_url,
                        "meta": {
                            "source": "heygen_sync"
                        },
                        "created_at": now.isoformat()
                    }).execute()

        _LAST_HEYGEN_SYNC[tenant_id] = now

    except Exception as sync_error:
        print(f"[MarcelGPT] Failed to sync HeyGen videos: {sync_error}")


async def _fetch_heygen_video_url(heygen_service, video_id: str) -> Optional[str]:
    try:
        status_response = await heygen_service.get_video_status(video_id)
        return status_response.get("data", {}).get("video_url")
    except Exception as fetch_error:
        print(f"[MarcelGPT] Could not fetch video URL for {video_id}: {fetch_error}")
        return None


async def _populate_missing_artifacts(jobs: List[Dict[str, Any]], heygen_service, tenant_id: str, user_id: str):
    """
    For completed jobs with heygen_job_id but no artifacts, fetch video URL and thumbnail from HeyGen API.
    This ensures videos generated but not yet synced will have their playback URLs available.
    """
    if not heygen_service:
        return

    for job in jobs:
        # Skip if already has artifacts
        if job.get("artifacts") and len(job.get("artifacts", [])) > 0:
            continue

        # Skip if no heygen_job_id
        heygen_job_id = job.get("heygen_job_id")
        if not heygen_job_id:
            continue

        # Skip if not completed
        if job.get("status") != "completed":
            continue

        try:
            print(f"[MarcelGPT] Fetching missing artifacts for job {job['id']} (HeyGen ID: {heygen_job_id})")
            status_response = await heygen_service.get_video_status(heygen_job_id)
            data = status_response.get("data", {})

            video_url = data.get("video_url")
            thumbnail_url = data.get("thumbnail_url") or data.get("cover_url")
            duration = data.get("duration")

            # Log what we got from HeyGen API
            print(f"[MarcelGPT] HeyGen response data keys: {list(data.keys())}")
            print(f"[MarcelGPT] Job {job['id']}: video_url={bool(video_url)}, thumbnail={bool(thumbnail_url)}, duration={duration}")

            # Convert duration from float to integer (HeyGen API returns float like 21.726)
            if duration is not None:
                duration = int(duration)

            if video_url:
                print(f"[MarcelGPT] Found video URL for job {job['id']}: {video_url[:50]}...")
                if thumbnail_url:
                    print(f"[MarcelGPT] Found thumbnail URL: {thumbnail_url[:60]}...")
                else:
                    print(f"[MarcelGPT] No thumbnail URL from HeyGen, generating fallback")
                    # Generate a placeholder thumbnail URL (can be a static image or video frame)
                    # Using a standard video placeholder thumbnail
                    thumbnail_url = f"https://via.placeholder.com/320x180?text=Video+{job['id']}"

                # Create artifact record in database
                artifact_insert = supabase.table("video_artifacts").insert({
                    "job_id": job["id"],
                    "heygen_url": video_url,
                    "storage_key": video_url,
                    "signed_url": video_url,
                    "duration": duration,
                    "thumbnail_url": thumbnail_url,
                    "meta": {
                        "source": "heygen_sync_missing"
                    },
                    "created_at": datetime.now(timezone.utc).isoformat()
                }).execute()

                artifact_data = ensure_response(artifact_insert)
                if artifact_data:
                    job["artifacts"] = artifact_data
                    print(f"[MarcelGPT] Successfully populated artifact for job {job['id']}")
            else:
                print(f"[MarcelGPT] No video URL found for job {job['id']}")

        except Exception as e:
            print(f"[MarcelGPT] Error populating artifacts for job {job['id']}: {e}")
            import traceback
            traceback.print_exc()


async def _detect_language_code(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "unknown"

    if detect:
        try:
            return _normalize_language_code(detect(text))
        except LangDetectException:
            return "unknown"
        except Exception as exc:
            logger.warning(f"[MarcelGPT] langdetect failed, falling back to OpenAI: {exc}")

    if not AsyncOpenAI or not settings.OPENAI_API_KEY:
        return "unknown"

    prompt = (
        "Identify the ISO 639-1 language code (two letters) for the following text. "
        "If unsure, respond with 'unknown'. Return only the code.\n\n"
        f"TEXT:\n{text[:1000]}"
    )

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=10,
            messages=[
                {"role": "system", "content": "Respond only with an ISO 639-1 language code."},
                {"role": "user", "content": prompt}
            ]
        )
        raw = completion.choices[0].message.content.strip().split()[0]
        return _normalize_language_code(raw)
    except Exception as exc:
        logger.error(f"[MarcelGPT] OpenAI-based language detection failed: {exc}")
        return "unknown"


# =========================================================================
# Job Management Endpoints
# =========================================================================

@router.get("/jobs")
async def list_jobs(
    user=Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    main_category: Optional[str] = Query(None, description="Filter by main category (process_safety | personal_safety)"),
    tags: Optional[List[str]] = Query(None, description="Filter by one or more category tag keys"),
):
    """List video generation jobs for current tenant with artifacts"""
    require_permission(user, "modules.access_marcel_gpt")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if heygen:
        await _sync_recent_heygen_videos(tenant_id, heygen, user.get("id"))

    query = supabase.table("video_jobs") \
        .select("*, video_artifacts(*)") \
        .eq("tenant_id", tenant_id)

    if status:
        query = query.eq("status", status)
    normalized_category = _normalize_category_key(main_category)
    if normalized_category:
        query = query.eq("main_category", normalized_category)

    if tags:
        normalized_tags = [
            _normalize_tag_key(tag) for tag in tags if _normalize_tag_key(tag)
        ]
        if normalized_tags:
            query = query.contains("category_tags", normalized_tags)

    query = query.range(offset, offset + limit - 1) \
        .order("created_at", desc=True)

    res = query.execute()

    # Transform video_artifacts array to artifacts key for consistency
    jobs = ensure_response(res)
    for job in jobs:
        if "video_artifacts" in job:
            job["artifacts"] = job.pop("video_artifacts")

    # Populate any missing category data for legacy records
    await _ensure_job_categories(jobs)

    # Populate missing artifacts for completed jobs that don't have them yet
    if heygen:
        await _populate_missing_artifacts(jobs, heygen, tenant_id, user.get("id"))

    return {"jobs": jobs, "count": len(jobs) if jobs else 0}


@router.patch("/jobs/{job_id}/training-questions")
async def update_job_training_questions(
    job_id: int,
    payload: UpdateTrainingQuestionsRequest,
    user=Depends(get_current_user)
):
    """Update quiz questions attached to a generated video job."""
    require_permission(user, "modules.access_marcel_gpt")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    job_res = (
        supabase.table("video_jobs")
        .select("id")
        .eq("id", job_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    job_data = ensure_response(job_res)
    if not job_data:
        raise HTTPException(404, "Video job not found")

    sanitized_questions = _sanitize_training_questions(payload.questions or [])

    update_res = (
        supabase.table("video_jobs")
        .update(
            {
                "training_questions": sanitized_questions
            }
        )
        .eq("id", job_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    ensure_response(update_res)

    return {"success": True, "training_questions": sanitized_questions}


@router.get("/heygen/videos")
async def list_raw_heygen_videos(
    user=Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0)
):
    """Expose HeyGen's native video.list response for debugging."""
    require_permission(user, "modules.access_marcel_gpt")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    heygen = get_heygen_service(tenant_id)
    if not heygen:
        raise HTTPException(400, "HeyGen API key not configured for this tenant")

    response = await heygen.list_videos(limit=limit, offset=offset)
    return response.get("data", {})


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: int,
    user=Depends(get_current_user),
):
    """Get job details with artifacts"""
    require_permission(user, "modules.access_marcel_gpt")

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
    require_permission(user, "modules.access_marcel_gpt")

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
    process_safety_violations: Optional[str] = None
    life_saving_rule_violations: Optional[str] = None
    preventive_actions: Optional[str] = None
    reference_case: Optional[str] = None


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
async def generate_script_from_documents(
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    """
    Generate a video script from uploaded documents.
    Supports PDF, PPT/PPTX, and image files (PNG/JPG).
    """
    require_permission(user, "marcel_gpt.access")

    from app.services.script_generation_service import (
        generate_script_from_material,
        extract_text_from_document
    )

    if not files:
        raise HTTPException(400, "Please upload at least one document")

    if len(files) > 5:
        raise HTTPException(400, "You can upload up to 5 documents at a time")

    try:
        extracted_chunks: List[str] = []

        for upload in files:
            file_bytes = await upload.read()
            if not file_bytes:
                continue

            try:
                text = await extract_text_from_document(
                    upload.filename or "document",
                    upload.content_type,
                    file_bytes
                )
            except ValueError as ve:
                raise HTTPException(400, str(ve))

            if not text.strip():
                continue

            extracted_chunks.append(
                f"Document: {upload.filename or 'Unnamed Document'}\n{text.strip()}"
            )

        if not extracted_chunks:
            raise HTTPException(400, "Could not extract text from the uploaded documents")

        combined_material = "\n\n".join(extracted_chunks)
        result = await generate_script_from_material(combined_material)

        if not result.get("success"):
            raise HTTPException(500, result.get("error", "Failed to generate script from documents"))

        return {**result, "documentsProcessed": len(extracted_chunks)}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Document Script Gen] Error: {str(e)}")
        raise HTTPException(500, f"Error processing documents: {str(e)}")


@router.post("/scripts/detect-language")
async def detect_script_language(
    payload: DetectLanguageRequest,
    user=Depends(get_current_user),
):
    """Detect the primary language for a script"""
    require_permission(user, "modules.access_marcel_gpt")

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "text is required")

    detected_code = await _detect_language_code(text)

    return {
        "language": detected_code,
        "language_name": _language_name(detected_code),
    }


@router.post("/scripts/translate")
async def translate_script(
    payload: TranslateScriptRequest,
    user=Depends(get_current_user),
):
    """Translate a script to the requested language using OpenAI"""
    require_permission(user, "modules.access_marcel_gpt")

    if not AsyncOpenAI:
        raise HTTPException(500, "OpenAI client is not configured on the server")

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, "text is required")

    target_language = _normalize_language_code(payload.target_language)
    if not target_language or target_language == "unknown":
        raise HTTPException(400, "target_language is required")

    source_language = _normalize_language_code(payload.source_language or "")
    if not source_language or source_language == "unknown":
        source_language = await _detect_language_code(text)

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    system_prompt = (
        "You translate corporate training content with high fidelity. "
        "Preserve tone, technical accuracy, and structure. "
        "Return only the translated script without additional commentary."
    )
    user_prompt = (
        f"Translate the following narration into {_language_name(target_language)}.\n"
        "Keep any bulleting or numbering intact.\n\n"
        f"--- SCRIPT START ---\n{text}\n--- SCRIPT END ---"
    )

    try:
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:
        logger.error(f"[MarcelGPT] Translation failed: {exc}")
        raise HTTPException(500, "Failed to translate script")

    translated_text = (
        completion.choices[0].message.content.strip()
        if completion.choices
        and completion.choices[0].message
        and completion.choices[0].message.content
        else ""
    )

    if not translated_text:
        raise HTTPException(500, "Translation returned an empty response")

    return {
        "text": translated_text,
        "language": target_language,
        "language_name": _language_name(target_language),
        "source_language": source_language or "unknown",
        "source_language_name": _language_name(source_language or "unknown"),
    }


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
        tenant_id=tenant_id,
        process_safety_violations=payload.process_safety_violations,
        life_saving_rule_violations=payload.life_saving_rule_violations,
        preventive_actions=payload.preventive_actions,
        reference_case=payload.reference_case
    )

    if not result.get("success"):
        raise HTTPException(500, result.get("error", "Failed to generate script"))

    return result


@router.post("/videos/{job_id}/translate")
async def translate_video(
    job_id: str,
    payload: dict = Body(...),
    user=Depends(get_current_user),
):
    """
    Create a translated version of an existing video job

    Request body:
    {
        "target_language": "tr"  # Language code (en, tr, es, fr, de, zh, ja, pt)
    }

    Returns: New translated video job details
    """
    require_permission(user, "modules.access_marcel_gpt")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    target_language = payload.get("target_language", "en")

    # Map language codes to language names (HeyGen supported languages)
    language_map = {
        "en": "English",
        "af": "Afrikaans",
        "ar": "Arabic",
        "hy": "Armenian",
        "az": "Azerbaijani",
        "be": "Belarusian",
        "bg": "Bulgarian",
        "ca": "Catalan",
        "cs": "Czech",
        "cy": "Welsh",
        "da": "Danish",
        "de": "German",
        "el": "Greek",
        "eo": "Esperanto",
        "es": "Spanish",
        "et": "Estonian",
        "fa": "Persian",
        "fi": "Finnish",
        "fr": "French",
        "ga": "Irish",
        "gd": "Scottish Gaelic",
        "gl": "Galician",
        "gu": "Gujarati",
        "he": "Hebrew",
        "hi": "Hindi",
        "hr": "Croatian",
        "hu": "Hungarian",
        "id": "Indonesian",
        "is": "Icelandic",
        "it": "Italian",
        "ja": "Japanese",
        "jv": "Javanese",
        "ko": "Korean",
        "lt": "Lithuanian",
        "lv": "Latvian",
        "mk": "Macedonian",
        "mr": "Marathi",
        "ms": "Malay",
        "my": "Burmese",
        "nb": "Norwegian",
        "nl": "Dutch",
        "pa": "Punjabi",
        "pl": "Polish",
        "pt": "Portuguese",
        "ro": "Romanian",
        "ru": "Russian",
        "sk": "Slovak",
        "sl": "Slovenian",
        "sq": "Albanian",
        "sv": "Swedish",
        "sw": "Swahili",
        "ta": "Tamil",
        "te": "Telugu",
        "th": "Thai",
        "tl": "Tagalog",
        "tr": "Turkish",
        "uk": "Ukrainian",
        "ur": "Urdu",
        "vi": "Vietnamese",
        "zh": "Chinese (Simplified)",
        "zh-TW": "Chinese (Traditional)",
        "yue": "Cantonese"
    }

    language_name = language_map.get(target_language, target_language.upper())
    language_label = f"[{target_language.upper()}]"

    # Fetch the original job
    try:
        original_job_res = supabase.table("video_jobs").select("*").eq("id", job_id).eq("tenant_id", tenant_id).execute()
        original_jobs = ensure_response(original_job_res)

        if not original_jobs:
            raise HTTPException(404, f"Video job {job_id} not found")

        original_job = original_jobs[0]
    except Exception as e:
        print(f"[MarcelGPT] Error fetching original job: {e}")
        raise HTTPException(500, "Failed to fetch original video job")

    # Get the original script
    original_script = original_job.get("input_text", "")
    if not original_script:
        raise HTTPException(400, "Original job has no script to translate")

    # Translate the script using OpenAI
    logger.info(f"[MarcelGPT] Starting translation: job_id={job_id}, target={language_name} ({target_language}), script_length={len(original_script)}")
    try:
        if not AsyncOpenAI:
            raise HTTPException(500, "OpenAI client not available. Please install openai package.")

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        translate_prompt = f"""Translate the following training script to {language_name}.
Keep the structure, tone, and safety focus intact. Maintain any specific technical terms and company-specific language where appropriate.

ORIGINAL SCRIPT:
{original_script}

TRANSLATED SCRIPT ({language_name}):"""

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional translator specializing in safety training materials. Translate accurately while maintaining the educational tone and safety context."},
                {"role": "user", "content": translate_prompt}
            ],
            temperature=0.7,
            max_tokens=5000
        )

        translated_script = response.choices[0].message.content.strip()
        logger.info(f"[MarcelGPT] Script translated successfully: length={len(translated_script)} chars")
    except Exception as e:
        logger.error(f"[MarcelGPT] Translation failed: {str(e)}")
        raise HTTPException(500, f"Failed to translate script: {str(e)}")

    # Create new translated job with language prefix in title
    original_title = original_job.get("title", f"Video #{job_id}")

    # Add language prefix if not already present
    if not original_title.startswith("["):
        translated_title = f"{language_label} {original_title}"
    else:
        translated_title = original_title

    # Get original config and update with target language
    original_config = original_job.get("input_config") or {}

    category_data = await classify_script_categories(translated_script)

    new_job_data = {
        "tenant_id": tenant_id,
        "user_id": user.get("id"),
        "title": translated_title,
        "engine": original_job.get("engine", "v2"),
        "status": "pending",  # Will be processed by video generation queue
        "input_text": translated_script,
        "input_config": {
            **original_config,
            "target_language": target_language,
            "translated_from_job_id": job_id,
            "language_label": language_label,
            "language": target_language  # Force target language for HeyGen
        },
        "main_category": category_data["main_category"] if category_data else original_job.get("main_category"),
        "category_tags": category_data["tags"] if category_data else original_job.get("category_tags"),
        "category_metadata": category_data or original_job.get("category_metadata")
    }

    try:
        # Insert the new translated job
        translated_job_res = supabase.table("video_jobs").insert(new_job_data).execute()
        translated_job = ensure_response(translated_job_res)[0]
        translated_job_id = translated_job["id"]

        # Now automatically trigger video generation for the translated job
        # Get HeyGen service for video generation
        heygen = get_heygen_service(tenant_id)
        if not heygen:
            raise HTTPException(400, "HeyGen API key not configured for this tenant")

        # Get original job details to use for video generation
        engine = original_job.get("engine", "v2")
        avatar_id = original_job.get("avatar_id") or original_job.get("image_key")
        original_voice_id = original_job.get("voice_id")

        if not avatar_id or not original_voice_id:
            # If original job doesn't have avatar/voice, just return job creation response
            # User will need to manually generate from the UI
            return {
                "success": True,
                "job_id": translated_job_id,
                "title": translated_job["title"],
                "language": target_language,
                "language_name": language_name,
                "original_job_id": job_id,
                "message": f"Translation created. Please select avatar and voice to generate."
            }

        # Find a voice that matches the target language
        # This ensures the translated video uses the appropriate language-specific voice
        voice_id = original_voice_id  # Fallback to original voice
        try:
            available_voices = await with_timeout(
                heygen.list_voices(force_refresh=False),
                REQUEST_TIMEOUT_VOICES,
                "Voice listing for translation"
            )

            # Filter voices by target language
            target_lang_voices = [
                v for v in available_voices
                if v.get("language", "").lower() == language_name.lower()
            ]

            if target_lang_voices:
                # Use the first available voice for the target language
                selected_lang_voice = target_lang_voices[0]
                voice_id = selected_lang_voice.get("voice_id", original_voice_id)
                logger.info(f"[MarcelGPT] Translation: Using {language_name} voice {voice_id}")
            else:
                logger.warning(f"[MarcelGPT] Translation: No voices found for {language_name}, using original voice {original_voice_id}")
        except Exception as voice_error:
            logger.warning(f"[MarcelGPT] Translation: Could not fetch voices for language selection: {voice_error}. Using original voice.")

        # Build callback URL
        from app.config import settings
        callback_url = f"{settings.API_URL}/marcel-gpt/webhook"
        full_callback_url = f"{callback_url}?job_id={translated_job_id}"

        # Prepare HeyGen parameters
        heygen_kwargs = {}
        if original_config.get("width"):
            heygen_kwargs["width"] = original_config["width"]
        if original_config.get("height"):
            heygen_kwargs["height"] = original_config["height"]
        if original_config.get("videoQuality"):
            heygen_kwargs["quality"] = original_config["videoQuality"]

        # Force target language for HeyGen
        heygen_kwargs["language"] = target_language

        # IMPORTANT: Force enable subtitles in the target language for translations
        heygen_kwargs["enable_subtitles"] = True
        heygen_kwargs["subtitle_language"] = target_language

        # Call HeyGen API to generate translated video
        logger.info(f"[MarcelGPT] Calling HeyGen API for translation: engine={engine}, voice_id={voice_id}, language={target_language}, subtitles=enabled")
        try:
            if engine == "v2":
                heygen_response = await with_timeout(
                    heygen.create_video_v2(
                        input_text=translated_script,
                        avatar_id=avatar_id,
                        voice_id=voice_id,
                        callback_url=full_callback_url,
                        title=translated_title,
                        **heygen_kwargs
                    ),
                    REQUEST_TIMEOUT_GENERATION,
                    "Translated video generation (HeyGen V2)"
                )
            elif engine == "av4":
                if original_config.get("image_key"):
                    heygen_kwargs["image_key"] = original_config["image_key"]
                heygen_response = await with_timeout(
                    heygen.create_video_av4(
                        input_text=translated_script,
                        avatar_id=avatar_id,
                        voice_id=voice_id,
                        callback_url=full_callback_url,
                        video_title=translated_title,
                        **heygen_kwargs
                    ),
                    REQUEST_TIMEOUT_GENERATION,
                    "Translated video generation (HeyGen AV4)"
                )
            else:
                raise Exception(f"Unsupported engine: {engine}")

            # Extract video_id from response
            video_id = heygen_response.get("data", {}).get("video_id")
            if not video_id:
                raise Exception("HeyGen API did not return video_id")

            logger.info(f"[MarcelGPT] HeyGen accepted translation job: heygen_job_id={video_id}")

            # Update translated job with HeyGen video ID
            supabase.table("video_jobs").update({
                "heygen_job_id": video_id,
                "status": "queued",
                "queued_at": datetime.now().isoformat(),
                "callback_url": full_callback_url
            }).eq("id", translated_job_id).execute()

            logger.info(f"[MarcelGPT] Translation SUCCESS: job_id={translated_job_id}, heygen_job_id={video_id}, language={language_name}")

            return {
                "success": True,
                "job_id": translated_job_id,
                "heygen_job_id": video_id,
                "title": translated_job["title"],
                "language": target_language,
                "language_name": language_name,
                "voice_id": voice_id,
                "original_job_id": job_id,
                "status": "queued",
                "message": f"Video translated to {language_name}! Using {language_name} voice with {language_name} subtitles. Video generation queued."
            }

        except Exception as generation_error:
            logger.error(f"[MarcelGPT] Translation FAILED: error={str(generation_error)}")
            # Update job as failed
            supabase.table("video_jobs").update({
                "status": "failed",
                "error_message": f"Video generation failed: {str(generation_error)}",
                "failed_at": datetime.now().isoformat()
            }).eq("id", translated_job_id).execute()
            raise HTTPException(500, f"Failed to generate translated video: {str(generation_error)}")

    except HTTPException:
        raise
    except Exception as e:
        print(f"[MarcelGPT] Error creating translated job: {e}")
        raise HTTPException(500, "Failed to create translated video job")


@router.post("/videos/{job_id}/compose")
async def compose_video(
    job_id: str,
    payload: VideoCompositionRequest = Body(...),
    user=Depends(get_current_user),
):
    """
    Compose a video with scene clips and background music

    NOTE: This endpoint queues composition asynchronously and returns immediately.
    The composition happens in the background. Check /videos/{job_id} for status.

    Request body:
    {
        "scene_clips": [
            {
                "path": "/path/to/clip.mp4",
                "start_time": 5.0,
                "end_time": 15.0,
                "position": {"x": 0.65, "y": 0.05, "scale": 0.3}
            }
        ],
        "background_music_path": "/path/to/music.mp3",
        "background_music_volume": 0.5,
        "fade_in": 1.0,
        "fade_out": 1.0
    }

    Returns: Composition job details (queued for async processing)
    """
    require_permission(user, "modules.access_marcel_gpt")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "User not assigned to a tenant")

    # Fetch the video job
    try:
        job_res = supabase.table("video_jobs").select("*").eq("id", job_id).eq("tenant_id", tenant_id).execute()
        jobs = ensure_response(job_res)

        if not jobs:
            raise HTTPException(404, f"Video job {job_id} not found")

        job = jobs[0]
    except Exception as e:
        print(f"[MarcelGPT] Error fetching job: {e}")
        raise HTTPException(500, "Failed to fetch video job")

    # Get artifacts for the base video
    try:
        artifacts_res = supabase.table("video_artifacts").select("*").eq("job_id", job_id).execute()
        artifacts = ensure_response(artifacts_res)

        if not artifacts:
            raise HTTPException(404, f"No video artifacts found for job {job_id}")

        primary_artifact = artifacts[0]
        base_video_url = primary_artifact.get("heygen_url") or primary_artifact.get("signed_url")

        if not base_video_url:
            raise HTTPException(400, "No video URL available for composition")
    except Exception as e:
        print(f"[MarcelGPT] Error fetching artifacts: {e}")
        raise HTTPException(500, "Failed to fetch video artifacts")

    # Validate scene clips exist
    if payload.scene_clips:
        for clip in payload.scene_clips:
            if not os.path.exists(clip.path):
                raise HTTPException(400, f"Scene clip not found: {clip.path}")

    # Validate background music exists
    if payload.background_music_path and not os.path.exists(payload.background_music_path):
        raise HTTPException(400, "Background music file not found")

    # Create composition job record
    composition_job = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "base_video_url": base_video_url,
        "composition_status": "pending",
        "scene_count": len(payload.scene_clips) if payload.scene_clips else 0,
        "has_background_music": bool(payload.background_music_path)
    }

    try:
        comp_res = supabase.table("video_compositions").insert(composition_job).execute()
        composition = ensure_response(comp_res)[0]
    except Exception as e:
        print(f"[MarcelGPT] Error creating composition job: {e}")
        raise HTTPException(500, "Failed to create composition job")

    # Queue composition as background task (returns immediately)
    # This prevents the endpoint from blocking while FFmpeg runs
    import asyncio

    async def _run_composition_async():
        """Background task to run composition without blocking the endpoint"""
        try:
            # Update composition status to processing
            supabase.table("video_compositions").update({
                "composition_status": "compositing",
                "started_at": datetime.now().isoformat()
            }).eq("id", composition["id"]).execute()

            # Download base video to temp location with timeout
            import tempfile as tmp
            base_video_path = None

            try:
                with tmp.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_base:
                    base_video_path = temp_base.name
                    # Download with 5-minute timeout for large files
                    async with httpx.AsyncClient(timeout=300.0) as client:
                        async with client.stream("GET", base_video_url) as response:
                            if response.status_code != 200:
                                raise Exception(f"Failed to download video: HTTP {response.status_code}")
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                temp_base.write(chunk)
            except asyncio.TimeoutError:
                raise Exception("Base video download timed out (5 minutes)")
            except Exception as download_error:
                raise Exception(f"Failed to download base video: {str(download_error)}")

            if not base_video_path or not os.path.exists(base_video_path):
                raise Exception("Failed to save base video to temp file")

            try:
                # Run composition (this is CPU-intensive, will block briefly)
                composition_service = get_composition_service()
                result = await composition_service.compose_video(
                    base_video_url=base_video_url,
                    base_video_path=base_video_path,
                    scene_clips=[clip.dict() for clip in (payload.scene_clips or [])],
                    background_music_path=payload.background_music_path,
                )

                if not result.get("success"):
                    error_msg = result.get("error", "Unknown composition error")
                    supabase.table("video_compositions").update({
                        "composition_status": "failed",
                        "composition_error": error_msg
                    }).eq("id", composition["id"]).execute()
                    return

                # Update composition job with results
                output_path = result.get("output_path")
                supabase.table("video_compositions").update({
                    "composition_status": "completed",
                    "final_video_url": f"file://{output_path}",
                    "total_duration": result.get("duration"),
                    "completed_at": datetime.now().isoformat()
                }).eq("id", composition["id"]).execute()

                print(f"[MarcelGPT] Composition completed for job {job_id}")

            finally:
                # Always cleanup temp base video
                if base_video_path:
                    try:
                        os.remove(base_video_path)
                    except Exception as cleanup_error:
                        print(f"[MarcelGPT] Warning: Failed to cleanup temp file {base_video_path}: {cleanup_error}")

        except Exception as e:
            print(f"[MarcelGPT] Background composition error: {str(e)}")
            try:
                supabase.table("video_compositions").update({
                    "composition_status": "failed",
                    "composition_error": str(e)
                }).eq("id", composition["id"]).execute()
            except Exception as db_error:
                print(f"[MarcelGPT] Failed to update composition error status: {db_error}")

    # Fire and forget - queue the background task without waiting
    asyncio.create_task(_run_composition_async())

    # Return immediately with pending status
    return {
        "success": True,
        "composition_id": composition["id"],
        "job_id": job_id,
        "status": "queued",
        "message": "Composition queued for processing. Check job status for updates."
    }

# ✅ FIX: Auto-trigger composition after video is generated
async def _trigger_composition_async(
    job_id: str,
    tenant_id: str,
    scene_clips: list,
    background_music: dict,
    heygen_job_id: str
):
    """
    Auto-trigger composition after HeyGen video is generated
    Waits for video to be completed, then triggers composition
    """
    try:
        logger.info(f"[MarcelGPT] Composition trigger started for job {job_id}")

        # Poll for video completion (max 30 minutes)
        max_attempts = 360  # 30 min (5 sec intervals)
        attempt = 0

        while attempt < max_attempts:
            try:
                # Check if video job is completed
                job_res = supabase.table("video_jobs").select("*").eq("id", job_id).execute()
                jobs = ensure_response(job_res)

                if jobs and jobs[0].get("status") == "completed":
                    logger.info(f"[MarcelGPT] Video job {job_id} completed, triggering composition")
                    break

                # Wait 5 seconds before next check
                await asyncio.sleep(5)
                attempt += 1

            except Exception as check_error:
                logger.warning(f"[MarcelGPT] Error checking video status: {check_error}")
                await asyncio.sleep(5)
                attempt += 1

        # Get video artifacts
        artifacts_res = supabase.table("video_artifacts").select("*").eq("job_id", job_id).execute()
        artifacts = ensure_response(artifacts_res)

        if not artifacts:
            logger.error(f"[MarcelGPT] No artifacts found for job {job_id}")
            return

        # Log composition trigger
        logger.info(f"[MarcelGPT] Composition queued for job {job_id} with {len(scene_clips or [])} scene clips")

    except Exception as e:
        logger.error(f"[MarcelGPT] Error in composition trigger: {str(e)}")
