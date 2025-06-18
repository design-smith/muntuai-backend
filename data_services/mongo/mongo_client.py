import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

MONGO_URI = 'mongodb+srv://nathangandawa:mpQKCbFr7h4H6Va3@muntuai-cluster.kysrdym.mongodb.net/?retryWrites=true&w=majority&appName=muntuai-cluster'
MONGO_DB_NAME = 'muntuai-cluster'

if not MONGO_URI or not MONGO_DB_NAME:
    raise ValueError("MONGO_URI and MONGO_DB_NAME must be set in the .env file.")

_client = None

def get_client():
    global _client
    if _client is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Trigger a server selection to verify connection
            _client.admin.command('ping')
        except ConnectionFailure as e:
            raise RuntimeError(f"Could not connect to MongoDB: {e}")
    return _client

def get_database():
    client = get_client()
    return client[MONGO_DB_NAME]

# Optional: get a collection handle
def get_collection(collection_name):
    db = get_database()
    return db[collection_name] 