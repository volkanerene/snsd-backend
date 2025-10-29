"""
HeyGen API Service
Handles all interactions with HeyGen API v2
"""
import httpx
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from app.db.supabase_client import supabase


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
        List available avatars with 24h caching

        Args:
            force_refresh: Force refresh cache

        Returns:
            List of avatar objects
        """
        import sys
        print(f"[HeyGen] list_avatars called, force_refresh={force_refresh}", file=sys.stderr, flush=True)

        # Check cache first
        if not force_refresh:
            cache_threshold = datetime.now() - timedelta(hours=self.CACHE_TTL_HOURS)
            cached = (supabase.table("catalog_avatars")
                .select("*")
                .gte("cached_at", cache_threshold.isoformat())
                .execute())

            print(f"[HeyGen] Cache check: found {len(cached.data) if cached.data else 0} cached avatars", file=sys.stderr, flush=True)
            if cached.data:
                return [item["data"] for item in cached.data]

        # Fetch from API
        print(f"[HeyGen] Fetching from HeyGen API: GET /v2/avatars", file=sys.stderr, flush=True)
        try:
            response = await self._make_request("GET", "/v2/avatars")
            print(f"[HeyGen] API Response keys: {list(response.keys())}", file=sys.stderr, flush=True)
            # HeyGen API returns: {'error': None, 'data': {'avatars': [...]}}
            avatars = response.get("data", {}).get("avatars", [])
            print(f"[HeyGen] Extracted {len(avatars)} avatars from response", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"[HeyGen] ERROR calling API: {type(e).__name__}: {str(e)}", file=sys.stderr, flush=True)
            return []

        # Update cache
        for avatar in avatars:
            avatar_data = {
                "avatar_id": avatar["avatar_id"],
                "avatar_name": avatar.get("avatar_name"),
                "gender": avatar.get("gender"),
                "preview_image_url": avatar.get("preview_image_url"),
                "preview_video_url": avatar.get("preview_video_url"),
                "is_public": avatar.get("is_public", True),
                "is_instant": avatar.get("is_instant", False),
                "data": avatar,
                "cached_at": datetime.now().isoformat()
            }

            (supabase.table("catalog_avatars")
                .upsert(avatar_data, on_conflict="avatar_id")
                .execute())

        return avatars

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
                return [item["data"] for item in cached.data]

        # Fetch from API
        response = await self._make_request("GET", "/v2/voices")
        # HeyGen API returns: {'error': None, 'data': {'voices': [...]}}
        voices = response.get("data", {}).get("voices", [])

        # Update cache
        for voice in voices:
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
            "dimension": {
                "width": kwargs.get("width", 1920),
                "height": kwargs.get("height", 1080)
            },
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
        **kwargs
    ) -> Dict:
        """
        Create video using AV4 API (photorealistic avatars)

        Args:
            input_text: Text for avatar to speak
            avatar_id: Avatar ID (must be AV4 compatible)
            voice_id: Voice ID from catalog
            callback_url: Webhook URL for completion
            **kwargs: Additional parameters

        Returns:
            Job response with video_id
        """
        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": input_text,
                    "voice_id": voice_id
                }
            }]
        }

        if callback_url:
            payload["callback_id"] = callback_url

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
