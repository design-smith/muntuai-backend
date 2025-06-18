from .mongo_client import get_collection
from bson import ObjectId
from datetime import datetime, UTC
from .utils import privacy_filter
from backend.GraphRAG.graphrag.sync import sync_channel_to_graph, delete_channel_from_graph

def create_channel(channel_data: dict):
    channels = get_collection("channels")
    channel_data["created_at"] = channel_data.get("created_at", datetime.now(UTC))
    channel_data["updated_at"] = datetime.now(UTC)
    result = channels.insert_one(channel_data)
    channel_doc = channels.find_one({"_id": result.inserted_id})
    sync_channel_to_graph(channel_doc)
    return channel_doc

def get_channel_by_id(channel_id):
    channels = get_collection("channels")
    if isinstance(channel_id, str):
        channel_id = ObjectId(channel_id)
    return channels.find_one({"_id": channel_id})

def update_channel(channel_id, update_data: dict):
    channels = get_collection("channels")
    if isinstance(channel_id, str):
        channel_id = ObjectId(channel_id)
    update_data["updated_at"] = datetime.now(UTC)
    channels.update_one({"_id": channel_id}, {"$set": update_data})
    channel_doc = channels.find_one({"_id": channel_id})
    sync_channel_to_graph(channel_doc)
    return channel_doc

def delete_channel(channel_id):
    channels = get_collection("channels")
    if isinstance(channel_id, str):
        channel_id = ObjectId(channel_id)
    result = channels.delete_one({"_id": channel_id})
    delete_channel_from_graph(channel_id)
    return result

def list_channels(filter_dict=None, user_id=None, limit=100):
    channels = get_collection("channels")
    filter_dict = privacy_filter(filter_dict, user_id)
    return list(channels.find(filter_dict).limit(limit)) 