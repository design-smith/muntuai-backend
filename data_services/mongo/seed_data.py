from data_services.mongo.mongo_client import get_collection
from data_services.mongo.user_repository import create_user, get_user_by_email
from data_services.mongo.business_repository import create_business
from bson import ObjectId

def seed():
    # Test user data
    test_user = {
        "email": "testuser@example.com",
        "name": "Test User",
        "auth": {
            "provider": "seed",
            "provider_id": "seed-testuser"
        }
    }
    # Check if user exists
    user = get_user_by_email(test_user["email"])
    if user:
        print(f"User already exists: {user['email']}")
    else:
        user = create_user(test_user)
        print(f"Inserted test user: {user['email']}")

    # Test business data
    test_business = {
        "user_id": str(user["_id"]),
        "name": "Test Business"
    }
    businesses = get_collection("businesses")
    existing = businesses.find_one({"user_id": ObjectId(user["_id"]), "name": test_business["name"]})
    if existing:
        print(f"Business already exists: {existing['name']}")
    else:
        business = create_business(test_business)
        print(f"Inserted test business: {business['name']}")

if __name__ == "__main__":
    seed() 