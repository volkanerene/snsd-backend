import os

import pytest
from httpx import AsyncClient

from app.main import app
from app.utils.auth import get_current_user


os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")


@pytest.fixture(autouse=True)
def override_auth_dependency():
    async def fake_current_user():
        return {
            "id": "user-123",
            "user_id": "user-123",
            "email": "tester@example.com",
            "role_id": 1,
            "tenant_id": "tenant-456",
        }

    app.dependency_overrides[get_current_user] = fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
