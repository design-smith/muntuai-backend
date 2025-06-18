from backend.data_services.mongo.mongo_client import get_collection
from backend.GraphRAG.graphrag.sync import (
    sync_user_to_graph,
    sync_business_to_graph,
    sync_contact_to_graph,
    sync_conversation_to_graph,
    sync_message_to_graph,
    sync_event_to_graph,
    sync_channel_to_graph,
    sync_task_to_graph,
    sync_chat_to_graph,
)

# List of (collection_name, sync_function)
SYNC_TARGETS = [
    ("users", sync_user_to_graph),
    ("businesses", sync_business_to_graph),
    ("contacts", sync_contact_to_graph),
    ("conversations", sync_conversation_to_graph),
    ("messages", sync_message_to_graph),
    ("events", sync_event_to_graph),
    ("channels", sync_channel_to_graph),
    ("tasks", sync_task_to_graph),
    ("chats", sync_chat_to_graph),
]

def sync_all():
    for collection_name, sync_func in SYNC_TARGETS:
        print(f"Syncing collection: {collection_name}")
        collection = get_collection(collection_name)
        count = 0
        for doc in collection.find():
            try:
                sync_func(doc)
                count += 1
            except Exception as e:
                print(f"Failed to sync {collection_name} doc with _id={doc.get('_id')}: {e}")
        print(f"  Synced {count} documents from {collection_name}.")

if __name__ == "__main__":
    sync_all()
    print("All existing MongoDB data has been synced to the graph.") 