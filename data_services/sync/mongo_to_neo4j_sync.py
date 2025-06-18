import os
import time
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson import ObjectId
from threading import Thread
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")

# Import Neo4j wrapper
from GraphRAG.graphrag.db.graph_db import Neo4jWrapper

# Collections to sync
COLLECTIONS = [
    "users", "businesses", "contacts", "conversations", "messages", "events", "assistants", "channels", "tasks"
]

# Helper: map MongoDB collection to Neo4j node label
COLLECTION_LABEL_MAP = {
    "users": "User",
    "businesses": "Business",
    "contacts": "Contact",
    "conversations": "Conversation",
    "messages": "Message",
    "events": "Event",
    "assistants": "Assistant",
    "channels": "Channel",
    "tasks": "Task"
}

# Relationship mapping: (collection, foreign_key) => (from_label, rel_type, to_label, from_field, to_field)
RELATIONSHIP_MAP = [
    # (collection, foreign_key, from_label, rel_type, to_label, from_field, to_field)
    ("contacts", "user_id", "User", "OWNS", "Contact", "id", "id"),
    ("businesses", "user_id", "User", "OWNS", "Business", "id", "id"),
    ("conversations", "user_id", "User", "OWNS", "Conversation", "id", "id"),
    ("conversations", "contact_id", "Contact", "PARTICIPATES_IN", "Conversation", "id", "id"),
    ("messages", "conversation_id", "Conversation", "HAS_MESSAGE", "Message", "id", "id"),
    ("messages", "user_id", "User", "SENT", "Message", "id", "id"),
    ("events", "user_id", "User", "OWNS", "Event", "id", "id"),
    ("assistants", "user_id", "User", "OWNS", "Assistant", "id", "id"),
    ("channels", "user_id", "User", "OWNS", "Channel", "id", "id"),
    ("tasks", "user_id", "User", "OWNS", "Task", "id", "id"),
]

def sync_collection(collection_name, db, neo4j):
    collection = db[collection_name]
    label = COLLECTION_LABEL_MAP[collection_name]
    print(f"[SYNC] Watching collection: {collection_name}")
    try:
        with collection.watch() as stream:
            for change in stream:
                op = change["operationType"]
                doc = change.get("fullDocument")
                doc_id = str(change["documentKey"]["_id"])
                print(f"[SYNC] {collection_name} {op} id={doc_id}")
                if op == "insert" or op == "replace":
                    # Upsert node in Neo4j
                    properties = {**doc, "id": doc_id}
                    neo4j.create_node(label, properties)
                    # Create relationships for foreign keys
                    for (coll, fk, from_label, rel_type, to_label, from_field, to_field) in RELATIONSHIP_MAP:
                        if coll == collection_name and fk in properties and properties[fk]:
                            from_id = str(properties[fk])
                            to_id = doc_id
                            try:
                                neo4j.create_relationship(
                                    from_label, to_label, rel_type,
                                    {from_field: from_id}, {to_field: to_id}
                                )
                            except Exception as e:
                                print(f"[SYNC] Relationship create error: {e}")
                elif op == "update":
                    updated_fields = change["updateDescription"]["updatedFields"]
                    neo4j.update_node(label, {"id": doc_id}, updated_fields)
                elif op == "delete":
                    neo4j.delete_node(label, {"id": doc_id})
                    # Delete relationships for this node
                    for (coll, fk, from_label, rel_type, to_label, from_field, to_field) in RELATIONSHIP_MAP:
                        if coll == collection_name:
                            to_id = doc_id
                            try:
                                neo4j.delete_relationship(
                                    from_label, to_label, rel_type,
                                    {}, {to_field: to_id}
                                )
                            except Exception as e:
                                print(f"[SYNC] Relationship delete error: {e}")
    except Exception as e:
        print(f"[SYNC] Error in {collection_name} sync: {e}")
        time.sleep(5)  # Backoff and retry
        sync_collection(collection_name, db, neo4j)

def main():
    print("[SYNC] Starting MongoDB ↔ Neo4j sync service...")
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    neo4j = Neo4jWrapper()
    threads = []
    for coll in COLLECTIONS:
        t = Thread(target=sync_collection, args=(coll, db, neo4j), daemon=True)
        t.start()
        threads.append(t)
    print("[SYNC] Sync service running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("[SYNC] Shutting down...")
        neo4j.close()

if __name__ == "__main__":
    main() 