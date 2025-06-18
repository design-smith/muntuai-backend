import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.routers.auth_utils import get_current_user
from unittest.mock import patch

# Use a valid MongoDB ObjectId string
TEST_USER_ID = "507f1f77bcf86cd799439011"
TEST_PROVIDER = "gmail"
TEST_CONNECTION_ID = "conn-abc123"

@pytest.fixture(autouse=True)
def override_get_current_user():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": TEST_USER_ID, "user": {"sub": TEST_USER_ID}}
    yield
    app.dependency_overrides = {}

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_header():
    # Simulate a valid JWT for test user
    return {"Authorization": "Bearer test.jwt.token"}

@patch("backend.integrations.composio.client.ComposioIntegrationClient.initiate_connection", return_value="https://composio.example.com/oauth/gmail?user_id=507f1f77bcf86cd799439011")
def test_connect_integration(mock_composio, client, auth_header):
    response = client.post(f"/integrations/connect?provider={TEST_PROVIDER}", headers=auth_header)
    assert response.status_code == 200
    assert "redirect_url" in response.json()
    assert response.json()["redirect_url"].startswith("https://composio.example.com/oauth/")

@patch("backend.routers.integrations_router.get_user_by_id", return_value={"_id": TEST_USER_ID, "composio_integrations": []})
@patch("backend.routers.integrations_router.update_user")
def test_callback_integration(mock_update, mock_get_user, client, auth_header):
    response = client.get(f"/integrations/callback?provider={TEST_PROVIDER}&connection_id={TEST_CONNECTION_ID}", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_update.assert_called_once()
    args, kwargs = mock_update.call_args
    assert args[0] == TEST_USER_ID
    update_data = args[1]
    assert any(i["connection_id"] == TEST_CONNECTION_ID for i in update_data["composio_integrations"])

@patch("backend.routers.integrations_router.get_user_by_id", return_value={"_id": TEST_USER_ID, "composio_integrations": [{"provider": TEST_PROVIDER, "connection_id": TEST_CONNECTION_ID}]})
def test_list_integrations(mock_get_user, client, auth_header):
    response = client.get("/integrations", headers=auth_header)
    assert response.status_code == 200
    assert "integrations" in response.json()
    assert any(i["connection_id"] == TEST_CONNECTION_ID for i in response.json()["integrations"])

@patch("backend.routers.integrations_router.get_user_by_id", return_value={"_id": TEST_USER_ID, "composio_integrations": [{"provider": TEST_PROVIDER, "connection_id": TEST_CONNECTION_ID}]})
@patch("backend.routers.integrations_router.update_user")
def test_remove_integration(mock_update, mock_get_user, client, auth_header):
    response = client.delete(f"/integrations/{TEST_CONNECTION_ID}", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_update.assert_called_once()
    args, kwargs = mock_update.call_args
    assert args[0] == TEST_USER_ID
    update_data = args[1]
    assert all(i["connection_id"] != TEST_CONNECTION_ID for i in update_data["composio_integrations"]) 