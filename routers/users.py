from fastapi import APIRouter, HTTPException, Body, Depends
from backend.data_services.mongo.user_repository import UserRepository
from backend.routers.auth_utils import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["users"])

# Initialize repository
user_repository = UserRepository()

@router.get("/users/me")
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get the current user's profile."""
    try:
        user_id = current_user["user_id"]
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/users/me")
async def update_current_user_profile(update: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Update the current user's profile."""
    try:
        user_id = current_user["user_id"]
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Update user profile
        updated_user = await user_repository.update_user(user_id, update)
        if not updated_user:
            raise HTTPException(status_code=500, detail="Failed to update user profile")
            
        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{user_id}")
async def get_user_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get a user's profile by ID."""
    try:
        # Check if user has permission to view this profile
        if user_id != current_user["user_id"]:
            # TODO: Add permission check here
            raise HTTPException(status_code=403, detail="Not authorized to view this profile")
            
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users")
def api_create_user(user: dict = Body(...)):
    new_user = create_user(user)
    return to_str_id(new_user)

@router.put("/users/{user_id}")
def api_update_user(user_id: str, update: dict = Body(...)):
    # Accept first_name, last_name, title, email, phone, etc.
    updated = update_user(user_id, update)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return to_str_id(updated)

@router.delete("/users/{user_id}")
def api_delete_user(user_id: str):
    result = delete_user(user_id)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True} 

@router.post("/users/{user_id}/resume")
async def update_user_resume(user_id: str, resume: dict, current_user: dict = Depends(get_current_user)):
    """
    Update the resume field for a user.
    """
    updated = update_user(user_id, {"resume": resume})
    # Serialize ObjectId and datetimes
    def serialize_user(user):
        user = dict(user)
        if '_id' in user:
            user['_id'] = str(user['_id'])
        for key in ['created_at', 'updated_at', 'last_login']:
            if key in user and hasattr(user[key], 'isoformat'):
                user[key] = user[key].isoformat()
        return user
    return {"user": serialize_user(updated)} 