from .mongo_client import get_collection
from .utils import to_datetime, privacy_filter
from bson import ObjectId
from datetime import datetime, UTC
from bson.errors import InvalidId
from .business_repository import create_business
from backend.GraphRAG.graphrag.sync import sync_user_to_graph, delete_user_from_graph
import logging
import base64
import json
import traceback
from typing import Optional, Dict, List
from motor.motor_asyncio import AsyncIOMotorClient
import os

logger = logging.getLogger(__name__)

def serialize_integration_credentials(integration_data: dict):
    if integration_data.get("provider") == "gmail" and "credentials" in integration_data:
        creds_data = integration_data["credentials"]
        final_creds_to_process = None

        if isinstance(creds_data, bytes):
            try:
                creds_data_str = creds_data.decode('utf-8')
                final_creds_to_process = json.loads(creds_data_str)
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.warning(f"Attempted to decode and parse bytes credentials, but failed: {e}. Falling back to Base64 encoding.")
                # If decoding or parsing fails, directly use the Base64 encoded raw bytes
                return {**integration_data, "credentials": base64.b64encode(creds_data).decode('utf-8')}
        elif isinstance(creds_data, dict):
            final_creds_to_process = creds_data
        else:
            # If it's already a string or other non-bytes, non-dict type, pass it through
            return integration_data

        if isinstance(final_creds_to_process, dict):
            processed_creds = {}
            for k, v in final_creds_to_process.items():
                if isinstance(v, bytes):
                    processed_creds[k] = base64.b64encode(v).decode('utf-8')
                else:
                    processed_creds[k] = v
            return {**integration_data, "credentials": processed_creds}
    return integration_data

def create_user(user_data: dict):
    users = get_collection("users")
    for k in ["created_at", "updated_at"]:
        if k in user_data:
            user_data[k] = to_datetime(user_data[k])
    user_data["created_at"] = user_data.get("created_at", datetime.now(UTC))
    user_data["updated_at"] = datetime.now(UTC)
    # Ensure first_name and last_name are present
    if "name" in user_data and ("first_name" not in user_data or "last_name" not in user_data):
        parts = user_data["name"].split()
        user_data["first_name"] = parts[0] if parts else ""
        user_data["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
    result = users.insert_one(user_data)
    user_doc = users.find_one({"_id": result.inserted_id})
    sync_user_to_graph(user_doc)
    return user_doc

class UserRepository:
    def __init__(self):
        self.client = AsyncIOMotorClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
        self.db = self.client.muntuai
        self.collection = self.db.users

    async def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get a user by their Supabase user ID."""
        try:
            # First try to find by provider_id
            user = await self.collection.find_one({"provider_id": user_id})
            if user:
                return user

            # If not found by provider_id, try to find by email
            # This is for users created before provider_id was introduced
            user = await self.collection.find_one({"email": user_id})
            if user:
                # Update the user document to include provider_id
                await self.collection.update_one(
                    {"_id": user["_id"]},
                    {"$set": {"provider_id": user_id}}
                )
                return user

            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None

    async def update_user(self, user_id: str, update_data: Dict) -> Optional[Dict]:
        """Update a user's profile."""
        try:
            # Get the user first to ensure they exist
            user = await self.get_user_by_id(user_id)
            if not user:
                return None

            # Update the user document
            result = await self.collection.update_one(
                {"provider_id": user_id},
                {"$set": update_data}
            )

            if result.modified_count == 0:
                return None

            # Get and return the updated user
            return await self.get_user_by_id(user_id)
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            return None

    async def create_user(self, user_data: Dict) -> Optional[Dict]:
        """Create a new user."""
        try:
            result = await self.collection.insert_one(user_data)
            if result.inserted_id:
                return await self.collection.find_one({"_id": result.inserted_id})
            return None
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return None

    async def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        try:
            result = await self.collection.delete_one({"provider_id": user_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting user: {str(e)}")
            return False

    async def list_users(self, user_id: str = None) -> List[Dict]:
        """List all users or users in the same organization."""
        try:
            if user_id:
                # Get the requesting user's organization
                user = await self.get_user_by_id(user_id)
                if not user:
                    return []
                org_id = user.get("organization_id")
                if org_id:
                    cursor = self.collection.find({"organization_id": org_id})
                else:
                    return []
            else:
                cursor = self.collection.find({})

            users = []
            async for user in cursor:
                users.append(user)
            return users
        except Exception as e:
            logger.error(f"Error listing users: {str(e)}")
            return []

def get_user_by_email(email):
    users = get_collection("users")
    return users.find_one({"email": email})

def update_user(user_id, update_data: dict):
    users = get_collection("users")
    # Try ObjectId first, fallback to provider_id
    try:
        obj_id = ObjectId(user_id)
        query = {"_id": obj_id}
    except Exception:
        query = {"auth.provider_id": user_id}
    for k in ["created_at", "updated_at"]:
        if k in update_data:
            update_data[k] = to_datetime(update_data[k])
    update_data["updated_at"] = datetime.now(UTC)
    # If name is present but first_name/last_name are not, split name
    if "name" in update_data and ("first_name" not in update_data or "last_name" not in update_data):
        parts = update_data["name"].split()
        update_data["first_name"] = parts[0] if parts else ""
        update_data["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
    # Only set resume if present
    if "resume" in update_data:
        users.update_one(query, {"$set": {"resume": update_data["resume"], **{k: v for k, v in update_data.items() if k != "resume"}}})
    else:
        users.update_one(query, {"$set": update_data})
    user_doc = users.find_one(query)
    sync_user_to_graph(user_doc)
    return user_doc

def delete_user(user_id):
    users = get_collection("users")
    if isinstance(user_id, str):
        user_id = ObjectId(user_id)
    result = users.delete_one({"_id": user_id})
    delete_user_from_graph(user_id)
    return result

def list_users(filter_dict=None, user_id=None, limit=100):
    users = get_collection("users")
    if user_id:
        # Try to find by auth.provider_id (Supabase UUID)
        filter_dict = {"auth.provider_id": user_id}
    else:
        filter_dict = privacy_filter(filter_dict, user_id)
    return list(users.find(filter_dict).limit(limit))

def upsert_user_from_supabase(auth_data: dict):
    """
    Upsert a user in MongoDB from Supabase auth data.
    Tracks first and last login.
    Sets status to 'unverified' on signup, and 'verified' on first login.
    Returns user document and is_first_login flag.
    Handles duplicate email errors by updating existing user if email exists.
    Always includes onboarding_completed (default False if missing).
    """
    users = get_collection("users")
    now = datetime.now(UTC)
    provider_id = auth_data["id"]
    email = auth_data["email"]
    name = auth_data.get("user_metadata", {}).get("full_name", "")
    first_name = auth_data.get("user_metadata", {}).get("first_name", "")
    last_name = auth_data.get("user_metadata", {}).get("last_name", "")

    logger.info(f"[upsert_user_from_supabase] Processing auth_data: {auth_data}")

    is_first_login = False
    
    # Try to find by provider_id first
    user = users.find_one({"auth.provider_id": provider_id})
    if not user:
        logger.info(f"[upsert_user_from_supabase] User with provider_id {provider_id} not found, trying email: {email}")
        # If not found, try to find by email
        user = users.find_one({"email": email})
        if user:
            logger.info(f"[upsert_user_from_supabase] User found by email {email}. Updating with provider_id: {provider_id}")
            # Update the existing user with the provider_id
            users.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "auth.provider_id": provider_id,
                    "auth.provider": "supabase",
                    "updated_at": now
                }}
            )
            user = users.find_one({"_id": user["_id"]}) # Re-fetch the updated user
        else:
            logger.info(f"[upsert_user_from_supabase] No existing user found, creating new user for email: {email}")
            # Create a new user if no existing user found
            user_data = {
                "email": email,
                "first_name": first_name or (name.split()[0] if name else ""),
                "last_name": last_name or (" ".join(name.split()[1:]) if name else ""),
                "auth": {
                    "provider": "supabase",
                    "provider_id": provider_id
                },
                "created_at": now,
                "updated_at": now,
                "last_login": now,
                "status": "verified", # Assume verified on initial login/sync via Supabase
                "onboarding_completed": False, # Default to False for new users
                "preferences": {"notifications": True, "theme": "dark"} # Default preferences
            }
            result = users.insert_one(user_data)
            user = users.find_one({"_id": result.inserted_id})
            is_first_login = True
            logger.info(f"[upsert_user_from_supabase] New user created with _id: {user.get('_id')}")
    
    if user:
        # Ensure onboarding_completed is always present
        if "onboarding_completed" not in user:
            users.update_one({"_id": user["_id"]}, {"$set": {"onboarding_completed": False}});
            user["onboarding_completed"] = False

        # Update last_login and status if necessary
        if user.get("last_login") is None:
            users.update_one({"_id": user["_id"]}, {"$set": {"last_login": now}});
            user["last_login"] = now

        if user.get("status") == "unverified":
            users.update_one({"_id": user["_id"]}, {"$set": {"status": "verified"}});
            user["status"] = "verified"
            
        # Update user's name details if provided in auth_data
        update_fields = {}
        if first_name and user.get("first_name") != first_name:
            update_fields["first_name"] = first_name
        if last_name and user.get("last_name") != last_name:
            update_fields["last_name"] = last_name
        if name and not (first_name or last_name):
            parts = name.split()
            if parts and user.get("first_name") != parts[0]:
                update_fields["first_name"] = parts[0]
            if len(parts) > 1 and user.get("last_name") != " ".join(parts[1:]):
                update_fields["last_name"] = " ".join(parts[1:])

        if update_fields:
            logger.info(f"[upsert_user_from_supabase] Updating user {user.get('_id')} with new name details: {update_fields}")
            users.update_one({"_id": user["_id"]}, {"$set": update_fields});
            user.update(update_fields)

        # Final check for user data completeness
        if "email" not in user or not user["email"]:
            logger.error(f"[upsert_user_from_supabase] User {user.get('_id')} has no email after upsert!")

    sync_user_to_graph(user) # Always sync to graph after upsert
    user["is_first_login"] = is_first_login # Add this flag for response
    logger.info(f"[upsert_user_from_supabase] Final user document: {user}")
    return user

def get_user_by_pending_connection():
    users = get_collection("users")
    # Find the most recent user with a PENDING composio_integration
    user = users.find_one(
        {"composio_integrations.status": "PENDING"},
        sort=[("composio_integrations.created_at", -1)]
    )
    if not user:
        return None, None
    # Find the most recent pending integration for this user
    pending = None
    for integ in reversed(user.get("composio_integrations", [])):
        if integ.get("status") == "PENDING":
            pending = integ
            break
    if not pending:
        return None, None
    return user, pending.get("provider") 