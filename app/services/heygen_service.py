"""
HeyGen API Service
Handles all interactions with HeyGen API v2
"""
import httpx
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from app.db.supabase_client import supabase
from app.config import settings


class HeyGenService:
    """Service for interacting with HeyGen API"""

    BASE_URL = "https://api.heygen.com"
    CACHE_TTL_HOURS = 24

    def __init__(self, api_key: str):
        """
        Initialize HeyGen service with API key

        Args:
            api_key: HeyGen API key
        """
        self.api_key = api_key
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Make HTTP request to HeyGen API

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters

        Returns:
            API response as dict

        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                raise httpx.HTTPStatusError(
                    f"{exc} - Response: {detail}",
                    request=exc.request,
                    response=exc.response
                ) from exc
            return response.json()

    # =========================================================================
    # Catalog Methods (with caching)
    # =========================================================================

    async def list_avatars(self, force_refresh: bool = False) -> List[Dict]:
        """
        List available avatars - NO CACHING, always fresh from API

        Args:
            force_refresh: Ignored, always fetches fresh

        Returns:
            List of avatar objects
        """
        import sys
        print(f"[HeyGen] list_avatars called - ALWAYS FRESH (no cache)", file=sys.stderr, flush=True)

        # ALWAYS fetch from API - NO CACHE
        print(f"[HeyGen] Fetching from HeyGen API: GET /v2/avatars", file=sys.stderr, flush=True)
        try:
            response = await self._make_request("GET", "/v2/avatars")
            print(f"[HeyGen] API Response keys: {list(response.keys())}", file=sys.stderr, flush=True)
            # HeyGen API returns: {'error': None, 'data': {'avatars': [...]}}
            avatars = response.get("data", {}).get("avatars", [])
            print(f"[HeyGen] Extracted {len(avatars)} avatars from response", file=sys.stderr, flush=True)
            return avatars
        except Exception as e:
            print(f"[HeyGen] ERROR calling API: {type(e).__name__}: {str(e)}", file=sys.stderr, flush=True)
            return []


    async def list_voices(self, force_refresh: bool = False) -> List[Dict]:
        """
        List available voices with 24h caching

        Args:
            force_refresh: Force refresh cache

        Returns:
            List of voice objects
        """
        # Check cache first
        if not force_refresh:
            cache_threshold = datetime.now() - timedelta(hours=self.CACHE_TTL_HOURS)
            cached = (supabase.table("catalog_voices")
                .select("*")
                .gte("cached_at", cache_threshold.isoformat())
                .execute())

            if cached.data:
                voices = [item["data"] for item in cached.data]
                # Always ensure volkanerenee is in the list
                volkanerenee_id = "891bc0ed75cd456db75ac706e82e6b31"
                if not any(v.get("voice_id") == volkanerenee_id for v in voices):
                    voices.append({
                        "voice_id": volkanerenee_id,
                        "name": "volkanerenee",
                        "language": "English",
                        "gender": "male",
                        "accent": "American",
                        "age_range": "25-35",
                        "preview_audio": None,
                        "support_pause": True,
                        "emotion_support": False,
                        "support_interactive_avatar": False,
                        "support_locale": False
                    })
                return voices

        # Fetch from API
        response = await self._make_request("GET", "/v2/voices")
        # HeyGen API returns: {'error': None, 'data': {'voices': [...]}}
        voices = response.get("data", {}).get("voices", [])

        # Add volkanerenee voice if not already present
        volkanerenee_id = "891bc0ed75cd456db75ac706e82e6b31"
        if not any(v.get("voice_id") == volkanerenee_id for v in voices):
            voices.append({
                "voice_id": volkanerenee_id,
                "name": "volkanerenee",
                "language": "English",
                "gender": "male",
                "accent": "American",
                "age_range": "25-35",
                "preview_audio": None,
                "support_pause": True,
                "emotion_support": False,
                "support_interactive_avatar": False,
                "support_locale": False
            })

        # Enrich voices with sample URLs - map preview_audio to sample_url
        for voice in voices:
            # HeyGen API returns preview_audio, map it to sample_url for frontend
            if voice.get("preview_audio"):
                voice["sample_url"] = voice["preview_audio"]
            elif not voice.get("sample_url"):
                # Fallback: construct one if neither exists
                voice_id = voice.get("voice_id", "")
                if voice_id:
                    voice["sample_url"] = f"https://heygen.com/sample-audio/{voice_id}.mp3"

            voice_data = {
                "voice_id": voice["voice_id"],
                "voice_name": voice.get("name"),
                "language": voice.get("language"),
                "gender": voice.get("gender"),
                "accent": voice.get("accent"),
                "age_range": voice.get("age_range"),
                "supports_emotion": voice.get("supports_emotion", False),
                "data": voice,
                "cached_at": datetime.now().isoformat()
            }

            (supabase.table("catalog_voices")
                .upsert(voice_data, on_conflict="voice_id")
                .execute())

        return voices

    async def list_avatar_groups(self) -> List[Dict]:
        """
        List all photo avatar groups

        Returns:
            List of avatar group dictionaries
        """
        import sys
        print(f"[HeyGen] Fetching avatar groups: GET /v2/avatar_group.list", file=sys.stderr, flush=True)
        response = await self._make_request("GET", "/v2/avatar_group.list")

        print(f"[HeyGen] list_avatar_groups response keys: {list(response.keys())}", file=sys.stderr, flush=True)
        data = response.get("data") or {}
        if isinstance(data, list):
            groups_raw = data
        else:
            groups_raw = (
                data.get("avatar_groups")
                or data.get("avatar_group_list")
                or data.get("list")
                or data.get("items")
                or []
            )

        print(f"[HeyGen] Normalizing {len(groups_raw)} avatar groups", file=sys.stderr, flush=True)
        groups: List[Dict[str, Any]] = []

        for idx, group in enumerate(groups_raw):
            if not isinstance(group, dict):
                continue

            group_id = (
                group.get("group_id")
                or group.get("avatar_group_id")
                or group.get("id")
            )
            if group_id:
                group.setdefault("group_id", group_id)
                group.setdefault("avatar_group_id", group_id)
                group.setdefault("id", group_id)

            num_looks = (
                group.get("num_looks")
                if group.get("num_looks") is not None
                else group.get("look_count")
                if group.get("look_count") is not None
                else group.get("num_avatars")
                if group.get("num_avatars") is not None
                else group.get("avatar_count")
            )
            if num_looks is not None:
                group["num_looks"] = num_looks

            preview_image = (
                group.get("preview_image")
                or group.get("preview_image_url")
                or group.get("cover_url")
            )
            if preview_image:
                group.setdefault("preview_image", preview_image)

            groups.append(group)

            print(
                f"[HeyGen] Group #{idx+1}: {group.get('group_id', 'NO_ID')} - {group.get('name', 'NO_NAME')} "
                f"({group.get('num_looks', 'unknown')} looks)",
                file=sys.stderr,
                flush=True
            )

        return groups

    async def list_avatars_in_group(self, group_id: str) -> List[Dict]:
        """
        List all avatars (looks) in a specific avatar group

        Args:
            group_id: Avatar group ID

        Returns:
            List of avatar (look) dictionaries
        """
        import sys

        collected: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()

        page = 1
        page_size = 50
        total_expected = None

        while True:
            print(
                f"[HeyGen] Fetching avatars in group {group_id}: page={page}, size={page_size}",
                file=sys.stderr,
                flush=True
            )
            response = await self._make_request(
                "GET",
                f"/v2/avatar_group/{group_id}/avatars",
                params={"page": page, "page_size": page_size}
            )

            data = response.get("data") or {}
            if isinstance(data, list):
                avatars_raw = data
            else:
                avatars_raw = (
                    data.get("avatar_list")
                    or data.get("avatars")
                    or data.get("items")
                    or []
                )

            page_total = len(avatars_raw)
            print(
                f"[HeyGen]   Received {page_total} avatars (running total {len(collected)})",
                file=sys.stderr,
                flush=True
            )

            for avatar in avatars_raw:
                if not isinstance(avatar, dict):
                    continue
                avatar_id = (
                    avatar.get("avatar_id")
                    or avatar.get("id")
                    or avatar.get("look_id")
                )
                if not avatar_id or avatar_id in seen_ids:
                    continue
                seen_ids.add(avatar_id)

                avatar.setdefault("avatar_id", avatar_id)
                avatar.setdefault("look_id", avatar_id)

                preview_image = (
                    avatar.get("preview_image_url")
                    or avatar.get("portrait_url")
                    or avatar.get("cover_url")
                )
                if preview_image:
                    avatar.setdefault("preview_image_url", preview_image)

                collected.append(avatar)

            # Determine pagination limits
            if total_expected is None:
                total_expected = (
                    data.get("total")
                    or data.get("total_count")
                    or data.get("total_page_count")
                    or data.get("total_avatars")
                )
                if isinstance(total_expected, str) and total_expected.isdigit():
                    total_expected = int(total_expected)

            has_more = False
            if total_expected is not None:
                has_more = len(collected) < total_expected
            else:
                has_more = page_total == page_size and page_total > 0

            if not has_more:
                break

            page += 1

            # Safety cap to prevent infinite loops
            if page > 20:
                print("[HeyGen] Pagination safety stop after 20 pages", file=sys.stderr, flush=True)
                break

        print(
            f"[HeyGen] Found {len(collected)} avatars in group {group_id}",
            file=sys.stderr,
            flush=True
        )

        # Log first few avatars
        for idx, avatar in enumerate(collected[:3]):
            print(
                f"[HeyGen]   Avatar #{idx+1}: {avatar.get('avatar_id', 'NO_ID')} - {avatar.get('avatar_name', 'NO_NAME')}",
                file=sys.stderr,
                flush=True
            )

        if len(collected) > 3:
            print(f"[HeyGen]   ... and {len(collected) - 3} more avatars", file=sys.stderr, flush=True)

        return collected

    # =========================================================================
    # Video Generation Methods
    # =========================================================================

    async def create_video_v2(
        self,
        input_text: str,
        avatar_id: str,
        voice_id: str,
        callback_url: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Create video using v2 API (simple talking avatar)

        Args:
            input_text: Text for avatar to speak (max 1500 chars)
            avatar_id: Avatar ID from catalog
            voice_id: Voice ID from catalog
            callback_url: Webhook URL for completion notification
            **kwargs: Additional parameters (dimension, background, etc.)

        Returns:
            Job response with video_id

        API Response:
        {
            "code": 100,
            "data": {
                "video_id": "abc123..."
            },
            "message": "Success"
        }
        """
        if len(input_text) > 1500:
            raise ValueError("Input text must be less than 1500 characters")

        dimension: Dict[str, Any] = {
            "width": kwargs.get("width", 1920),
            "height": kwargs.get("height", 1080)
        }

        # Add orientation if provided
        if kwargs.get("orientation"):
            dimension["orientation"] = kwargs["orientation"]

        payload: Dict[str, Any] = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": kwargs.get("avatar_style", "normal")
                },
                "voice": {
                    "type": "text",
                    "input_text": input_text,
                    "voice_id": voice_id,
                    "speed": kwargs.get("speed", 1.0)
                }
            }],
            "dimension": dimension,
            "test": kwargs.get("test", False),
        }

        title = kwargs.get("title")
        if title:
            payload["title"] = title

        # Add callback if provided
        if callback_url:
            payload["callback_id"] = callback_url

        # Add background if provided
        if kwargs.get("background") is not None:
            payload["video_inputs"][0]["background"] = kwargs["background"]

        response = await self._make_request("POST", "/v2/video/generate", data=payload)
        return response

    async def create_video_av4(
        self,
        input_text: str,
        avatar_id: str,
        voice_id: str,
        callback_url: Optional[str] = None,
        video_title: Optional[str] = None,
        **kwargs
    ) -> Dict:
        """
        Create video using AV4 API (photorealistic avatars)

        Args:
            input_text: Text for avatar to speak (script parameter)
            avatar_id: Avatar ID (must be AV4 compatible) or image_key for photo avatars
            voice_id: Voice ID from catalog
            callback_url: Webhook URL for completion
            video_title: Title for the video (required by HeyGen AV4 API)
            **kwargs: Additional parameters (image_key for photo avatars, etc.)

        Returns:
            Job response with video_id
        """
        # AV4 API expects "script" as the text parameter
        payload = {
            "script": input_text,
            "voice_id": voice_id
        }

        # Add video_title (required by HeyGen AV4 API)
        if video_title:
            payload["video_title"] = video_title

        # For photo avatars, use image_key parameter; for standard avatars use avatar_id
        # If image_key is explicitly provided in kwargs, use it; otherwise use avatar_id
        if kwargs.get("image_key"):
            payload["image_key"] = kwargs["image_key"]
        else:
            # Try avatar_id first, but also check if it should be image_key
            # Photo avatar IDs often have specific patterns, but to be safe, try with image_key as fallback
            payload["avatar_id"] = avatar_id

        # Add optional parameters from kwargs
        if kwargs.get("width"):
            payload["width"] = kwargs["width"]
        if kwargs.get("height"):
            payload["height"] = kwargs["height"]
        if kwargs.get("orientation"):
            payload["orientation"] = kwargs["orientation"]
        if kwargs.get("speed"):
            payload["speed"] = kwargs["speed"]

        if callback_url:
            payload["webhook_url"] = callback_url

        response = await self._make_request("POST", "/v2/video/av4/generate", data=payload)
        return response

    # =========================================================================
    # Job Status Methods
    # =========================================================================

    async def get_video_status(self, video_id: str) -> Dict:
        """
        Get video generation status

        Args:
            video_id: Video job ID from HeyGen

        Returns:
            Status response with video URL when completed

        Status flow: pending -> processing -> completed/failed
        """
        response = await self._make_request("GET", f"/v1/video_status.get?video_id={video_id}")
        return response

    async def list_videos(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> Dict:
        """
        List generated videos

        Args:
            limit: Number of results
            offset: Pagination offset

        Returns:
            List of videos
        """
        params = {"limit": limit, "offset": offset}
        response = await self._make_request("GET", "/v1/video.list", params=params)
        return response

    # =========================================================================
    # Asset Upload Methods
    # =========================================================================

    async def upload_asset(
        self,
        file_url: str,
        asset_type: str = "image"
    ) -> Dict:
        """
        Upload asset to HeyGen

        Args:
            file_url: Public URL of file to upload
            asset_type: Type of asset (image, video)

        Returns:
            Asset ID and details
        """
        payload = {
            "url": file_url,
            "type": asset_type
        }

        response = await self._make_request("POST", "/v1/asset.upload", data=payload)
        return response

    # =========================================================================
    # Photo Avatar (Looks) Methods
    # =========================================================================

    async def create_photo_avatar_group(self, name: str, **kwargs) -> Dict:
        payload = {"name": name, **kwargs}
        return await self._make_request(
            "POST", "/v2/photo_avatar/avatar_group/create", data=payload
        )

    async def add_to_photo_avatar_group(
        self,
        avatar_group_id: str,
        look_ids: Optional[List[str]] = None,
        photo_ids: Optional[List[str]] = None
    ) -> Dict:
        payload: Dict[str, Any] = {"avatar_group_id": avatar_group_id}
        if look_ids:
            payload["look_ids"] = look_ids
        if photo_ids:
            payload["photo_ids"] = photo_ids
        return await self._make_request(
            "POST", "/v2/photo_avatar/avatar_group/add", data=payload
        )

    async def generate_photo_avatar_photo(self, **payload) -> Dict:
        return await self._make_request(
            "POST", "/v2/photo_avatar/photo/generate", data=payload
        )

    async def train_photo_avatar_group(self, avatar_group_id: str) -> Dict:
        payload = {"avatar_group_id": avatar_group_id}
        return await self._make_request(
            "POST", "/v2/photo_avatar/train", data=payload
        )

    async def get_photo_avatar_training(self, job_id: str) -> Dict:
        return await self._make_request(
            "GET", f"/v2/photo_avatar/training/{job_id}"
        )

    async def generate_photo_avatar_look(self, payload: Dict[str, Any]) -> Dict:
        return await self._make_request(
            "POST", "/v2/photo_avatar/look/generate", data=payload
        )

    async def generate_photo_avatar_looks(
        self,
        image_url: str,
        group_id: str,
        prompt: str,
        style: str = "Realistic",
        orientation: str = "square",
        pose: str = "half_body"
    ) -> Dict:
        """
        Generate new photo avatar looks using HeyGen's photo avatar generation API

        Args:
            image_url: URL of avatar image (e.g., preview image from HeyGen)
            group_id: Avatar group ID (e.g., Marcel group ID)
            prompt: Description of the look to generate
            style: Style - 'Realistic', 'Pixar', 'Cinematic', 'Vintage', 'Noir', 'Cyberpunk', 'Unspecified'
            orientation: Orientation - 'square', 'horizontal', 'vertical'
            pose: Pose - 'half_body', 'close_up', 'full_body'

        Returns:
            Generation response with generation_id and image_keys
        """
        payload = {
            "image_url": image_url,
            "group_id": group_id,
            "prompt": prompt,
            "style": style,
            "orientation": orientation,
            "pose": pose
        }
        return await self.generate_photo_avatar_look(payload)

    async def get_photo_avatar_generation(self, generation_id: str) -> Dict:
        return await self._make_request(
            "GET", f"/v2/photo_avatar/generation/{generation_id}"
        )

    async def get_photo_avatar(self, look_id: str) -> Dict:
        return await self._make_request(
            "GET", f"/v2/photo_avatar/{look_id}"
        )


# Singleton helper to get service instance
def get_heygen_service(tenant_id: int) -> Optional[HeyGenService]:
    """
    Get HeyGen service instance for tenant

    Args:
        tenant_id: Tenant ID

    Returns:
        HeyGenService instance or None if no API key
    """
    # Get tenant's API key
    result = (supabase.table("tenants")
        .select("heygen_api_key")
        .eq("id", tenant_id)
        .limit(1)
        .execute())

    if not result.data or not result.data[0].get("heygen_api_key"):
        return None

    api_key = result.data[0]["heygen_api_key"]
    return HeyGenService(api_key)


def get_fallback_heygen_service() -> Optional[HeyGenService]:
    """
    Get HeyGen service instance based on fallback API key.

    Returns:
        HeyGenService instance or None if fallback key not configured.
    """
    fallback_key = settings.HEYGEN_FALLBACK_API_KEY
    if not fallback_key:
        return None
    return HeyGenService(fallback_key)
