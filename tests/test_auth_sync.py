import sys
import os
import pytest
from httpx import AsyncClient

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from backend.main import app

@pytest.mark.asyncio
async def test_supabase_user_sync():
    sample_user = {
        "id": "supabase-123-test",
        "email": "testuser@example.com",
        "user_metadata": {
            "full_name": "Test User"
        }
    }
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/auth/sync_user", json=sample_user)
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        user = data["user"]
        assert user["email"] == sample_user["email"]
        assert user["name"] == sample_user["user_metadata"]["full_name"]
        assert user["auth"]["provider"] == "supabase"
        assert user["auth"]["provider_id"] == sample_user["id"] 