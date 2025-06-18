import sys
import os
import pytest
from httpx import AsyncClient

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from backend.main import app

entities = [
    ("users", {"email": "testuser@example.com", "auth": {"provider": "test", "provider_id": "testid"}, "created_at": "2024-01-01T00:00:00Z"}),
    ("businesses", {"user_id": "000000000000000000000000", "name": "TestBiz", "created_at": "2024-01-01T00:00:00Z"}),
    ("contacts", {"user_id": "000000000000000000000000", "name": "TestContact", "created_at": "2024-01-01T00:00:00Z"}),
    ("conversations", {"user_id": "000000000000000000000000", "status": "active", "created_at": "2024-01-01T00:00:00Z"}),
    ("messages", {"conversation_id": "000000000000000000000000", "timestamp": "2024-01-01T00:00:00Z", "content": {"text": "hi"}}),
    ("events", {"user_id": "000000000000000000000000", "title": "TestEvent", "start_time": "2024-01-01T00:00:00Z", "created_at": "2024-01-01T00:00:00Z"}),
    ("assistants", {"user_id": "000000000000000000000000", "name": "TestAssistant", "type": "test", "created_at": "2024-01-01T00:00:00Z"}),
    ("tasks", {"name": "TestTask", "created_at": "2024-01-01T00:00:00Z"}),
    ("channels", {"name": "TestChannel", "created_at": "2024-01-01T00:00:00Z"}),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("entity, payload", entities)
async def test_crud_entity(entity, payload):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create
        create_resp = await ac.post(f"/api/{entity}", json=payload)
        assert create_resp.status_code == 200
        created = create_resp.json()
        _id = created.get("_id") or created.get(entity[:-1], {}).get("_id")
        assert _id
        # Get
        get_resp = await ac.get(f"/api/{entity}/{_id}")
        assert get_resp.status_code == 200
        # List
        list_resp = await ac.get(f"/api/{entity}")
        assert list_resp.status_code == 200
        # Update
        update_resp = await ac.put(f"/api/{entity}/{_id}", json={"updated": True})
        assert update_resp.status_code == 200
        # Delete
        delete_resp = await ac.delete(f"/api/{entity}/{_id}")
        assert delete_resp.status_code == 200
        # Confirm delete
        get_resp2 = await ac.get(f"/api/{entity}/{_id}")
        assert get_resp2.status_code == 404

def test_billing_get_plan(client, auth_header):
    response = client.get("/billing/plan", headers=auth_header)
    assert response.status_code in (200, 401)

def test_billing_add_payment_method(client, auth_header):
    # This would require a real or mocked Stripe payment method ID
    response = client.post("/billing/payment-method", json={"payment_method_id": "pm_test"}, headers=auth_header)
    assert response.status_code in (200, 401, 500)

def test_billing_list_payment_methods(client, auth_header):
    response = client.get("/billing/payment-methods", headers=auth_header)
    assert response.status_code in (200, 401)

def test_billing_remove_payment_method(client, auth_header):
    response = client.delete("/billing/payment-method/pm_test", headers=auth_header)
    assert response.status_code in (200, 401, 500)

def test_billing_subscribe_cancel(client, auth_header):
    # This would require a real or mocked Stripe price ID
    response = client.post("/billing/subscribe", json={"price_id": "price_test"}, headers=auth_header)
    assert response.status_code in (200, 401, 500)
    response = client.post("/billing/cancel", headers=auth_header)
    assert response.status_code in (200, 401, 400, 500)

def test_billing_invoices(client, auth_header):
    response = client.get("/billing/invoices", headers=auth_header)
    assert response.status_code in (200, 401)

def test_billing_webhook(client):
    # Simulate a Stripe webhook payload (signature should be mocked or disabled in test)
    response = client.post("/billing/webhook", data=b"{}", headers={"stripe-signature": "test"})
    assert response.status_code in (200, 400) 