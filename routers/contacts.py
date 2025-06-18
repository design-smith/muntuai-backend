from fastapi import APIRouter, HTTPException, Body, Depends
from backend.data_services.mongo.contact_repository import (
    list_contacts, get_contact_by_id, create_contact, update_contact, delete_contact
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

@router.get("/contacts")
def api_list_contacts():
    contacts = list_contacts()
    return {"contacts": [to_str_id(c) for c in contacts]}

@router.get("/contacts/{contact_id}")
def api_get_contact(contact_id: str):
    contact = get_contact_by_id(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return to_str_id(contact)

@router.post("/contacts")
def api_create_contact(contact: dict = Body(...)):
    new_contact = create_contact(contact)
    return to_str_id(new_contact)

@router.put("/contacts/{contact_id}")
def api_update_contact(contact_id: str, update: dict = Body(...)):
    updated = update_contact(contact_id, update)
    if not updated:
        raise HTTPException(status_code=404, detail="Contact not found")
    return to_str_id(updated)

@router.delete("/contacts/{contact_id}")
def api_delete_contact(contact_id: str):
    result = delete_contact(contact_id)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"deleted": True} 