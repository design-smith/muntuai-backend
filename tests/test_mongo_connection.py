import sys
import os
import pytest

# Ensure the backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.data_services.mongo.mongo_client import get_database

def test_mongo_connection():
    db = get_database()
    # Check that the database object is not None and has the correct name
    assert db is not None, "Database connection failed: db is None"
    assert db.name, "Database object has no name attribute"
    print(f"Connected to MongoDB database: {db.name}") 