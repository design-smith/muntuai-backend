import os
import hmac
import hashlib
from fastapi import APIRouter, Request, HTTPException, Header, Depends, Body
from fastapi.responses import JSONResponse
from ..data_services.mongo.user_repository import UserRepository
from ..integrations.composio.ingestion_pipeline import process_email_payload
from ..routers.auth_utils import get_current_user
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhooks"])

COMPOSIO_WEBHOOK_SECRET = os.getenv("COMPOSIO_WEBHOOK_SECRET")

# Initialize repositories
user_repository = UserRepository()

# Utility to validate HMAC signature
def validate_hmac_signature(request: Request, body: bytes) -> bool:
    signature = request.headers.get("X-Composio-Signature")
    if not signature or not COMPOSIO_WEBHOOK_SECRET:
        return False
    computed = hmac.new(COMPOSIO_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, computed)

@router.post("/webhooks/email")
async def email_webhook(request: Request, x_composio_signature: str = Header(...)):
    """
    Endpoint to receive new email payloads from Composio.
    Validates HMAC signature and processes the email payload.
    """
    # Shared secret for HMAC validation (replace with your actual secret)
    SHARED_SECRET = "your_shared_secret"

    # Read the raw body of the request
    body = await request.body()

    # Validate HMAC signature
    computed_signature = hmac.new(
        key=SHARED_SECRET.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_signature, x_composio_signature):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    # Parse the JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Process the email payload
    try:
        process_email_payload(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process email payload: {str(e)}")

    return JSONResponse({"status": "success", "message": "Email payload processed successfully"})

@router.post("/webhook/{provider}")
async def handle_webhook(provider: str, request: Request):
    """Handle incoming webhook from a provider."""
    try:
        # Get webhook data
        webhook_data = await request.json()
        logger.info(f"Received webhook from {provider}: {webhook_data}")
        
        # Extract user ID from webhook data
        user_id = webhook_data.get("user_id")
        if not user_id:
            logger.error(f"No user_id found in webhook data from {provider}")
            raise HTTPException(status_code=400, detail="No user_id found in webhook data")
        
        # Get user data
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found for user_id: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Process webhook data
        # TODO: Implement webhook processing logic
        return {"status": "success", "message": "Webhook processed successfully"}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/webhooks")
async def list_webhooks(current_user: dict = Depends(get_current_user)):
    """List all webhooks for the current user."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Listing webhooks for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Get webhooks from user profile
        webhooks = user.get("webhooks", [])
        return {"webhooks": webhooks}
    except Exception as e:
        logger.error(f"Error listing webhooks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhooks")
async def create_webhook(webhook_data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Create a new webhook."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Creating webhook for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Add webhook to user's webhooks list
        webhooks = user.get("webhooks", [])
        webhooks.append(webhook_data)
        
        # Update user profile
        updated_user = await user_repository.update_user(user_id, {"webhooks": webhooks})
        return updated_user
    except Exception as e:
        logger.error(f"Error creating webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a webhook."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Deleting webhook {webhook_id} for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Remove webhook from user's webhooks list
        webhooks = user.get("webhooks", [])
        webhooks = [w for w in webhooks if w.get("id") != webhook_id]
        
        # Update user profile
        updated_user = await user_repository.update_user(user_id, {"webhooks": webhooks})
        return updated_user
    except Exception as e:
        logger.error(f"Error deleting webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))