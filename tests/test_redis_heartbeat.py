import pytest
import sys
from pathlib import Path
import os
import asyncio

# Ensure backend is importable
sys.path.append(str(Path(__file__).parent.parent))

from data_services.redis_messaging import RedisMessaging

@pytest.mark.asyncio
async def test_redis_heartbeat():
    """Test Redis connection and configuration."""
    # Verify environment variables are set
    assert os.getenv("REDIS_HOST"), "REDIS_HOST environment variable is not set"
    assert os.getenv("REDIS_PORT"), "REDIS_PORT environment variable is not set"
    assert os.getenv("REDIS_PASSWORD"), "REDIS_PASSWORD environment variable is not set"
    
    # Try to connect to Redis
    redis = RedisMessaging()
    assert redis.publisher is not None, "Failed to create Redis publisher connection"
    assert redis.subscriber is not None, "Failed to create Redis subscriber connection"
    
    # Test connection with ping
    assert redis.publisher.ping(), "Redis ping failed"
    
    # Test basic operations
    test_key = "test:heartbeat"
    test_value = "test_value"
    
    # Set value
    redis.publisher.set(test_key, test_value)
    
    # Get value
    retrieved_value = redis.publisher.get(test_key)
    assert retrieved_value == test_value, "Failed to retrieve test value from Redis"
    
    # Clean up
    redis.publisher.delete(test_key)
    redis.close()

@pytest.mark.asyncio
async def test_simple_pubsub():
    redis_messaging = RedisMessaging()
    channel = "test_channel"
    test_message = {"type": "test", "content": "hello"}
    received = asyncio.Event()
    result = {}

    async def handler(msg):
        print(f"[Test] Received message: {msg}")
        result["msg"] = msg
        received.set()

    # Subscribe first
    task = asyncio.create_task(redis_messaging.subscribe_to_channel(channel, handler))
    await asyncio.sleep(1)
    print(f"[Test] Publishing message to {channel}")
    redis_messaging.publish_message(channel, test_message)
    try:
        await asyncio.wait_for(received.wait(), timeout=10)
        assert result["msg"]["type"] == "test"
        assert result["msg"]["content"] == "hello"
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(test_redis_heartbeat()) 