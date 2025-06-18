from .mongo_client import get_collection
from .utils import to_datetime, privacy_filter
from bson import ObjectId
from datetime import datetime, UTC
from backend.GraphRAG.graphrag.sync import sync_task_to_graph, delete_task_from_graph

def create_task(task_data: dict):
    tasks = get_collection("tasks")
    for k in ["created_at", "updated_at"]:
        if k in task_data:
            task_data[k] = to_datetime(task_data[k])
    task_data["created_at"] = task_data.get("created_at", datetime.now(UTC))
    task_data["updated_at"] = datetime.now(UTC)
    result = tasks.insert_one(task_data)
    task_doc = tasks.find_one({"_id": result.inserted_id})
    sync_task_to_graph(task_doc)
    return task_doc

def get_task_by_id(task_id):
    tasks = get_collection("tasks")
    if isinstance(task_id, str):
        task_id = ObjectId(task_id)
    return tasks.find_one({"_id": task_id})

def update_task(task_id, update_data: dict):
    tasks = get_collection("tasks")
    if isinstance(task_id, str):
        task_id = ObjectId(task_id)
    for k in ["created_at", "updated_at"]:
        if k in update_data:
            update_data[k] = to_datetime(update_data[k])
    update_data["updated_at"] = datetime.now(UTC)
    tasks.update_one({"_id": task_id}, {"$set": update_data})
    task_doc = tasks.find_one({"_id": task_id})
    sync_task_to_graph(task_doc)
    return task_doc

def delete_task(task_id):
    tasks = get_collection("tasks")
    if isinstance(task_id, str):
        task_id = ObjectId(task_id)
    result = tasks.delete_one({"_id": task_id})
    delete_task_from_graph(task_id)
    return result

def list_tasks(filter_dict=None, user_id=None, limit=100):
    tasks = get_collection("tasks")
    filter_dict = privacy_filter(filter_dict, user_id)
    return list(tasks.find(filter_dict).limit(limit)) 