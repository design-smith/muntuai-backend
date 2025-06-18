from fastapi import APIRouter, HTTPException, Body, Depends
from backend.data_services.mongo.message_repository import (
    list_messages, get_message_by_id, create_message, update_message, delete_message
)
from bson import ObjectId
from backend.routers.auth_utils import get_current_user

router = APIRouter()

def to_str_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "conversation_id" in doc and isinstance(doc["conversation_id"], ObjectId):
        doc["conversation_id"] = str(doc["conversation_id"])
    return doc

@router.get("/messages")
def api_list_messages():
    messages = list_messages()
    return {"messages": [to_str_id(m) for m in messages]}

@router.get("/messages/{message_id}")
def api_get_message(message_id: str):
    message = get_message_by_id(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    return to_str_id(message)

@router.post("/messages")
def api_create_message(message: dict = Body(...)):
    new_message = create_message(message)
    return to_str_id(new_message)

@router.put("/messages/{message_id}")
def api_update_message(message_id: str, update: dict = Body(...)):
    updated = update_message(message_id, update)
    return to_str_id(updated)

@router.delete("/messages/{message_id}")
def api_delete_message(message_id: str):
    result = delete_message(message_id)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"deleted": True} 