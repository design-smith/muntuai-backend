from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Body, Depends
from typing import Dict, List
from backend.agents.primary_agent import get_primary_agent, process_request
import json
from backend.data_services.mongo.chat_repository import create_chat, add_message, list_chats, get_chat_by_id, update_chat, delete_chat
from bson import ObjectId
from datetime import datetime
from backend.routers.auth_utils import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

# Store active connections, their agents, and conversation history
active_connections: Dict[str, WebSocket] = {}
active_agents: Dict[str, any] = {}
conversation_history: Dict[str, List[dict]] = {}

# Expose active_connections to be used by other modules (like email_sync.py)
# This is a simple global. For more complex apps, consider a pub/sub system or dependency injection.
async def broadcast_message(message: dict):
    for connection in active_connections.values():
        await connection.send_json(message)

# Context window settings
MAX_MESSAGES = 20  # Maximum number of messages to keep in context
MAX_CHARS = 4000   # Maximum characters to keep in context

def get_context_messages(history: List[dict]) -> List[dict]:
    """Get messages within the context window based on both message count and character limit."""
    if not history:
        return []
    
    # Start with the most recent messages
    context_messages = history[-MAX_MESSAGES:]
    
    # Calculate total characters
    total_chars = sum(len(msg.get("text", "")) for msg in context_messages)
    
    # If we're over the character limit, remove oldest messages until we're under
    while total_chars > MAX_CHARS and len(context_messages) > 1:
        removed_msg = context_messages.pop(0)
        total_chars -= len(removed_msg.get("text", ""))
    
    return context_messages

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat."""
    try:
        await websocket.accept()
        while True:
            try:
                # Receive message
                data = await websocket.receive_json()
                message = data.get("message", "")
                user_id = data.get("user_id")
                assistant_id = data.get("assistant_id")

                if not message or not user_id:
                    await websocket.send_json({
                        "error": "Missing required fields"
                    })
                    continue

                # Get the primary agent
                agent = get_primary_agent(
                    assistant_id=assistant_id,
                    user_id=user_id
                )

                # Process the message
                response = process_request(
                    agent=agent,
                    request=message,
                    user_id=user_id,
                    assistant_id=assistant_id
                )

                # Send response
                await websocket.send_json({
                    "response": response
                })

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in websocket: {str(e)}")
                await websocket.send_json({
                    "error": str(e)
                })

    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()

def to_str_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "user_id" in doc and isinstance(doc["user_id"], ObjectId):
        doc["user_id"] = str(doc["user_id"])
    if doc and "assistant_id" in doc and isinstance(doc["assistant_id"], ObjectId):
        doc["assistant_id"] = str(doc["assistant_id"])
    if doc and "messages" in doc:
        for m in doc["messages"]:
            if "_id" in m and isinstance(m["_id"], ObjectId):
                m["_id"] = str(m["_id"])
    return doc

@router.post("/chats")
def api_create_chat(chat: dict = Body(...)):
    # chat must include user_id and assistant_id
    new_chat = create_chat(chat)
    return to_str_id(new_chat)

@router.post("/chats/{chat_id}/messages")
def api_add_message(chat_id: str, message: dict = Body(...)):
    updated_chat = add_message(chat_id, message)
    return to_str_id(updated_chat)

@router.get("/chats")
def api_list_chats(user_id: str = None):
    # Optionally filter by user_id
    chats = list_chats(user_id=user_id) if user_id else list_chats()
    return {"chats": [to_str_id(c) for c in chats]}

@router.get("/chats/{chat_id}")
def api_get_chat(chat_id: str):
    chat = get_chat_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return to_str_id(chat)

@router.put("/api/chats/{chat_id}")
async def api_update_chat(chat_id: str, update: dict = Body(...)):
    """Update a chat's data."""
    try:
        updated = update_chat(chat_id, update)
        if not updated:
            raise HTTPException(status_code=404, detail="Chat not found")
        return to_str_id(updated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/chats/{chat_id}")
async def api_delete_chat(chat_id: str):
    """Delete a chat."""
    try:
        result = delete_chat(chat_id)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Chat not found")
        return {"deleted": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
async def chat_endpoint(request: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Process a chat request."""
    try:
        user_id = current_user["user_id"]
        message = request.get("message")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
            
        # Process the request
        response = await process_request(user_id, message)
        if not response:
            raise HTTPException(status_code=500, detail="Failed to process request")
            
        return {"response": response}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 