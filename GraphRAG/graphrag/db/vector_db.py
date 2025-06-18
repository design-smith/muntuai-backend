from qdrant_client import QdrantClient
from qdrant_client.http import models
from ..config import get_settings
from typing import List, Dict, Any

PERSON_VECTOR_SIZE = 768  # Adjust as needed
ORG_VECTOR_SIZE = 768
MSG_VECTOR_SIZE = 768
EVENT_VECTOR_SIZE = 768
LOC_VECTOR_SIZE = 768

class QdrantWrapper:
    def __init__(self):
        settings = get_settings()
        self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    def create_person_collection(self):
        self.client.recreate_collection(
            collection_name="Person",
            vectors_config=models.VectorParams(size=PERSON_VECTOR_SIZE, distance=models.Distance.COSINE),
            payload_schema={
                "id": models.PayloadSchemaType.KEYWORD,
                "name": models.PayloadSchemaType.TEXT,
                "email": models.PayloadSchemaType.KEYWORD,
                "phone": models.PayloadSchemaType.KEYWORD,
                "title": models.PayloadSchemaType.TEXT,
                "organization_id": models.PayloadSchemaType.KEYWORD,
                "first_contact_date": models.PayloadSchemaType.DATETIME,
                "last_contact_date": models.PayloadSchemaType.DATETIME,
                "source": models.PayloadSchemaType.KEYWORD,
                "embedding_id": models.PayloadSchemaType.KEYWORD,
            }
        )

    def create_organization_collection(self):
        self.client.recreate_collection(
            collection_name="Organization",
            vectors_config=models.VectorParams(size=ORG_VECTOR_SIZE, distance=models.Distance.COSINE),
            payload_schema={
                "id": models.PayloadSchemaType.KEYWORD,
                "name": models.PayloadSchemaType.TEXT,
                "type": models.PayloadSchemaType.KEYWORD,
                "website": models.PayloadSchemaType.KEYWORD,
                "description": models.PayloadSchemaType.TEXT,
                "location": models.PayloadSchemaType.TEXT,
                "embedding_id": models.PayloadSchemaType.KEYWORD,
            }
        )
    
    def create_task_collection(self):
        self.client.recreate_collection(
            collection_name="Task",
            vectors_config=models.VectorParams(size=MSG_VECTOR_SIZE, distance=models.Distance.COSINE),
            payload_schema={
                "id": models.PayloadSchemaType.KEYWORD,
                "title": models.PayloadSchemaType.TEXT,
                "status": models.PayloadSchemaType.KEYWORD,
                "created_date": models.PayloadSchemaType.DATETIME,
                "source_type": models.PayloadSchemaType.KEYWORD,
                "description": models.PayloadSchemaType.TEXT,
                "priority": models.PayloadSchemaType.KEYWORD,
                "due_date": models.PayloadSchemaType.DATETIME,
                "completion_date": models.PayloadSchemaType.DATETIME,
                "horizon": models.PayloadSchemaType.KEYWORD,
                "recurrence": models.PayloadSchemaType.KEYWORD,
                "estimated_time": models.PayloadSchemaType.FLOAT,
                "tags": models.PayloadSchemaType.KEYWORD,
                "confidence_score": models.PayloadSchemaType.FLOAT,
                "assignee_id": models.PayloadSchemaType.KEYWORD,
                "creator_id": models.PayloadSchemaType.KEYWORD,
                "is_actionable": models.PayloadSchemaType.BOOL,
                "reminder_date": models.PayloadSchemaType.DATETIME,
                "embedding_id": models.PayloadSchemaType.KEYWORD,
            }
        )

    def create_channel_collection(self):
        self.client.recreate_collection(
            collection_name="Channel",
            vectors_config=models.VectorParams(size=MSG_VECTOR_SIZE, distance=models.Distance.COSINE),
            payload_schema={
                "id": models.PayloadSchemaType.KEYWORD,
                "name": models.PayloadSchemaType.TEXT,
                "type": models.PayloadSchemaType.KEYWORD,
                "provider": models.PayloadSchemaType.KEYWORD,
                "is_connected": models.PayloadSchemaType.BOOL,
                "connection_status": models.PayloadSchemaType.KEYWORD,
                "last_synced": models.PayloadSchemaType.DATETIME,
                "credentials_id": models.PayloadSchemaType.KEYWORD,
                "settings": models.PayloadSchemaType.JSON,
                "embedding_id": models.PayloadSchemaType.KEYWORD,
            }
        )

    def create_thread_collection(self):
        self.client.recreate_collection(
            collection_name="Thread",
            vectors_config=models.VectorParams(size=MSG_VECTOR_SIZE, distance=models.Distance.COSINE),
            payload_schema={
                "id": models.PayloadSchemaType.KEYWORD,
                "title": models.PayloadSchemaType.TEXT,
                "status": models.PayloadSchemaType.KEYWORD,
                "created_date": models.PayloadSchemaType.DATETIME,
                "last_updated": models.PayloadSchemaType.DATETIME,
                "channel_id": models.PayloadSchemaType.KEYWORD,
                "external_id": models.PayloadSchemaType.KEYWORD,
                "participants_count": models.PayloadSchemaType.INTEGER,
                "message_count": models.PayloadSchemaType.INTEGER,
                "embedding_id": models.PayloadSchemaType.KEYWORD,
            }
        )

    def create_message_collection(self):
        self.client.recreate_collection(
            collection_name="Message",
            vectors_config=models.VectorParams(size=MSG_VECTOR_SIZE, distance=models.Distance.COSINE),
            payload_schema={
                "id": models.PayloadSchemaType.KEYWORD,
                "content": models.PayloadSchemaType.TEXT,
                "sender_id": models.PayloadSchemaType.KEYWORD,
                "channel_id": models.PayloadSchemaType.KEYWORD,
                "thread_id": models.PayloadSchemaType.KEYWORD,
                "timestamp": models.PayloadSchemaType.DATETIME,
                "read_status": models.PayloadSchemaType.KEYWORD,
                "has_attachments": models.PayloadSchemaType.BOOL,
                "sentiment": models.PayloadSchemaType.FLOAT,
                "intent": models.PayloadSchemaType.KEYWORD,
                "is_actionable": models.PayloadSchemaType.BOOL,
                "reply_to_id": models.PayloadSchemaType.KEYWORD,
                "embedding_id": models.PayloadSchemaType.KEYWORD,
            }
        )

    def create_event_collection(self):
        self.client.recreate_collection(
            collection_name="Event",
            vectors_config=models.VectorParams(size=EVENT_VECTOR_SIZE, distance=models.Distance.COSINE),
            payload_schema={
                "id": models.PayloadSchemaType.KEYWORD,
                "title": models.PayloadSchemaType.TEXT,
                "description": models.PayloadSchemaType.TEXT,
                "start_time": models.PayloadSchemaType.DATETIME,
                "end_time": models.PayloadSchemaType.DATETIME,
                "location": models.PayloadSchemaType.TEXT,
                "embedding_id": models.PayloadSchemaType.KEYWORD,
            }
        )

    def create_location_collection(self):
        self.client.recreate_collection(
            collection_name="Location",
            vectors_config=models.VectorParams(size=LOC_VECTOR_SIZE, distance=models.Distance.COSINE),
            payload_schema={
                "id": models.PayloadSchemaType.KEYWORD,
                "name": models.PayloadSchemaType.TEXT,
                "address": models.PayloadSchemaType.TEXT,
                "coordinates": models.PayloadSchemaType.GEO,
                "type": models.PayloadSchemaType.KEYWORD,
                "embedding_id": models.PayloadSchemaType.KEYWORD,
            }
        )

    def upsert_embedding(self, collection: str, id: str, vector: List[float], payload: Dict[str, Any]):
        self.client.upsert(
            collection_name=collection,
            points=models.Batch(
                ids=[id],
                vectors=[vector],
                payloads=[payload]
            )
        )

    def get_embedding(self, collection: str, id: str):
        result = self.client.retrieve(collection_name=collection, ids=[id])
        return result
    
    def search_vectors(self, collection_name: str, query_vector: List[float], limit: int = 5):
        search_result = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit
        )
        return search_result 

if __name__ == "__main__":
    print("Testing Qdrant connectivity...")
    try:
        db = QdrantWrapper()
        collections = db.client.get_collections()
        print("Connection successful! Collections:", collections)
    except Exception as e:
        print("Connection failed:", e) 