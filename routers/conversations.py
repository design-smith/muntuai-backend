from fastapi import APIRouter, HTTPException, Body, Depends, WebSocket, WebSocketDisconnect
from backend.data_services.mongo.conversation_repository import ConversationRepository
from backend.data_services.mongo.user_repository import UserRepository
from bson import ObjectId
from backend.routers.auth_utils import get_current_user
from backend.data_services.redis_messaging import RedisMessaging
from dateutil.parser import isoparse
import logging
import json
import asyncio
from typing import Dict, Set

logger = logging.getLogger(__name__)
router = APIRouter(tags=["conversations"])

# Store active WebSocket connections
active_connections: Dict[str, Set[WebSocket]] = {}

# Initialize repositories
conversation_repository = ConversationRepository()
user_repository = UserRepository()
redis_messaging = RedisMessaging()

def parse_datetime_fields(conversation: dict):
    """Convert ISO string dates to datetime objects"""
    # Convert top-level datetime fields
    if isinstance(conversation.get("created_at"), str):
        conversation["created_at"] = isoparse(conversation["created_at"])
    if isinstance(conversation.get("updated_at"), str):
        conversation["updated_at"] = isoparse(conversation["updated_at"])

    # Convert message timestamps
    for message in conversation.get("messages", []):
        if isinstance(message.get("timestamp"), str):
            message["timestamp"] = isoparse(message["timestamp"])

    return conversation

def to_str_id(doc):
    """Convert ObjectIds to strings in the response"""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "user_id" in doc and isinstance(doc["user_id"], ObjectId):
        doc["user_id"] = str(doc["user_id"])
    return doc

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = None
    redis_task = None
    
    try:
        # Get user_id from query parameters
        user_id = websocket.query_params.get("user_id")
        if not user_id:
            await websocket.close(code=4000, reason="No user_id provided")
            return
            
        # Add connection to active connections
        if user_id not in active_connections:
            active_connections[user_id] = set()
        active_connections[user_id].add(websocket)
        
        # Subscribe to Redis channel for this user
        channel = f"conversations:{user_id}"
        logger.info(f"WebSocket connection established for user {user_id}")
        
        async def handle_redis_message(message):
            try:
                # Forward Redis message to WebSocket
                await websocket.send_json(message)
                logger.debug(f"Forwarded message to WebSocket for user {user_id}: {message}")
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {str(e)}")
                # If we can't send to this WebSocket, remove it from active connections
                if user_id in active_connections:
                    active_connections[user_id].remove(websocket)
                    if not active_connections[user_id]:
                        del active_connections[user_id]
                raise
        
        # Start Redis subscription in background
        redis_task = asyncio.create_task(
            redis_messaging.subscribe_to_channel(channel, handle_redis_message)
        )
        
        try:
            # Keep connection alive and handle incoming messages
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                    # Handle test messages
                    if data.get("type") == "test":
                        await websocket.send_json(data)
                    # Handle any other incoming messages from client if needed
                except asyncio.TimeoutError:
                    # No message received within timeout, continue waiting
                    continue
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected for user {user_id}")
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message: {str(e)}")
                    break
        finally:
            # Clean up
            if user_id in active_connections:
                active_connections[user_id].remove(websocket)
                if not active_connections[user_id]:
                    del active_connections[user_id]
            if redis_task:
                redis_task.cancel()
                try:
                    await redis_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error cancelling Redis task: {str(e)}")
            
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        if websocket.client_state.CONNECTED:
            await websocket.close(code=4000, reason=str(e))

@router.get("/conversations")
async def api_list_conversations(current_user: dict = Depends(get_current_user)):
    """List all conversations for the current user."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Listing conversations for user_id: {user_id}, email: {email}")
        
        # First try to get from Redis
        conversations = await redis_messaging.get_conversations(user_id)
        if conversations:
            logger.info(f"Found {len(conversations)} conversations in Redis")
            return {"conversations": conversations}
        
        # If not in Redis, get from MongoDB
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        conversations = await conversation_repository.list_conversations(user_id=user_id)
        logger.info(f"Found {len(conversations)} conversations for user {user_id}")
        
        # Store conversations in Redis for future use
        for conversation in conversations:
            redis_key = f"conversation:{user_id}:{conversation['_id']}"
            redis_messaging.publisher.set(redis_key, json.dumps(to_str_id(conversation)))
        
        return {"conversations": conversations}
    except Exception as e:
        logger.error(f"Error listing conversations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-conversations")
async def test_conversations_endpoint():
    print("DEBUG: --- TEST CONVERSATIONS ENDPOINT HIT ---")
    return {"message": "Test conversations endpoint hit successfully!"}

@router.get("/debug-auth-test")
async def debug_auth_test(current_user: dict = Depends(get_current_user)):
    print("DEBUG: --- DEBUG AUTH TEST ENDPOINT HIT ---")
    print(f"DEBUG: Current user from debug auth test: {current_user}")
    return {"message": "Auth test successful", "user": current_user}

@router.get("/conversations/{conversation_id}")
async def api_get_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific conversation by ID."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        
        # First try to get from Redis
        redis_key = f"conversation:{user_id}:{conversation_id}"
        conversation_data = redis_messaging.publisher.get(redis_key)
        if conversation_data:
            conversation = json.loads(conversation_data)
            return conversation
        
        # If not in Redis, get from MongoDB
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        conversation = await conversation_repository.get_conversation_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        if str(conversation.get("user_id")) != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
        
        # Store in Redis for future use
        redis_messaging.publisher.set(redis_key, json.dumps(to_str_id(conversation)))
        
        return to_str_id(conversation)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/conversations")
async def api_create_conversation(conversation: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Create a new conversation."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Parse datetime fields before creating conversation
        conversation = parse_datetime_fields(conversation)
        
        # Ensure required fields
        if "source" not in conversation:
            conversation["source"] = "Email"
        if "status" not in conversation:
            conversation["status"] = "active"
        
        # Create conversation
        new_conversation = await conversation_repository.create_conversation(conversation)
        
        # Store in Redis
        redis_key = f"conversation:{user_id}:{new_conversation['_id']}"
        redis_messaging.publisher.set(redis_key, json.dumps(to_str_id(new_conversation)))
        
        # Publish to Redis channel
        redis_messaging.publish_message(
            f"conversations:{user_id}",
            {
                "type": "new_conversation",
                "conversation": to_str_id(new_conversation)
            }
        )
        
        return to_str_id(new_conversation)
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/conversations/{conversation_id}")
async def api_update_conversation(conversation_id: str, update: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Update a conversation."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Parse datetime fields in update data
        update = parse_datetime_fields(update)
        
        # Get existing conversation
        conversation = await conversation_repository.get_conversation_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Verify ownership
        if str(conversation.get("user_id")) != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Not authorized to update this conversation")
        
        # Update conversation
        updated = await conversation_repository.update_conversation(conversation_id, update)
        
        # Update in Redis
        redis_key = f"conversation:{user_id}:{conversation_id}"
        redis_messaging.publisher.set(redis_key, json.dumps(to_str_id(updated)))
        
        # Publish to Redis channel
        redis_messaging.publish_message(
            f"conversations:{user_id}",
            {
                "type": "update_conversation",
                "conversation": to_str_id(updated)
            }
        )
        
        return to_str_id(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/conversations/{conversation_id}")
async def api_delete_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a conversation."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Get existing conversation
        conversation = await conversation_repository.get_conversation_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Verify ownership
        if str(conversation.get("user_id")) != str(user["_id"]):
            raise HTTPException(status_code=403, detail="Not authorized to delete this conversation")
        
        # Delete conversation
        result = await conversation_repository.delete_conversation(conversation_id)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Delete from Redis
        redis_key = f"conversation:{user_id}:{conversation_id}"
        redis_messaging.publisher.delete(redis_key)
        
        # Publish to Redis channel
        redis_messaging.publish_message(
            f"conversations:{user_id}",
            {
                "type": "delete_conversation",
                "conversation_id": conversation_id
            }
        )
        
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 