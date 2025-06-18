import sys
import os
import pytest
from bson import ObjectId
from uuid import uuid4
from datetime import datetime, UTC

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.data_services.mongo.user_repository import create_user, update_user, delete_user, get_user_by_id
from backend.data_services.mongo.business_repository import create_business, update_business, delete_business
from backend.data_services.mongo.contact_repository import create_contact, update_contact, delete_contact
from backend.data_services.mongo.conversation_repository import create_conversation, delete_conversation
from backend.data_services.mongo.message_repository import create_message, delete_message
from backend.data_services.mongo.event_repository import create_event, delete_event
from backend.data_services.mongo.channel_repository import create_channel, delete_channel
from backend.data_services.mongo.task_repository import create_task, delete_task
from backend.data_services.mongo.chat_repository import create_chat
from backend.data_services.mongo.mongo_client import get_collection
from backend.GraphRAG.graphrag.db.graph_db import Neo4jWrapper

def delete_all_sync_users():
    """
    Delete all users with 'Sync' in their first_name or name in MongoDB and Neo4j.
    """
    users_collection = get_collection("users")
    mongo_query = {"$or": [
        {"first_name": {"$regex": "Sync", "$options": "i"}},
        {"name": {"$regex": "Sync", "$options": "i"}}
    ]}
    users = list(users_collection.find(mongo_query))
    graph_db = Neo4jWrapper()
    for user in users:
        user_id = str(user["_id"])
        print(f"Deleting user {user_id} ({user.get('first_name', '')} {user.get('last_name', '')})")
        delete_user(user_id)
        graph_db.delete_node("User", {"id": user_id})
    graph_db.close()
    print(f"Deleted {len(users)} users with 'Sync' in their name from MongoDB and Neo4j.")

def test_full_sync_for_all_entities():
    try:
        unique_email = f"sync_test_{uuid4()}@example.com"
        user_doc = create_user({
            "email": unique_email,
            "name": "Sync Test User",
            "first_name": "Sync",
            "last_name": "TestUser",
            "auth": {"provider": "test", "provider_id": f"sync-test-user-{uuid4()}"}
        })
        user_id = str(user_doc["_id"])
        graph_db = Neo4jWrapper()
        assert graph_db.get_node("User", {"id": user_id}), "User node not created"
        business_doc = create_business({"user_id": user_id, "name": "Sync Test Business"})
        business_id = str(business_doc["_id"])
        assert graph_db.get_node("Organization", {"id": business_id}), "Business node not created"
        contact_doc = create_contact({"user_id": user_id, "name": "Sync Test Contact", "email": f"contact_{uuid4()}@example.com"})
        contact_id = str(contact_doc["_id"])
        assert graph_db.get_node("Person", {"id": contact_id}), "Contact node not created"
        conversation_doc = create_conversation({"user_id": user_id, "title": "Sync Test Conversation", "status": "active"})
        conversation_id = str(conversation_doc["_id"])
        assert graph_db.get_node("Thread", {"id": conversation_id}), "Conversation node not created"
        message_doc = create_message({"conversation_id": conversation_id, "timestamp": datetime.now(UTC), "content": {"text": "Hello from sync test!"}})
        message_id = str(message_doc["_id"])
        assert graph_db.get_node("Message", {"id": message_id}), "Message node not created"
        event_doc = create_event({"user_id": user_id, "title": "Sync Test Event", "start_time": datetime.now(UTC), "created_at": datetime.now(UTC)})
        event_id = str(event_doc["_id"])
        assert graph_db.get_node("Event", {"id": event_id}), "Event node not created"
        channel_doc = create_channel({"name": f"Sync Test Channel {uuid4()}", "type": "test", "user_id": user_id, "created_at": datetime.now(UTC)})
        channel_id = str(channel_doc["_id"])
        assert graph_db.get_node("Channel", {"id": channel_id}), "Channel node not created"
        task_doc = create_task({"title": "Sync Test Task", "user_id": user_id, "created_at": datetime.now(UTC)})
        task_id = str(task_doc["_id"])
        assert graph_db.get_node("Task", {"id": task_id}), "Task node not created"
        chat_doc = create_chat({
            "user_id": user_id,
            "assistant_id": str(ObjectId()),
            "messages": [{"sender": user_id, "text": "Hello", "created_at": datetime.now(UTC)}],
            "title": "Sync Test Chat",
            "created_at": datetime.now(UTC)
        })
        chat_id = str(chat_doc["_id"])
        assert graph_db.get_node("Thread", {"id": chat_id}), "Chat node not created"
        # Clean up (delete in reverse order)
        delete_task(task_id)
        delete_channel(channel_id)
        delete_event(event_id)
        delete_message(message_id)
        delete_conversation(conversation_id)
        delete_contact(contact_id)
        delete_business(business_id)
        delete_user(user_id)
        graph_db.close()
    finally:
        # Always clean up all Sync users
        delete_all_sync_users() 