from fastapi import APIRouter, HTTPException, Body, Depends
from backend.data_services.mongo.task_repository import (
    list_tasks, get_task_by_id, create_task, update_task, delete_task
)
from bson import ObjectId
from backend.routers.auth_utils import get_current_user

router = APIRouter()

def to_str_id(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

@router.get("/tasks")
def api_list_tasks():
    tasks = list_tasks()
    return {"tasks": [to_str_id(t) for t in tasks]}

@router.get("/tasks/{task_id}")
def api_get_task(task_id: str):
    task = get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return to_str_id(task)

@router.post("/tasks")
def api_create_task(task: dict = Body(...)):
    new_task = create_task(task)
    return to_str_id(new_task)

@router.put("/tasks/{task_id}")
def api_update_task(task_id: str, update: dict = Body(...)):
    updated = update_task(task_id, update)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    return to_str_id(updated)

@router.delete("/tasks/{task_id}")
def api_delete_task(task_id: str):
    result = delete_task(task_id)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True} 