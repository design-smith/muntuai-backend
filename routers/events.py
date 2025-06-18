from fastapi import APIRouter, HTTPException, Body, Depends
from backend.data_services.mongo.event_repository import (
    list_events, get_event_by_id, create_event, update_event, delete_event
)
from bson import ObjectId
from backend.routers.auth_utils import get_current_user

router = APIRouter()

def to_str_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "user_id" in doc and isinstance(doc["user_id"], ObjectId):
        doc["user_id"] = str(doc["user_id"])
    return doc

@router.get("/events")
def api_list_events():
    events = list_events()
    return {"events": [to_str_id(e) for e in events]}

@router.get("/events/{event_id}")
def api_get_event(event_id: str):
    event = get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return to_str_id(event)

@router.post("/events")
def api_create_event(event: dict = Body(...)):
    new_event = create_event(event)
    return to_str_id(new_event)

@router.put("/events/{event_id}")
def api_update_event(event_id: str, update: dict = Body(...)):
    updated = update_event(event_id, update)
    return to_str_id(updated)

@router.delete("/events/{event_id}")
def api_delete_event(event_id: str):
    result = delete_event(event_id)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"deleted": True} 