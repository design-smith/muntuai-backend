import pytest
from pymongo import MongoClient, errors
import os
from dotenv import load_dotenv
from bson import ObjectId
from datetime import datetime, UTC

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

def get_test_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB_NAME]

def test_user_email_unique():
    db = get_test_db()
    db.users.delete_many({"email": {"$in": ["unique@example.com", "unique2@example.com"]}})
    db.users.insert_one({"email": "unique@example.com", "auth": {"provider": "test", "provider_id": "1"}, "created_at": db.command('serverStatus')['localTime']})
    with pytest.raises(errors.DuplicateKeyError):
        db.users.insert_one({"email": "unique@example.com", "auth": {"provider": "test", "provider_id": "2"}, "created_at": db.command('serverStatus')['localTime']})

def test_user_schema_validation():
    db = get_test_db()
    db.users.delete_many({"email": "invalidschema@example.com"})
    # Missing required 'auth' field
    with pytest.raises(errors.WriteError):
        db.users.insert_one({"email": "invalidschema@example.com", "created_at": db.command('serverStatus')['localTime']})

def test_text_index():
    db = get_test_db()
    db.contacts.insert_one({
        "name": "Alice Wonderland",
        "bio": "Loves adventures",
        "user_id": ObjectId(),
        "created_at": datetime.now(UTC)
    })
    results = db.contacts.find({"$text": {"$search": "adventures"}})
    assert any("adventures" in (doc.get("bio") or "") for doc in results)

def test_ttl_index():
    db = get_test_db()
    db.notifications.insert_one({"created_at": db.command('serverStatus')['localTime']})
    # Can't test TTL expiry in real time, but index should exist
    indexes = db.notifications.index_information()
    assert any('expireAfterSeconds' in idx for idx in indexes.values()) 