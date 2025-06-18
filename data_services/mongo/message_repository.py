from .mongo_client import get_collection
from .utils import to_objectid, to_datetime, privacy_filter
from bson import ObjectId
from datetime import datetime, UTC
from backend.GraphRAG.graphrag.sync import sync_message_to_graph, delete_message_from_graph

def create_message(message_data: dict):
    messages = get_collection("messages")
    if "conversation_id" in message_data:
        message_data["conversation_id"] = to_objectid(message_data["conversation_id"])
    for k in ["timestamp", "created_at", "updated_at"]:
        if k in message_data:
            message_data[k] = to_datetime(message_data[k])
    message_data["created_at"] = message_data.get("created_at", datetime.now(UTC))
    message_data["updated_at"] = datetime.now(UTC)
    result = messages.insert_one(message_data)
    message_doc = messages.find_one({"_id": result.inserted_id})
    sync_message_to_graph(message_doc)
    return message_doc

def get_message_by_id(message_id):
    messages = get_collection("messages")
    if isinstance(message_id, str):
        message_id = ObjectId(message_id)
    return messages.find_one({"_id": message_id})

def update_message(message_id, update_data: dict):
    messages = get_collection("messages")
    if isinstance(message_id, str):
        message_id = ObjectId(message_id)
    if "conversation_id" in update_data:
        update_data["conversation_id"] = to_objectid(update_data["conversation_id"])
    for k in ["timestamp", "created_at", "updated_at"]:
        if k in update_data:
            update_data[k] = to_datetime(update_data[k])
    update_data["updated_at"] = datetime.now(UTC)
    messages.update_one({"_id": message_id}, {"$set": update_data})
    message_doc = messages.find_one({"_id": message_id})
    sync_message_to_graph(message_doc)
    return message_doc

def delete_message(message_id):
    messages = get_collection("messages")
    if isinstance(message_id, str):
        message_id = ObjectId(message_id)
    result = messages.delete_one({"_id": message_id})
    delete_message_from_graph(message_id)
    return result

def list_messages(filter_dict=None, user_id=None, limit=100):
    messages = get_collection("messages")
    filter_dict = privacy_filter(filter_dict, user_id)
    return list(messages.find(filter_dict).limit(limit)) 