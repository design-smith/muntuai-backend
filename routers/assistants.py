from fastapi import APIRouter, HTTPException, Body, Depends
from backend.data_services.mongo.assistant_repository import (
    list_assistants, get_assistant_by_id, create_assistant, update_assistant, delete_assistant
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

@router.get("/assistants")
def api_list_assistants(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    assistants = list_assistants(user_id=user_id)
    return {"assistants": [to_str_id(a) for a in assistants]}

@router.get("/assistants/{assistant_id}")
def api_get_assistant(assistant_id: str, current_user: dict = Depends(get_current_user)):
    assistant = get_assistant_by_id(assistant_id)
    if not assistant or str(assistant.get("user_id")) != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return to_str_id(assistant)

@router.post("/assistants")
def api_create_assistant(assistant: dict = Body(...), current_user: dict = Depends(get_current_user)):
    assistant["user_id"] = current_user["user_id"]
    new_assistant = create_assistant(assistant)
    return to_str_id(new_assistant)

@router.put("/assistants/{assistant_id}")
def api_update_assistant(assistant_id: str, update: dict = Body(...), current_user: dict = Depends(get_current_user)):
    assistant = get_assistant_by_id(assistant_id)
    if not assistant or str(assistant.get("user_id")) != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Assistant not found")
    updated = update_assistant(assistant_id, update)
    return to_str_id(updated)

@router.delete("/assistants/{assistant_id}")
def api_delete_assistant(assistant_id: str, current_user: dict = Depends(get_current_user)):
    assistant = get_assistant_by_id(assistant_id)
    if not assistant or str(assistant.get("user_id")) != current_user["user_id"]:
        raise HTTPException(status_code=404, detail="Assistant not found")
    result = delete_assistant(assistant_id)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return {"deleted": True} 