import pytest
from pytest_asyncio import fixture as async_fixture
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, UTC
import asyncio
from dotenv import load_dotenv
from bson import ObjectId

# Load environment variables
load_dotenv()

# Get MongoDB connection string from environment
MONGODB_URI = os.getenv("MONGO_URI")
if not MONGODB_URI:
    raise ValueError("MONGO_URI environment variable is not set")

# Import after environment setup
from backend.data_services.mongo.integration_repository import IntegrationRepository

@async_fixture
async def integration_repo():
    """Fixture to create and clean up the integration repository."""
    client = AsyncIOMotorClient(MONGODB_URI)
    repo = IntegrationRepository(client)
    # Clean up before and after tests
    await repo.collection.delete_many({})
    yield repo
    await repo.collection.delete_many({})

@pytest.mark.asyncio
async def test_create_and_get_integration(integration_repo):
    """Test creating and retrieving an integration."""
    user_id_str = str(ObjectId()) # Generate user_id once as a string
    # Test data
    integration_data = {
        "user_id": user_id_str, # Use the string user_id
        "type": "email",
        "provider": "gmail",
        "name": "test@gmail.com",
        "credentials": {
            "token": "test_token",
            "refresh_token": "test_refresh_token",
            "email": "test@gmail.com"
        },
        "status": "ACTIVE",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }

    # Create integration
    created_integration = await integration_repo.create_integration(integration_data)
    assert created_integration is not None
    assert created_integration["_id"] is not None
    assert created_integration["user_id"] == user_id_str # Compare as string
    assert created_integration["type"] == integration_data["type"]
    assert created_integration["provider"] == integration_data["provider"]

    # Get integration by ID
    retrieved_integration = await integration_repo.get_integration_by_id(created_integration["_id"])
    assert retrieved_integration is not None
    assert retrieved_integration["_id"] == created_integration["_id"]
    assert retrieved_integration["user_id"] == user_id_str # Compare as string

@pytest.mark.asyncio
async def test_update_integration(integration_repo):
    """Test updating an integration."""
    user_id_str = str(ObjectId()) # Generate user_id once as a string
    # Create initial integration
    integration_data = {
        "user_id": user_id_str, # Use the string user_id
        "type": "email",
        "provider": "gmail",
        "name": "test@gmail.com",
        "credentials": {
            "token": "test_token",
            "refresh_token": "test_refresh_token",
            "email": "test@gmail.com"
        },
        "status": "ACTIVE",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }
    created_integration = await integration_repo.create_integration(integration_data)

    # Update data
    update_data = {
        "status": "INACTIVE",
        "name": "updated@gmail.com",
        "updated_at": datetime.now(UTC)
    }

    # Update integration
    await integration_repo.update_integration(created_integration["_id"], update_data)

    # Get updated integration
    updated_integration = await integration_repo.get_integration_by_id(created_integration["_id"])
    assert updated_integration is not None
    assert updated_integration["status"] == "INACTIVE"
    assert updated_integration["name"] == "updated@gmail.com"
    assert updated_integration["user_id"] == user_id_str # Compare as string

@pytest.mark.asyncio
async def test_delete_integration(integration_repo):
    """Test deleting an integration."""
    user_id_str = str(ObjectId()) # Generate user_id once as a string
    # Create integration
    integration_data = {
        "user_id": user_id_str, # Use the string user_id
        "type": "email",
        "provider": "gmail",
        "name": "test@gmail.com",
        "credentials": {
            "token": "test_token",
            "refresh_token": "test_refresh_token",
            "email": "test@gmail.com"
        },
        "status": "ACTIVE",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }
    created_integration = await integration_repo.create_integration(integration_data)

    # Delete integration
    await integration_repo.delete_integration(created_integration["_id"])

    # Verify deletion
    deleted_integration = await integration_repo.get_integration_by_id(created_integration["_id"])
    assert deleted_integration is None

@pytest.mark.asyncio
async def test_get_user_integrations(integration_repo):
    """Test retrieving all integrations for a user."""
    user_id_str = str(ObjectId()) # Generate user_id once as a string
    # Create multiple integrations for the same user
    integrations = [
        {
            "user_id": user_id_str, # Use the string user_id
            "type": "email",
            "provider": "gmail",
            "name": "test1@gmail.com",
            "credentials": {"token": "token1"},
            "status": "ACTIVE",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        },
        {
            "user_id": user_id_str, # Use the string user_id
            "type": "email",
            "provider": "outlook",
            "name": "test2@outlook.com",
            "credentials": {"token": "token2"},
            "status": "ACTIVE",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
    ]

    # Insert integrations
    for integration in integrations:
        await integration_repo.create_integration(integration)

    # Get user integrations
    user_integrations = await integration_repo.get_user_integrations(user_id_str) # Pass the string user_id
    assert len(user_integrations) == 2
    assert all(integration["user_id"] == user_id_str for integration in user_integrations) # Compare as string
    assert {integration["provider"] for integration in user_integrations} == {"gmail", "outlook"} 