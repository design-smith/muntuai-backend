import redis
import pickle
import os
import time
import logging
from typing import Any, Optional
from redis.exceptions import ConnectionError, TimeoutError

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_USERNAME = os.getenv("REDIS_USERNAME", None)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_SSL = os.getenv("REDIS_SSL", "true").lower() == "true"
REDIS_RETRY_ATTEMPTS = 3
REDIS_RETRY_DELAY = 1  # seconds

class RedisCache:
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB):
        print(f"[RedisCache] Connecting to Redis at {host}:{port} db={db}")
        self.host = host
        self.port = port
        self.db = db
        self.client = None
        self.connect()

    def connect(self):
        """Establish Redis connection with retry logic"""
        for attempt in range(REDIS_RETRY_ATTEMPTS):
            try:
                self.client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    username=REDIS_USERNAME,
                    password=REDIS_PASSWORD,
                    ssl=REDIS_SSL,
                    decode_responses=False,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                
                # Test connection
                self.client.ping()
                logger.info("Successfully connected to Redis")
                return
                
            except (ConnectionError, TimeoutError) as e:
                if attempt < REDIS_RETRY_ATTEMPTS - 1:
                    logger.warning(f"Redis connection attempt {attempt + 1} failed: {str(e)}. Retrying in {REDIS_RETRY_DELAY} seconds...")
                    time.sleep(REDIS_RETRY_DELAY)
                else:
                    logger.error(f"Failed to connect to Redis after {REDIS_RETRY_ATTEMPTS} attempts: {str(e)}")
                    raise

    def ensure_connection(self):
        """Ensure Redis connection is active, reconnect if necessary"""
        try:
            self.client.ping()
            return True
        except (ConnectionError, TimeoutError):
            logger.warning("Redis connection lost. Attempting to reconnect...")
            try:
                self.connect()
                return True
            except Exception as e:
                logger.error(f"Failed to reconnect to Redis: {str(e)}")
                return False

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set a value in Redis with optional TTL"""
        try:
            self.ensure_connection()
            data = pickle.dumps(value)
            if ttl:
                self.client.setex(key, ttl, data)
            else:
                self.client.set(key, data)
            logger.debug(f"Set key {key} in Redis")
        except Exception as e:
            logger.error(f"Error setting key {key} in Redis: {str(e)}")
            raise

    def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis"""
        try:
            self.ensure_connection()
            data = self.client.get(key)
            if data is not None:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting key {key} from Redis: {str(e)}")
            return None

    def delete(self, key: str):
        """Delete a key from Redis"""
        try:
            self.ensure_connection()
            self.client.delete(key)
            logger.debug(f"Deleted key {key} from Redis")
        except Exception as e:
            logger.error(f"Error deleting key {key} from Redis: {str(e)}")
            raise

    def exists(self, key: str) -> bool:
        """Check if a key exists in Redis"""
        try:
            self.ensure_connection()
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Error checking existence of key {key} in Redis: {str(e)}")
            return False

    def flush(self):
        """Flush all keys from the current database"""
        try:
            self.ensure_connection()
            self.client.flushdb()
            logger.info("Flushed Redis database")
        except Exception as e:
            logger.error(f"Error flushing Redis database: {str(e)}")
            raise

    def close(self):
        """Close Redis connection"""
        try:
            if self.client:
                self.client.close()
                logger.info("Closed Redis connection")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {str(e)}")
            raise 