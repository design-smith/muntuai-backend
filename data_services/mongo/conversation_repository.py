from .mongo_client import get_collection
from .utils import to_objectid, to_datetime, privacy_filter
from bson import ObjectId
from datetime import datetime, UTC
from backend.GraphRAG.graphrag.sync import sync_conversation_to_graph, delete_conversation_from_graph
from backend.data_services.redis_messaging import RedisMessaging
from backend.data_services.mongo.user_repository import UserRepository
import logging
import json
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Initialize Redis messaging
redis_messaging = RedisMessaging()

def format_conversation_for_redis(conversation):
    """
    Format a conversation document for Redis storage.
    Ensures all ObjectIds are converted to strings and dates are properly formatted.
    """
    try:
        formatted = conversation.copy()
        
        # Convert ObjectIds to strings
        if "_id" in formatted:
            formatted["_id"] = str(formatted["_id"])
        if "user_id" in formatted:
            formatted["user_id"] = str(formatted["user_id"])
        
        # Format dates - handle both datetime objects and ISO strings
        if "created_at" in formatted:
            if isinstance(formatted["created_at"], str):
                formatted["created_at"] = formatted["created_at"]
            else:
                formatted["created_at"] = formatted["created_at"].isoformat()
        if "updated_at" in formatted:
            if isinstance(formatted["updated_at"], str):
                formatted["updated_at"] = formatted["updated_at"]
            else:
                formatted["updated_at"] = formatted["updated_at"].isoformat()
        
        # Format message timestamps
        for message in formatted.get("messages", []):
            if "timestamp" in message:
                if isinstance(message["timestamp"], str):
                    message["timestamp"] = message["timestamp"]
                else:
                    message["timestamp"] = message["timestamp"].isoformat()
        
        return formatted
    except Exception as e:
        logger.error(f"Error formatting conversation for Redis: {str(e)}")
        raise

def sync_to_redis(conversation, operation="update"):
    """
    Synchronize conversation data to Redis.
    """
    try:
        formatted_conversation = format_conversation_for_redis(conversation)
        user_id = str(conversation.get("user_id"))
        conversation_id = str(conversation.get("_id"))
        
        # Store in Redis
        redis_key = f"conversation:{user_id}:{conversation_id}"
        
        if operation == "delete":
            # Delete from Redis
            redis_messaging.publisher.delete(redis_key)
        else:
            # Store in Redis
            redis_messaging.publisher.set(redis_key, json.dumps(formatted_conversation))
        
        # Publish to Redis channel
        message_type = {
            "update": "update_conversation",
            "create": "new_conversation",
            "delete": "delete_conversation"
        }.get(operation, "update_conversation")
        
        message = {
            "type": message_type,
            "conversation": formatted_conversation if operation != "delete" else None,
            "conversation_id": conversation_id if operation == "delete" else None
        }
        
        redis_messaging.publish_message(f"conversations:{user_id}", message)
        logger.info(f"Successfully synchronized conversation to Redis: {operation}")
    except Exception as e:
        logger.error(f"Error synchronizing conversation to Redis: {str(e)}")
        raise

def create_conversation(conversation_data: dict):
    """Create a new conversation"""
    try:
        collection = get_collection("conversations")
        
        # Ensure required fields
        if "created_at" not in conversation_data:
            conversation_data["created_at"] = datetime.now(UTC)
        if "updated_at" not in conversation_data:
            conversation_data["updated_at"] = datetime.now(UTC)
        if "status" not in conversation_data:
            conversation_data["status"] = "active"
        if "source" not in conversation_data:
            conversation_data["source"] = "Email"
        if "messages" not in conversation_data:
            conversation_data["messages"] = []
            
        # Ensure messages have timestamps
        for message in conversation_data.get("messages", []):
            if "timestamp" not in message:
                message["timestamp"] = datetime.now(UTC)
        
        # Create conversation in MongoDB
        result = collection.insert_one(conversation_data)
        conversation_data["_id"] = result.inserted_id
        
        # Sync to Redis
        sync_to_redis(conversation_data, "create")
        
        return conversation_data
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise

def get_conversation_by_id(conversation_id):
    """Get a conversation by ID"""
    try:
        collection = get_collection("conversations")
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        return collection.find_one({"_id": conversation_id})
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        raise

def update_conversation(conversation_id: str, update_data: dict):
    """Update a conversation"""
    try:
        collection = get_collection("conversations")
        
        # Add updated_at timestamp if not present
        if "updated_at" not in update_data:
            update_data["updated_at"] = datetime.now(UTC)
        
        # Update in MongoDB
        result = collection.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            return None
            
        # Get updated conversation
        updated = collection.find_one({"_id": ObjectId(conversation_id)})
        
        # Sync to Redis
        sync_to_redis(updated, "update")
        
        return updated
    except Exception as e:
        logger.error(f"Error updating conversation: {str(e)}")
        raise

def delete_conversation(conversation_id):
    """Delete a conversation"""
    try:
        collection = get_collection("conversations")
        if isinstance(conversation_id, str):
            conversation_id = ObjectId(conversation_id)
        
        # Get conversation before deleting to get user_id for Redis operations
        conversation = collection.find_one({"_id": conversation_id})
        if conversation:
            # Delete from MongoDB
            result = collection.delete_one({"_id": conversation_id})
            delete_conversation_from_graph(conversation_id)
            
            # Sync to Redis
            sync_to_redis(conversation, "delete")
            
            return result
        return None
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        raise

class ConversationRepository:
    def __init__(self):
        self.redis_messaging = RedisMessaging()
        self.user_repository = UserRepository()
        self.collection = get_collection("conversations")

    async def list_conversations(self, user_id: str) -> List[Dict]:
        """List all conversations for a user."""
        try:
            # First try to get from Redis
            conversations = await self.redis_messaging.get_conversations(user_id)
            if conversations:
                logger.info(f"Found {len(conversations)} conversations in Redis")
                return conversations

            # If not in Redis, get from MongoDB
            user = await self.user_repository.get_user_by_id(user_id)
            if not user:
                logger.warning(f"No MongoDB user found for user_id: {user_id}")
                return []

            customer_id = str(user.get('_id'))
            conversations = []
            
            # Get conversations from MongoDB
            cursor = self.collection.find({"customer_id": customer_id})
            async for conv in cursor:
                try:
                    # Convert ObjectId fields to strings
                    conv['_id'] = str(conv['_id'])
                    if 'customer_id' in conv:
                        conv['customer_id'] = str(conv['customer_id'])
                    if 'assistant_id' in conv:
                        conv['assistant_id'] = str(conv['assistant_id'])
                    if 'assigned_to' in conv:
                        conv['assigned_to'] = str(conv['assigned_to'])

                    # Format date fields
                    for field in ['created_at', 'updated_at', 'last_message_time']:
                        if field in conv and conv[field]:
                            if isinstance(conv[field], str):
                                continue
                            conv[field] = conv[field].isoformat()

                    # Ensure subject field exists
                    if 'subject' not in conv:
                        conv['subject'] = 'No Subject'

                    # Add user_id for compatibility
                    conv['user_id'] = user_id

                    conversations.append(conv)
                    
                    # Store in Redis for future use
                    sync_to_redis(conv, "update")
                except Exception as e:
                    logger.error(f"Error formatting conversation {conv.get('_id')}: {str(e)}")
                    continue

            logger.info(f"Successfully formatted {len(conversations)} conversations")
            return conversations

        except Exception as e:
            logger.error(f"Error listing conversations: {str(e)}")
            return [] 