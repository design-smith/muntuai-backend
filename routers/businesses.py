from fastapi import APIRouter, HTTPException, Body, Depends
from backend.data_services.mongo.business_repository import (
    list_businesses, get_business_by_id, create_business, update_business, delete_business
)
from bson import ObjectId
from backend.routers.auth_utils import get_current_user

router = APIRouter()

def to_str_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "user_id" in doc and isinstance(doc["user_id"], ObjectId):
        doc["user_id"] = str(doc["user_id"])
    return doc

@router.get("/businesses")
def api_list_businesses(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    businesses = list_businesses(user_id=user_id)
    return {"businesses": [to_str_id(b) for b in businesses]}

@router.get("/businesses/{business_id}")
def api_get_business(business_id: str, current_user: dict = Depends(get_current_user)):
    business = get_business_by_id(business_id)
    if not business or str(business.get("user_id")) != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Business not found")
    return to_str_id(business)

@router.post("/businesses")
def api_create_business(business: dict = Body(...), current_user: dict = Depends(get_current_user)):
    business["user_id"] = current_user["user_id"]
    new_business = create_business(business)
    return to_str_id(new_business)

@router.put("/businesses/{business_id}")
def api_update_business(business_id: str, update: dict = Body(...), current_user: dict = Depends(get_current_user)):
    business = get_business_by_id(business_id)
    if not business or str(business.get("user_id")) != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Business not found")
    updated = update_business(business_id, update)
    return to_str_id(updated)

@router.delete("/businesses/{business_id}")
def api_delete_business(business_id: str, current_user: dict = Depends(get_current_user)):
    business = get_business_by_id(business_id)
    if not business or str(business.get("user_id")) != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Business not found")
    result = delete_business(business_id)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Business not found")
    return {"deleted": True} 