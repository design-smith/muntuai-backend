from .mongo_client import get_collection
from .utils import to_objectid, to_datetime, privacy_filter
from bson import ObjectId
from datetime import datetime, UTC

def create_assistant(assistant_data: dict):
    assistants = get_collection("assistants")
    if "user_id" in assistant_data:
        assistant_data["user_id"] = to_objectid(assistant_data["user_id"])
    for k in ["created_at", "updated_at"]:
        if k in assistant_data:
            assistant_data[k] = to_datetime(assistant_data[k])
    assistant_data["created_at"] = assistant_data.get("created_at", datetime.now(UTC))
    assistant_data["updated_at"] = datetime.now(UTC)
    result = assistants.insert_one(assistant_data)
    return assistants.find_one({"_id": result.inserted_id})

def get_assistant_by_id(assistant_id):
    assistants = get_collection("assistants")
    if isinstance(assistant_id, str):
        assistant_id = ObjectId(assistant_id)
    return assistants.find_one({"_id": assistant_id})

def update_assistant(assistant_id, update_data: dict):
    assistants = get_collection("assistants")
    if isinstance(assistant_id, str):
        assistant_id = ObjectId(assistant_id)
    if "user_id" in update_data:
        update_data["user_id"] = to_objectid(update_data["user_id"])
    for k in ["created_at", "updated_at"]:
        if k in update_data:
            update_data[k] = to_datetime(update_data[k])
    update_data["updated_at"] = datetime.now(UTC)
    assistants.update_one({"_id": assistant_id}, {"$set": update_data})
    return assistants.find_one({"_id": assistant_id})

def delete_assistant(assistant_id):
    assistants = get_collection("assistants")
    if isinstance(assistant_id, str):
        assistant_id = ObjectId(assistant_id)
    return assistants.delete_one({"_id": assistant_id})

def list_assistants(filter_dict=None, user_id=None, limit=100):
    assistants = get_collection("assistants")
    filter_dict = privacy_filter(filter_dict, user_id)
    return list(assistants.find(filter_dict).limit(limit))

def get_all_assistants():
    assistants = get_collection("assistants")
    return list(assistants.find({})) 