import redis
import json
import os
from typing import Any, Optional, Callable
import logging
import time
from redis.exceptions import ConnectionError, TimeoutError
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis Cloud configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis-10492.c238.us-central1-2.gce.redns.redis-cloud.com")
REDIS_PORT = int(os.getenv("REDIS_PORT", 10492))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "your-redis-password")
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_SSL = os.getenv("REDIS_SSL", "true").lower() == "true"
REDIS_RETRY_ATTEMPTS = 3
REDIS_RETRY_DELAY = 1  # seconds

class RedisMessaging:
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, db=REDIS_DB):
        logger.info(f"[RedisMessaging] Initializing connection to Redis at {host}:{port} db={db}")
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.publisher = None
        self.subscriber = None
        self.pubsub = None
        self.connect()

    def connect(self):
        """Establish Redis connections with retry logic"""
        for attempt in range(REDIS_RETRY_ATTEMPTS):
            try:
                logger.info(f"[RedisMessaging] Connection attempt {attempt + 1}/{REDIS_RETRY_ATTEMPTS}")
                
                # Initialize publisher connection
                logger.info("[RedisMessaging] Initializing publisher connection...")
                self.publisher = redis.Redis(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    db=self.db,
                    ssl=REDIS_SSL,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                
                # Initialize subscriber connection
                logger.info("[RedisMessaging] Initializing subscriber connection...")
                self.subscriber = redis.Redis(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    db=self.db,
                    ssl=REDIS_SSL,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                
                # Initialize pubsub
                logger.info("[RedisMessaging] Initializing pubsub...")
                self.pubsub = self.subscriber.pubsub()
                
                # Test connection
                logger.info("[RedisMessaging] Testing connection with PING...")
                self.publisher.ping()
                logger.info("[RedisMessaging] Successfully connected to Redis Cloud")
                return
                
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"[RedisMessaging] Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < REDIS_RETRY_ATTEMPTS - 1:
                    logger.warning(f"[RedisMessaging] Retrying in {REDIS_RETRY_DELAY} seconds...")
                    time.sleep(REDIS_RETRY_DELAY)
                else:
                    logger.error(f"[RedisMessaging] Failed to connect after {REDIS_RETRY_ATTEMPTS} attempts")
                    raise

    def ensure_connection(self):
        """Ensure Redis connection is active, reconnect if necessary"""
        try:
            self.publisher.ping()
            return True
        except (ConnectionError, TimeoutError):
            logger.warning("[RedisMessaging] Connection lost. Attempting to reconnect...")
            try:
                self.connect()
                return True
            except Exception as e:
                logger.error(f"[RedisMessaging] Failed to reconnect: {str(e)}")
                return False

    def publish_message(self, channel: str, message: dict):
        """Publish a message to a Redis channel."""
        try:
            self.ensure_connection()
            logger.info(f"[RedisMessaging] Publishing to channel {channel}: {json.dumps(message)}")
            self.publisher.publish(channel, json.dumps(message))
            logger.info(f"[RedisMessaging] Successfully published message to channel {channel}")
        except Exception as e:
            logger.error(f"[RedisMessaging] Error publishing message: {str(e)}")
            raise

    async def subscribe_to_channel(self, channel: str, message_handler: Callable):
        """Subscribe to a Redis channel and process incoming messages."""
        try:
            logger.info(f"[RedisMessaging] Subscribing to channel: {channel}")
            self.ensure_connection()
            
            # Create a new pubsub instance for this subscription
            self.pubsub = self.publisher.pubsub()
            logger.info("[RedisMessaging] Created pubsub instance")
            
            # Subscribe to the channel
            self.pubsub.subscribe(channel)
            logger.info(f"[RedisMessaging] Subscribed to channel {channel}")
            
            # Wait for subscription confirmation
            while True:
                message = self.pubsub.get_message(ignore_subscribe_messages=False)
                if message and message['type'] == 'subscribe':
                    logger.info(f"[RedisMessaging] Subscription confirmed for channel {channel}")
                    break
                await asyncio.sleep(0.1)
            
            # Process messages
            while True:
                try:
                    logger.debug(f"[RedisMessaging] Waiting for message on channel {channel}")
                    message = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                    if message and message['type'] == 'message':
                        logger.info(f"[RedisMessaging] Received message on channel {channel}: {message['data']}")
                        data = json.loads(message['data'])
                        await message_handler(data)
                except Exception as e:
                    logger.error(f"[RedisMessaging] Error processing message: {str(e)}")
                    if not self.ensure_connection():
                        logger.error("[RedisMessaging] Failed to reconnect, retrying...")
                        await asyncio.sleep(1)
                        continue
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"[RedisMessaging] Error in subscribe_to_channel: {str(e)}")
            raise

    async def get_conversations(self, user_id: str) -> list:
        """
        Get all conversations for a user from Redis.
        """
        try:
            self.ensure_connection()
            pattern = f"conversation:{user_id}:*"
            keys = self.publisher.keys(pattern)
            conversations = []
            
            for key in keys:
                try:
                    data = self.publisher.get(key)
                    if data:
                        conversation = json.loads(data)
                        conversations.append(conversation)
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding conversation data: {str(e)}")
                    continue
                    
            return conversations
        except Exception as e:
            logger.error(f"Error getting conversations from Redis: {str(e)}")
            return []

    def unsubscribe_from_channel(self, channel: str):
        """Unsubscribe from a Redis channel."""
        try:
            self.ensure_connection()
            logger.info(f"[RedisMessaging] Unsubscribing from channel {channel}")
            self.pubsub.unsubscribe(channel)
            logger.info(f"[RedisMessaging] Successfully unsubscribed from channel {channel}")
        except Exception as e:
            logger.error(f"[RedisMessaging] Error unsubscribing from channel: {str(e)}")
            raise

    def close(self):
        """Close Redis connections."""
        try:
            logger.info("[RedisMessaging] Closing Redis connections...")
            if self.pubsub:
                self.pubsub.close()
            if self.publisher:
                self.publisher.close()
            if self.subscriber:
                self.subscriber.close()
            logger.info("[RedisMessaging] Successfully closed all Redis connections")
        except Exception as e:
            logger.error(f"[RedisMessaging] Error closing Redis connections: {str(e)}")
            raise 