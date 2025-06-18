from .mongo_client import get_collection
from .utils import to_objectid, to_datetime, privacy_filter
from bson import ObjectId
from datetime import datetime, UTC
from backend.GraphRAG.graphrag.sync import sync_event_to_graph, delete_event_from_graph

def create_event(event_data: dict):
    events = get_collection("events")
    if "user_id" in event_data:
        event_data["user_id"] = to_objectid(event_data["user_id"])
    for k in ["start_time", "created_at", "updated_at"]:
        if k in event_data:
            event_data[k] = to_datetime(event_data[k])
    event_data["created_at"] = event_data.get("created_at", datetime.now(UTC))
    event_data["updated_at"] = datetime.now(UTC)
    result = events.insert_one(event_data)
    event_doc = events.find_one({"_id": result.inserted_id})
    sync_event_to_graph(event_doc)
    return event_doc

def get_event_by_id(event_id):
    events = get_collection("events")
    if isinstance(event_id, str):
        event_id = ObjectId(event_id)
    return events.find_one({"_id": event_id})

def update_event(event_id, update_data: dict):
    events = get_collection("events")
    if isinstance(event_id, str):
        event_id = ObjectId(event_id)
    if "user_id" in update_data:
        update_data["user_id"] = to_objectid(update_data["user_id"])
    for k in ["start_time", "created_at", "updated_at"]:
        if k in update_data:
            update_data[k] = to_datetime(update_data[k])
    update_data["updated_at"] = datetime.now(UTC)
    events.update_one({"_id": event_id}, {"$set": update_data})
    event_doc = events.find_one({"_id": event_id})
    sync_event_to_graph(event_doc)
    return event_doc

def delete_event(event_id):
    events = get_collection("events")
    if isinstance(event_id, str):
        event_id = ObjectId(event_id)
    result = events.delete_one({"_id": event_id})
    delete_event_from_graph(event_id)
    return result

def list_events(filter_dict=None, user_id=None, limit=100):
    events = get_collection("events")
    filter_dict = privacy_filter(filter_dict, user_id)
    return list(events.find(filter_dict).limit(limit)) 