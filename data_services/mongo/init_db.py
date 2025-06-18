from mongo_client import get_database
from pymongo.errors import CollectionInvalid
from validation import apply_collection_validations

def create_collections_and_indexes():
    db = get_database()
    collections = [
        "users", "businesses", "contacts", "conversations", "messages", "events", "assistants", "channels", "tasks", "payment_methods", "invoices", "notifications", "user_activity", "analytics", "job_queue", "settings", "email_signatures", "chats", "plans"
    ]
    # Create collections if not exist
    for coll in collections:
        if coll not in db.list_collection_names():
            try:
                db.create_collection(coll)
                print(f"Created collection: {coll}")
            except CollectionInvalid:
                print(f"Collection already exists: {coll}")
        else:
            print(f"Collection exists: {coll}")

    # Indexes for each collection
    # Users
    db.users.create_index({"email": 1}, unique=True)
    db.users.create_index({"auth.provider_id": 1})
    db.users.create_index({"subscription.status": 1})
    db.users.create_index({"last_login": -1})
    # Businesses
    db.businesses.create_index({"user_id": 1})
    db.businesses.create_index({"name": 1})
    db.businesses.create_index({"neo4j_entity_id": 1})
    # Contacts
    db.contacts.create_index({"user_id": 1})
    db.contacts.create_index({"email": 1})
    db.contacts.create_index({"phone": 1})
    db.contacts.create_index({"neo4j_entity_id": 1})
    db.contacts.create_index({"privacy_key": 1})
    db.contacts.create_index({"lead_status.is_lead": 1})
    # Conversations
    db.conversations.create_index({"user_id": 1, "status": 1, "last_message_at": -1})
    db.conversations.create_index({"contact_id": 1})
    db.conversations.create_index({"channel_id": 1})
    db.conversations.create_index({"privacy_key": 1})
    db.conversations.create_index({"neo4j_conversation_id": 1})
    # Messages
    db.messages.create_index({"conversation_id": 1, "timestamp": -1})
    db.messages.create_index({"user_id": 1, "timestamp": -1})
    db.messages.create_index({"sender.id": 1, "timestamp": -1})
    db.messages.create_index({"metadata.is_actionable": 1})
    db.messages.create_index({"privacy_key": 1})
    db.messages.create_index({"neo4j_message_id": 1})
    db.messages.create_index({"metadata.ai_generated": 1})
    # Events
    db.events.create_index({"user_id": 1, "start_time": 1})
    db.events.create_index({"attendees.contact_id": 1})
    db.events.create_index({"related_conversations": 1})
    db.events.create_index({"neo4j_event_id": 1})
    # Other collections
    db.assistants.create_index({"user_id": 1})
    db.channels.create_index({"user_id": 1, "type": 1})
    db.tasks.create_index({"user_id": 1, "status": 1, "due_date": 1})
    # Text indexes
    db.messages.create_index({"content.text": "text"})
    db.conversations.create_index({"context_summary.text": "text"})
    db.contacts.create_index({"name": "text", "bio": "text"})
    # TTL indexes
    db.job_queue.create_index({"created_at": 1}, expireAfterSeconds=604800)  # 7 days
    db.notifications.create_index({"created_at": 1}, expireAfterSeconds=2592000)  # 30 days
    # Chats
    db.chats.create_index({"user_id": 1})
    db.chats.create_index({"assistant_id": 1})
    db.chats.create_index({"created_at": -1})
    # Plans
    db.plans.create_index({"stripe_price_id": 1})
    db.plans.create_index({"name": 1})
    # Seed initial plans
    if db.plans.count_documents({}) == 0:
        db.plans.insert_many([
            {
                "name": "Free",
                "stripe_price_id": "price_free",
                "price": 0.0,
                "features": ["1 user account", "Email channel only", "100 emails", "No phone or social media", "1GB communication storage"],
                "billing_cycle": "monthly",
                "description": "Get started for free. Limited features."
            },
            {
                "name": "Pro Plan",
                "stripe_price_id": "price_pro_monthly",
                "price": 50.0,
                "features": ["1 user account", "All Channels Included: Phone, Email, SMS, Social Media", "500 emails", "1000 call minutes", "Unlimited Social Media Messaging", "10GB communication storage"],
                "billing_cycle": "monthly",
                "description": "Perfect for individual professionals."
            },
            {
                "name": "Pro Plan",
                "stripe_price_id": "price_pro_yearly",
                "price": 120.0,
                "features": ["3 AI assistants (Both customer support and sales)", "3 user accounts included", "2,000 emails", "3000 call minutes", "Unlimited Social Media Messaging", "80GB communication storage"],
                "billing_cycle": "yearly",
                "description": "Growing businesses and teams"
            }
        ])
    print("All collections and indexes created.")

    # Apply JSON Schema validation to collections
    apply_collection_validations()
    print("All collection validations applied.")

if __name__ == "__main__":
    create_collections_and_indexes() 