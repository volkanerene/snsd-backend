import pytest


@pytest.mark.asyncio
async def test_list_photo_avatar_looks_returns_serialized_payload(async_client, monkeypatch):
    sample_record = {
        "id": 42,
        "name": "Sample Look",
        "prompt": "Sample prompt",
        "status": "ready",
        "heygen_look_id": "look-4992bcd0c5594cebb40d881144f8c412",
        "voice_id": "voice-abc",
        "preview_urls": ["https://cdn.example.com/look.png"],
        "cover_url": "https://cdn.example.com/look.png",
        "heygen_generation_id": "gen-123",
        "error_message": None,
        "config": {"width": 1280, "height": 720, "avatarStyle": "normal"},
        "meta": {"source": "existing_avatar", "brand_preset_id": 7},
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }

    class StubPhotoAvatarService:
        def __init__(self, tenant_id: str, user_id: str):
            self.tenant_id = tenant_id
            self.user_id = user_id

        async def list_looks(self, force_refresh: bool = False):
            assert force_refresh is False
            return [sample_record]

    monkeypatch.setattr(
        "app.routers.marcel_gpt.PhotoAvatarService",
        StubPhotoAvatarService,
    )

    response = await async_client.get("/marcel-gpt/photo-avatars/looks")
    assert response.status_code == 200

    payload = response.json()
    assert payload["count"] == 1
    look = payload["looks"][0]
    assert look["id"] == sample_record["id"]
    assert look["avatarId"] == sample_record["heygen_look_id"]
    assert look["voiceId"] == sample_record["voice_id"]
    assert look["source"] == sample_record["meta"]["source"]


@pytest.mark.asyncio
async def test_list_avatars_uses_heygen_service(async_client, monkeypatch):
    class StubHeyGenService:
        def __init__(self):
            self.call_args = []

        async def list_avatars(self, force_refresh: bool = False):
            self.call_args.append(force_refresh)
            return [
                {
                    "avatar_id": "avatar-1289",
                    "avatar_name": "Demo Avatar",
                    "preview_image_url": "https://cdn.example.com/avatar.png",
                }
            ]

    stub_service = StubHeyGenService()
    monkeypatch.setattr(
        "app.routers.marcel_gpt.get_heygen_service",
        lambda tenant_id: stub_service,
    )

    response = await async_client.get("/marcel-gpt/avatars?force_refresh=true")
    assert response.status_code == 200

    payload = response.json()
    assert payload["count"] == 1
    assert payload["avatars"][0]["avatar_id"] == "avatar-1289"
    assert stub_service.call_args == [True]


@pytest.mark.asyncio
async def test_list_voices_applies_filters(async_client, monkeypatch):
    voices = [
        {
            "voice_id": "en-female",
            "name": "Alice",
            "language": "en",
            "gender": "female",
        },
        {
            "voice_id": "es-male",
            "name": "Carlos",
            "language": "es",
            "gender": "male",
        },
    ]

    class StubHeyGenService:
        async def list_voices(self, force_refresh: bool = False):
            return voices

    monkeypatch.setattr(
        "app.routers.marcel_gpt.get_heygen_service",
        lambda tenant_id: StubHeyGenService(),
    )

    response = await async_client.get(
        "/marcel-gpt/voices?language=en&gender=female"
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["count"] == 1
    assert payload["voices"][0]["voice_id"] == "en-female"


@pytest.mark.asyncio
async def test_list_avatar_groups_with_avatars(async_client, monkeypatch):
    class StubHeyGenService:
        async def list_avatar_groups(self):
            return [
                {
                    "id": "group-1",
                    "name": "Demo Group",
                    "num_looks": 2,
                    "preview_image": "https://cdn.example.com/group.png"
                }
            ]

        async def list_avatars_in_group(self, group_id: str):
            assert group_id == "group-1"
            return [
                {
                    "avatar_id": "avatar-1",
                    "avatar_name": "Demo Avatar",
                    "preview_image_url": "https://cdn.example.com/avatar.png"
                }
            ]

    monkeypatch.setattr(
        "app.routers.marcel_gpt.get_heygen_service",
        lambda tenant_id: StubHeyGenService(),
    )

    response = await async_client.get(
        "/marcel-gpt/avatar-groups?include_avatars=true"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    group = payload["groups"][0]
    assert group["id"] == "group-1"
    assert group["numLooks"] == 2
    assert group["avatars"][0]["avatar_id"] == "avatar-1"
