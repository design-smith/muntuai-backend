from fastapi import APIRouter, HTTPException, Body, Depends
from backend.data_services.mongo.channel_repository import (
    list_channels, get_channel_by_id, create_channel, update_channel, delete_channel
)
from bson import ObjectId
from backend.routers.auth_utils import get_current_user

router = APIRouter()

def to_str_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

@router.get("/channels")
def api_list_channels():
    channels = list_channels()
    return {"channels": [to_str_id(c) for c in channels]}

@router.get("/channels/{channel_id}")
def api_get_channel(channel_id: str):
    channel = get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return to_str_id(channel)

@router.post("/channels")
def api_create_channel(channel: dict = Body(...)):
    new_channel = create_channel(channel)
    return to_str_id(new_channel)

@router.put("/channels/{channel_id}")
def api_update_channel(channel_id: str, update: dict = Body(...)):
    updated = update_channel(channel_id, update)
    return to_str_id(updated)

@router.delete("/channels/{channel_id}")
def api_delete_channel(channel_id: str):
    result = delete_channel(channel_id)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"deleted": True} 