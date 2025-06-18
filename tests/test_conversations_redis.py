import pytest
from backend.data_services.mongo.conversation_repository import ConversationRepository, create_conversation, update_conversation, delete_conversation
from backend.data_services.redis_messaging import RedisMessaging
from datetime import datetime, UTC
from bson import ObjectId
import json
import asyncio

@pytest.fixture
def conversation_repository():
    return ConversationRepository()

@pytest.fixture
def redis_messaging():
    return RedisMessaging()

@pytest.fixture
def sample_conversation():
    return {
        "user_id": ObjectId(),  # Generate a new ObjectId for user_id
        "subject": "Test Conversation",
        "source": "Email",
        "status": "active",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "messages": [
            {
                "sender": "test@example.com",
                "text": "Hello, this is a test message",
                "timestamp": datetime.now(UTC)
            }
        ]
    }

@pytest.mark.asyncio
async def test_mongo_redis_sync(conversation_repository, redis_messaging, sample_conversation):
    """Test that MongoDB updates are properly synchronized with Redis."""
    
    # 1. Test Create Operation
    # Create conversation in MongoDB
    created_conv = create_conversation(sample_conversation)
    assert created_conv is not None
    conversation_id = str(created_conv["_id"])
    
    # Verify Redis has the conversation
    redis_key = f"conversation:{str(sample_conversation['user_id'])}:{conversation_id}"
    redis_data = redis_messaging.publisher.get(redis_key)
    assert redis_data is not None
    
    # Parse Redis data and verify content
    redis_conv = json.loads(redis_data)
    assert redis_conv["subject"] == sample_conversation["subject"]
    assert redis_conv["source"] == sample_conversation["source"]
    
    # 2. Test Update Operation
    # Update conversation in MongoDB
    update_data = {
        "subject": "Updated Test Conversation",
        "updated_at": datetime.now(UTC)
    }
    updated_conv = update_conversation(conversation_id, update_data)
    assert updated_conv is not None
    
    # Verify Redis has the updated conversation
    redis_data = redis_messaging.publisher.get(redis_key)
    assert redis_data is not None
    
    # Parse Redis data and verify updated content
    redis_conv = json.loads(redis_data)
    assert redis_conv["subject"] == "Updated Test Conversation"
    
    # 3. Test Delete Operation
    # Delete conversation from MongoDB
    delete_result = delete_conversation(conversation_id)
    assert delete_result is not None
    
    # Verify Redis no longer has the conversation
    redis_data = redis_messaging.publisher.get(redis_key)
    assert redis_data is None

@pytest.mark.asyncio
async def test_redis_pubsub(conversation_repository, redis_messaging, sample_conversation):
    """Test Redis pub/sub functionality with actual MongoDB data."""
    # Set up event for message signaling
    message_received = asyncio.Event()
    received_messages = []

    async def message_handler(message):
        print(f"Message received: {message}")
        received_messages.append(message)
        message_received.set()

    # Subscribe to Redis channel first
    user_id = str(sample_conversation["user_id"])
    channel = f"conversations:{user_id}"
    print(f"Subscribing to channel: {channel}")
    redis_task = asyncio.create_task(
        redis_messaging.subscribe_to_channel(channel, message_handler)
    )

    try:
        # Wait a moment to ensure subscription is established
        await asyncio.sleep(1)
        
        # Create conversation in MongoDB
        print("Creating conversation in MongoDB...")
        created_conv = create_conversation(sample_conversation)
        assert created_conv is not None
        conversation_id = str(created_conv["_id"])
        
        # Wait for message with timeout
        try:
            print("Waiting for message...")
            await asyncio.wait_for(message_received.wait(), timeout=20.0)
        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for message from MongoDB")

        # Verify message was received
        assert len(received_messages) > 0
        assert received_messages[0]["type"] == "new_conversation"
        assert received_messages[0]["conversation"]["_id"] == conversation_id

    finally:
        # Clean up
        redis_task.cancel()
        try:
            await redis_task
        except asyncio.CancelledError:
            pass 