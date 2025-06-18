from fastapi import APIRouter, HTTPException, Request, Depends, Body
from ..data_services.mongo.user_repository import upsert_user_from_supabase, get_user_by_email, UserRepository
from .auth_utils import get_current_user
import logging
import base64
import traceback
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)

user_repository = UserRepository()

def serialize_user(user):
    user = dict(user)
    if '_id' in user:
        user['_id'] = str(user['_id'])
    # Convert datetime fields to isoformat if present
    for key in ['created_at', 'updated_at', 'last_login']:
        if key in user and hasattr(user[key], 'isoformat'):
            user[key] = user[key].isoformat()
    
    # Iterate through all values and encode bytes to base64
    for key, value in user.items():
        logger.debug(f"Serializing user - Key: {key}, Type: {type(value)}")
        if isinstance(value, bytes):
            logger.debug(f"  Found bytes for key {key}. Encoding...")
            user[key] = base64.b64encode(value).decode('utf-8')
        elif isinstance(value, dict):
            logger.debug(f"  Found dict for key {key}. Recursing...")
            user[key] = serialize_user(value) # Recursively serialize nested dictionaries
        elif isinstance(value, list):
            logger.debug(f"  Found list for key {key}. Iterating...")
            processed_list = []
            for item_index, item in enumerate(value):
                logger.debug(f"    List item {item_index} - Type: {type(item)}")
                if isinstance(item, bytes):
                    logger.debug(f"      Found bytes in list for key {key}, item {item_index}. Encoding...")
                    processed_list.append(base64.b64encode(item).decode('utf-8'))
                elif isinstance(item, dict):
                    logger.debug(f"      Found dict in list for key {key}, item {item_index}. Recursing...")
                    processed_list.append(serialize_user(item))
                else:
                    processed_list.append(item)
            user[key] = processed_list

    return user

@router.post("/register_user")
async def register_user(current_user: dict = Depends(get_current_user)):
    try:
        logger.info("/auth/register_user called")
        payload = current_user['user']
        logger.info(f"Payload from JWT: {payload}")
        auth_data = {
            "id": payload["sub"],
            "email": payload["email"],
            "user_metadata": payload.get("user_metadata", {"full_name": payload.get("name", "")})
        }
        logger.info(f"Auth data to upsert: {auth_data}")
        user = upsert_user_from_supabase(auth_data)
        logger.info(f"User upserted: {user}")
        if not user:
            logger.error("User registration failed")
            raise HTTPException(status_code=500, detail="User registration failed")
        user = serialize_user(user)
        is_first_login = user.pop("is_first_login", False)
        return {"user": user, "is_first_login": is_first_login}
    except Exception as e:
        logger.error(f"Exception in /auth/register_user: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/sync_user")
async def sync_user(request: Request):
    try:
        logger.info("/auth/sync_user called")
        auth_data = await request.json()
        logger.info(f"Auth data from request: {auth_data}")
        user = upsert_user_from_supabase(auth_data)
        logger.info(f"User upserted: {user}")
        
        # Add logging to inspect types before serialization
        logger.info("Inspecting user object types before serialization:")
        for key, value in user.items():
            logger.info(f"  Key: {key}, Type: {type(value)}")

        if not user:
            logger.error("User upsert failed")
            raise HTTPException(status_code=500, detail="User upsert failed")
        user = serialize_user(user)
        is_first_login = user.pop("is_first_login", False)
        return {"user": user, "is_first_login": is_first_login}
    except Exception as e:
        logger.error(f"Exception in /auth/sync_user: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/test")
async def test():
    logger.info("/auth/test called")
    return {"message": "Auth API is up!"}

@router.post("/complete_onboarding")
async def complete_onboarding(current_user: dict = Depends(get_current_user)):
    """
    Mark onboarding as completed for the current user.
    """
    payload = current_user['user']
    provider_id = payload["sub"]
    users = __import__('backend.data_services.mongo.user_repository', fromlist=['get_collection']).get_collection("users")
    user = users.find_one({"auth.provider_id": provider_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    users.update_one({"_id": user["_id"]}, {"$set": {"onboarding_completed": True}})
    return {"success": True}

async def get_mongo_user_by_id(user_id: str, email: str = None) -> Optional[Dict]:
    """Get the MongoDB user document for the current authenticated user."""
    try:
        logger.info(f"[get_mongo_user_by_id] Getting MongoDB user for user_id: {user_id}, email: {email}")
        
        # Get user from repository
        user = await user_repository.get_user_by_id(user_id)
        
        if not user:
            logger.warning(f"[get_mongo_user_by_id] No MongoDB user found for user_id: {user_id}, email: {email}")
            return None
            
        logger.info(f"[get_mongo_user_by_id] Successfully retrieved user: {user.get('_id')}. Returning user object.")
        return user
        
    except Exception as e:
        logger.error(f"[get_mongo_user_by_id] Error getting MongoDB user for user_id: {user_id}, email: {email}. Error: {str(e)}")
        logger.error(f"[get_mongo_user_by_id] Traceback: {traceback.format_exc()}")
        return None

@router.get("/me")
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get the current user's profile."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Getting profile for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        return user
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/me")
async def update_current_user_profile(update: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Update the current user's profile."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Updating profile for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Update user profile
        updated_user = await user_repository.update_user(user_id, update)
        return updated_user
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}")
async def get_user_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get a user's profile by ID."""
    try:
        # Get the requesting user's profile to check organization
        requesting_user = await user_repository.get_user_by_id(current_user["user_id"])
        if not requesting_user:
            raise HTTPException(status_code=404, detail="Requesting user not found")
        
        # Get the target user's profile
        target_user = await user_repository.get_user_by_id(user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if users are in the same organization
        if target_user.get("organization_id") != requesting_user.get("organization_id"):
            raise HTTPException(status_code=403, detail="Not authorized to view this user's profile")
        
        return target_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
