import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from backend.data_services.mongo.mongo_client import get_database

def apply_collection_validations():
    db = get_database()
    # USERS
    user_schema = {
        "bsonType": "object",
        "required": ["email", "auth", "created_at"],
        "properties": {
            "email": {"bsonType": "string", "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"},
            "auth": {
                "bsonType": "object",
                "required": ["provider", "provider_id"],
                "properties": {
                    "provider": {"bsonType": "string"},
                    "provider_id": {"bsonType": "string"}
                }
            },
            "created_at": {"bsonType": "date"},
            "subscription": {
                "bsonType": "object",
                "properties": {
                    "plan_id": {"bsonType": "objectId"},
                    "stripe_customer_id": {"bsonType": "string"},
                    "stripe_subscription_id": {"bsonType": "string"},
                    "status": {"bsonType": "string"},
                    "billing_cycle": {"bsonType": "string"},
                    "current_period_start": {"bsonType": "date"},
                    "current_period_end": {"bsonType": "date"},
                    "usage": {
                        "bsonType": "object",
                        "properties": {
                            "emails_sent": {"bsonType": "int"},
                            "call_minutes": {"bsonType": "int"},
                            "storage_gb": {"bsonType": "double"}
                        }
                    }
                }
            }
        }
    }
    print(db.command({"collMod": "users", "validator": {"$jsonSchema": user_schema}, "validationLevel": "moderate"}))

    # PLANS
    plan_schema = {
        "bsonType": "object",
        "required": ["name", "stripe_price_id", "price", "features"],
        "properties": {
            "name": {"bsonType": "string"},
            "stripe_price_id": {"bsonType": "string"},
            "price": {"bsonType": "double"},
            "features": {"bsonType": "array", "items": {"bsonType": "string"}},
            "billing_cycle": {"bsonType": "string"},
            "description": {"bsonType": "string"}
        }
    }
    print(db.command({"collMod": "plans", "validator": {"$jsonSchema": plan_schema}, "validationLevel": "moderate"}))

    # PAYMENT METHODS
    payment_method_schema = {
        "bsonType": "object",
        "required": ["user_id", "stripe_payment_method_id", "brand", "last4", "exp_month", "exp_year", "created_at"],
        "properties": {
            "user_id": {"bsonType": "objectId"},
            "stripe_payment_method_id": {"bsonType": "string"},
            "customer_id": {"bsonType": "string"},
            "brand": {"bsonType": "string"},
            "last4": {"bsonType": "string"},
            "exp_month": {"bsonType": "int"},
            "exp_year": {"bsonType": "int"},
            "is_default": {"bsonType": "bool"},
            "created_at": {"bsonType": "date"}
        }
    }
    print(db.command({"collMod": "payment_methods", "validator": {"$jsonSchema": payment_method_schema}, "validationLevel": "moderate"}))

    # Add indexes for billing fields
    db.users.create_index({"subscription.stripe_customer_id": 1})
    db.users.create_index({"subscription.status": 1})
    db.payment_methods.create_index({"stripe_payment_method_id": 1})
    db.payment_methods.create_index({"customer_id": 1})
    db.plans.create_index({"stripe_price_id": 1})

    # BUSINESSES
    business_schema = {
        "bsonType": "object",
        "required": ["user_id", "name", "created_at"],
        "properties": {
            "user_id": {"bsonType": "objectId"},
            "name": {"bsonType": "string"},
            "created_at": {"bsonType": "date"}
        }
    }
    print(db.command({"collMod": "businesses", "validator": {"$jsonSchema": business_schema}, "validationLevel": "moderate"}))

    # CONTACTS
    contact_schema = {
        "bsonType": "object",
        "required": ["user_id", "name", "created_at"],
        "properties": {
            "user_id": {"bsonType": "objectId"},
            "name": {"bsonType": "string"},
            "created_at": {"bsonType": "date"}
        }
    }
    print(db.command({"collMod": "contacts", "validator": {"$jsonSchema": contact_schema}, "validationLevel": "moderate"}))

    # CONVERSATIONS
    conversation_schema = {
        "bsonType": "object",
        "required": ["user_id", "status", "created_at"],
        "properties": {
            "user_id": {"bsonType": "objectId"},
            "status": {"bsonType": "string"},
            "created_at": {"bsonType": "date"}
        }
    }
    print(db.command({"collMod": "conversations", "validator": {"$jsonSchema": conversation_schema}, "validationLevel": "moderate"}))

    # MESSAGES
    message_schema = {
        "bsonType": "object",
        "required": ["conversation_id", "timestamp", "content"],
        "properties": {
            "conversation_id": {"bsonType": "objectId"},
            "timestamp": {"bsonType": "date"},
            "content": {"bsonType": "object"}
        }
    }
    print(db.command({"collMod": "messages", "validator": {"$jsonSchema": message_schema}, "validationLevel": "moderate"}))

    # EVENTS
    event_schema = {
        "bsonType": "object",
        "required": ["user_id", "title", "start_time", "created_at"],
        "properties": {
            "user_id": {"bsonType": "objectId"},
            "title": {"bsonType": "string"},
            "start_time": {"bsonType": "date"},
            "created_at": {"bsonType": "date"}
        }
    }
    print(db.command({"collMod": "events", "validator": {"$jsonSchema": event_schema}, "validationLevel": "moderate"}))

    # ASSISTANTS
    assistant_schema = {
        "bsonType": "object",
        "required": ["user_id", "name", "type", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "name": {"bsonType": "string"},
            "type": {"bsonType": "string"},
            "created_at": {"bsonType": "date"}
        }
    }
    print(db.command({"collMod": "assistants", "validator": {"$jsonSchema": assistant_schema}, "validationLevel": "moderate"}))

    # CHANNELS
    channel_schema = {
        "bsonType": "object",
        "required": ["created_at"],
        "properties": {
            "created_at": {"bsonType": "date"},
            # Add more fields as needed
        }
    }
    print(db.command({"collMod": "channels", "validator": {"$jsonSchema": channel_schema}, "validationLevel": "moderate"}))

    # TASKS
    task_schema = {
        "bsonType": "object",
        "required": ["created_at"],
        "properties": {
            "created_at": {"bsonType": "date"},
            # Add more fields as needed
        }
    }
    print(db.command({"collMod": "tasks", "validator": {"$jsonSchema": task_schema}, "validationLevel": "moderate"}))

    # CHATS
    chat_schema = {
        "bsonType": "object",
        "required": ["user_id", "assistant_id", "messages", "created_at"],
        "properties": {
            "user_id": {"bsonType": ["objectId", "string"]},
            "assistant_id": {"bsonType": ["objectId", "string"]},
            "messages": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["sender", "text", "created_at"],
                    "properties": {
                        "sender": {"bsonType": "string"},
                        "text": {"bsonType": "string"},
                        "created_at": {"bsonType": "date"}
                    }
                }
            },
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"}
        }
    }
    print(db.command({"collMod": "chats", "validator": {"$jsonSchema": chat_schema}, "validationLevel": "moderate"}))

if __name__ == "__main__":
    apply_collection_validations() 