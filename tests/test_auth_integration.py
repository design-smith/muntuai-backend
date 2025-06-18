import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.routers.auth_utils import get_current_user

def override_get_current_user_valid():
    return {"user_id": "testuser", "user": {"sub": "testuser"}}

def override_get_current_user_invalid():
    raise Exception("Invalid token")

def test_protected_endpoint_requires_auth():
    app.dependency_overrides[get_current_user] = override_get_current_user_valid
    client = TestClient(app)
    response = client.get("/users")
    assert response.status_code == 200
    app.dependency_overrides[get_current_user] = override_get_current_user_invalid
    client = TestClient(app)
    response = client.get("/users")
    assert response.status_code in (401, 403)
    app.dependency_overrides = {} 