from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.db.supabase_client import supabase
from app.routers.deps import ensure_response
from app.services.heygen_service import get_heygen_service

logger = logging.getLogger(__name__)

PHOTO_AVATAR_GROUPS_TABLE = "photo_avatar_groups"
PHOTO_AVATAR_LOOKS_TABLE = "photo_avatar_looks"
BRAND_PRESETS_TABLE = "brand_presets"


class PhotoAvatarService:
    """
    High-level orchestrator for HeyGen photo avatar look generation.
    Handles Supabase persistence and HeyGen API interactions.
    """

    def __init__(self, tenant_id: str, user_id: str):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.heygen = get_heygen_service(tenant_id)
        if not self.heygen:
            raise HTTPException(400, "HeyGen API key is not configured for this tenant")

    # ------------------------------------------------------------------
    # Supabase helpers
    # ------------------------------------------------------------------

    def _get_group_record(self) -> Optional[Dict[str, Any]]:
        res = (
            supabase.table(PHOTO_AVATAR_GROUPS_TABLE)
            .select("*")
            .eq("tenant_id", self.tenant_id)
            .limit(1)
            .execute()
        )
        data = ensure_response(res)
        return data[0] if data else None

    def _upsert_group_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        res = (
            supabase.table(PHOTO_AVATAR_GROUPS_TABLE)
            .upsert(record, on_conflict="tenant_id")
            .execute()
        )
        data = ensure_response(res)
        return data[0] if data else record

    def _insert_look_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        res = supabase.table(PHOTO_AVATAR_LOOKS_TABLE).insert(record).execute()
        data = ensure_response(res)
        return data[0]

    def _update_look_record(self, look_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        updates["updated_at"] = datetime.utcnow().isoformat()
        res = (
            supabase.table(PHOTO_AVATAR_LOOKS_TABLE)
            .update(updates)
            .eq("id", look_id)
            .eq("tenant_id", self.tenant_id)
            .execute()
        )
        data = ensure_response(res)
        return data[0] if data else updates

    def _get_look_record(self, look_id: int) -> Dict[str, Any]:
        res = (
            supabase.table(PHOTO_AVATAR_LOOKS_TABLE)
            .select("*")
            .eq("id", look_id)
            .eq("tenant_id", self.tenant_id)
            .limit(1)
            .execute()
        )
        data = ensure_response(res)
        if not data:
            raise HTTPException(404, "Look not found")
        return data[0]

    # ------------------------------------------------------------------
    # Group management
    # ------------------------------------------------------------------

    async def ensure_group(self) -> Dict[str, Any]:
        existing = self._get_group_record()
        if existing:
            return existing

        group_name = f"snsd-tenant-{self.tenant_id}"
        response = await self.heygen.create_photo_avatar_group(name=group_name)
        group_data = response.get("data") or response

        heygen_group_id = group_data.get("avatar_group_id") or group_data.get("id")
        if not heygen_group_id:
            raise HTTPException(500, "HeyGen API did not return avatar_group_id")

        record = {
            "tenant_id": self.tenant_id,
            "heygen_group_id": heygen_group_id,
            "name": group_name,
            "status": group_data.get("status", "created"),
            "meta": group_data,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        return self._upsert_group_record(record)

    # ------------------------------------------------------------------
    # Look lifecycle
    # ------------------------------------------------------------------

    async def create_look(
        self,
        name: str,
        prompt: Optional[str],
        notes: Optional[str],
        config: Dict[str, Any],
        voice_id: str,
        look_options: Optional[Dict[str, Any]] = None,
        base_avatar_id: Optional[str] = None,
        base_avatar_preview_url: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(
            "[PhotoAvatar] create_look | tenant=%s user=%s name=%s mode=%s",
            self.tenant_id,
            self.user_id,
            name,
            "existing" if base_avatar_id else "generate"
        )
        if base_avatar_id:
            logger.info(
                "[PhotoAvatar] using existing avatar | avatar_id=%s cover=%s",
                base_avatar_id,
                base_avatar_preview_url
            )
            record = {
                "tenant_id": self.tenant_id,
                "user_id": self.user_id,
                "heygen_generation_id": None,
                "heygen_look_id": base_avatar_id,
                "name": name,
                "prompt": prompt or notes,
                "status": "ready",
                "preview_urls": [base_avatar_preview_url] if base_avatar_preview_url else [],
                "cover_url": base_avatar_preview_url,
                "config": config,
                "voice_id": voice_id,
                "meta": {"source": "existing_avatar"},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }

            look_record = self._insert_look_record(record)
            preset_id = await self._ensure_brand_preset_for_look(
                look_id=look_record["id"],
                look_name=name,
                heygen_look_id=base_avatar_id,
                config=config,
                voice_id=voice_id,
                notes=prompt or notes,
                cover_url=base_avatar_preview_url
            )

            updates: Dict[str, Any] = {}
            if preset_id:
                updates["meta"] = {**(record.get("meta") or {}), "brand_preset_id": preset_id}
            if updates:
                look_record = self._update_look_record(look_record["id"], updates)
            logger.info(
                "[PhotoAvatar] existing avatar stored | look_id=%s preset_id=%s",
                look_record.get("id"),
                preset_id
            )
            return look_record

        group = await self.ensure_group()
        look_options = look_options or {}

        payload: Dict[str, Any] = {
            "avatar_group_id": group["heygen_group_id"],
            "prompt": prompt or notes or name,
            "orientation": look_options.get("orientation", "front"),
            "pose": look_options.get("pose", "neutral"),
            "style": look_options.get("style", "studio"),
            "camera_move": look_options.get("camera_move"),
            "count": look_options.get("count", 1),
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        logger.info(
            "[PhotoAvatar] generating new look | payload=%s",
            payload
        )
        response = await self.heygen.generate_photo_avatar_look(payload)
        data = response.get("data") or response

        generation_id = data.get("generation_id") or data.get("id")
        status = data.get("status", "generating")
        preview_urls = data.get("preview_urls") or []

        record = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "group_id": group.get("id"),
            "heygen_generation_id": generation_id,
            "heygen_look_id": data.get("look_id"),
            "name": name,
            "prompt": prompt or notes,
            "status": status,
            "preview_urls": preview_urls,
            "cover_url": data.get("cover_url") or (preview_urls[0] if preview_urls else None),
            "config": config,
            "voice_id": voice_id,
            "meta": {**data, "source": "generated"},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        look_record = self._insert_look_record(record)
        return await self.refresh_look_status(look_record["id"], auto=False)

    async def list_looks(self) -> List[Dict[str, Any]]:
        res = (
            supabase.table(PHOTO_AVATAR_LOOKS_TABLE)
            .select("*")
            .eq("tenant_id", self.tenant_id)
            .order("created_at", desc=True)
            .execute()
        )
        data = ensure_response(res) or []

        # Refresh pending looks quietly
        updated: List[Dict[str, Any]] = []
        for look in data:
            if look.get("status") in {"pending", "generating", "processing"} and look.get("heygen_generation_id"):
                try:
                    refreshed = await self.refresh_look_status(look["id"], auto=True)
                    updated.append(refreshed)
                    continue
                except Exception:
                    # Ignore background refresh errors; return stale data
                    pass
            updated.append(look)
        return updated

    async def refresh_look_status(self, look_id: int, auto: bool = False) -> Dict[str, Any]:
        look = self._get_look_record(look_id)

        if look.get("status") in {"ready", "failed"} and not auto:
            return look

        generation_id = look.get("heygen_generation_id")
        if not generation_id:
            return look

        generation_response = await self.heygen.get_photo_avatar_generation(generation_id)
        generation_data = generation_response.get("data") or generation_response
        status = generation_data.get("status", look.get("status"))

        updates: Dict[str, Any] = {
            "status": status,
            "meta": {**(look.get("meta") or {}), "generation": generation_data},
        }

        if status in {"completed", "success", "ready"}:
            look_id_from_generation = generation_data.get("look_id") or generation_data.get("photo_avatar_id") or look.get("heygen_look_id")
            if look_id_from_generation:
                look_response = await self.heygen.get_photo_avatar(look_id_from_generation)
                look_data = look_response.get("data") or look_response
                preview_urls = look_data.get("preview_urls") or generation_data.get("preview_urls") or look.get("preview_urls") or []
                cover_url = look_data.get("cover_url") or look_data.get("thumbnail_url") or (preview_urls[0] if preview_urls else None)

                updates.update({
                    "heygen_look_id": look_id_from_generation,
                    "preview_urls": preview_urls,
                    "cover_url": cover_url,
                    "status": "ready",
                    "meta": {**updates["meta"], "look": look_data}
                })

                # Ensure brand preset exists / updated
                preset_id = await self._ensure_brand_preset_for_look(
                    look_id=look_id,
                    look_name=look.get("name") or f"Look #{look_id}",
                    heygen_look_id=look_id_from_generation,
                    config=look.get("config") or {},
                    voice_id=look.get("voice_id"),
                    notes=look.get("prompt"),
                    cover_url=cover_url
                )
                if preset_id:
                    updates["meta"]["brand_preset_id"] = preset_id
        elif status in {"failed", "error"}:
            updates["error_message"] = generation_data.get("message") or generation_data.get("error")

        updated_record = self._update_look_record(look_id, updates)
        logger.info(
            "[PhotoAvatar] refresh status | look_id=%s status=%s",
            look_id,
            updated_record.get("status")
        )
        return updated_record

    async def get_look(self, look_id: int, refresh: bool = False) -> Dict[str, Any]:
        if refresh:
            return await self.refresh_look_status(look_id, auto=False)
        return self._get_look_record(look_id)

    async def _ensure_brand_preset_for_look(
        self,
        look_id: int,
        look_name: str,
        heygen_look_id: str,
        config: Dict[str, Any],
        voice_id: Optional[str],
        notes: Optional[str],
        cover_url: Optional[str]
    ) -> Optional[int]:
        # Check existing preset
        res = (
            supabase.table(BRAND_PRESETS_TABLE)
            .select("id")
            .eq("tenant_id", self.tenant_id)
            .eq("photo_avatar_look_id", look_id)
            .limit(1)
            .execute()
        )
        preset_data = ensure_response(res)
        preset_payload = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "name": look_name,
            "description": notes,
            "avatar_id": heygen_look_id,
            "avatar_style": config.get("avatarStyle", "normal"),
            "voice_id": voice_id or "default",
            "language": config.get("language", "en"),
            "tts_speed": config.get("speed", 1.0),
            "bg_type": config.get("backgroundType", "color"),
            "bg_value": (
                config.get("backgroundColor")
                if config.get("backgroundType") == "color"
                else config.get("backgroundImageUrl")
            ),
            "enable_subtitles": config.get("enableSubtitles", False),
            "video_width": config.get("width", 1280),
            "video_height": config.get("height", 720),
            "aspect_ratio": config.get("aspectRatio", "16:9"),
            "photo_avatar_look_id": look_id,
        }

        if preset_data:
            preset_id = preset_data[0]["id"]
            supabase.table(BRAND_PRESETS_TABLE).update(preset_payload).eq("id", preset_id).execute()
            return preset_id

        insert_res = supabase.table(BRAND_PRESETS_TABLE).insert(preset_payload).execute()
        inserted = ensure_response(insert_res)
        if inserted:
            return inserted[0]["id"]
        return None
