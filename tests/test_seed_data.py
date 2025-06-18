import pytest
from backend.data_services.mongo.mongo_client import get_collection
from backend.data_services.mongo.seed_data import seed

def test_seed_data_creates_user_and_business():
    seed()
    users = list(get_collection("users").find({"email": "testuser@example.com"}))
    assert users, "Test user not found after seeding"
    user = users[0]
    businesses = list(get_collection("businesses").find({"user_id": user["_id"], "name": "Test Business"}))
    assert businesses, "Test business not found after seeding" 