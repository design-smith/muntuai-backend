from fastapi import APIRouter, Request, Query, HTTPException, Depends, Header, Body
from fastapi.responses import JSONResponse, RedirectResponse
import logging
import traceback
from backend.routers.auth_utils import get_current_user, security
from backend.data_services.mongo.user_repository import update_user, get_user_by_pending_connection, UserRepository
from jose import jwt, JWTError
import os
from datetime import datetime, UTC
from backend.integrations.manual.gmail_client import GmailClient
import pickle
from googleapiclient.discovery import build
from backend.data_services.mongo.conversation_repository import ConversationRepository
from backend.data_services.mongo.message_repository import create_message, list_messages
from bson import ObjectId

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manual-integrations", tags=["manual-integrations"])

# Initialize repositories
user_repository = UserRepository()
conversation_repository = ConversationRepository()

@router.get("/connect")
async def connect_integration(
    request: Request, 
    provider: str = Query(...), 
    token: str = Query(None),
    authorization: str = Header(None)
):
    """
    Initiate an OAuth connection for the given provider using manual integration.
    Returns a redirect URL for the user to complete the OAuth flow.
    """
    try:
        logger.info(f"🔗 Manual connect request for provider: {provider}")
        user_id = None
        user = None
        jwt_token = None

        # Try Authorization header first
        if authorization and authorization.startswith("Bearer "):
            jwt_token = authorization.split(" ", 1)[1]
            logger.info("Using Authorization header for JWT.")
        elif token:
            jwt_token = token
            logger.info("Using token query param for JWT.")

        if jwt_token:
            secret = os.getenv("SUPABASE_JWT_SECRET") or os.getenv("JWT_SECRET")
            payload = jwt.decode(jwt_token, secret, audience="authenticated", algorithms=["HS256"])
            user_id = payload.get("sub") or payload.get("user_id")
            user = get_user_by_id(user_id)
            if not user:
                logger.error(f"User not found for user_id from JWT: {user_id}")
                raise HTTPException(status_code=404, detail="User not found")
        else:
            logger.error("No authentication provided")
            raise HTTPException(status_code=403, detail="Not authenticated")

        # Store a pending connection in the user's record
        manual_integrations = user.get("manual_integrations", [])
        manual_integrations.append({
            "provider": provider,
            "status": "PENDING",
            "created_at": datetime.now(UTC).isoformat()
        })
        update_user(user_id, {"manual_integrations": manual_integrations})
        logger.info(f"Added PENDING integration for user {user_id}, provider {provider}")

        # Initialize the appropriate client based on provider
        if provider == "gmail":
            client = GmailClient()
            auth_url, state = client.get_auth_url(state=user_id)  # Use user_id as state for tracking
            return JSONResponse({
                "status": "pending",
                "auth_url": auth_url
            })
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in manual connect_integration: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Integration connection failed: {str(e)}"
        )

@router.get("/list")
async def list_manual_integrations(current_user: dict = Depends(get_current_user)):
    """List all manual integrations for the current user."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Listing manual integrations for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Get manual integrations from user profile
        manual_integrations = user.get("manual_integrations", [])
        return {"integrations": manual_integrations}
    except Exception as e:
        logger.error(f"Error listing manual integrations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{provider}")
async def remove_integration(
    provider: str, 
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a manual integration for the current user.
    """
    try:
        logger.info(f"🗑️ Removing manual integration: {provider}")
        
        user_id = current_user["user_id"]
        user = get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        manual_integrations = user.get("manual_integrations", [])
        original_count = len(manual_integrations)
        
        new_integrations = [
            i for i in manual_integrations 
            if i["provider"] != provider
        ]
        
        if len(new_integrations) == original_count:
            raise HTTPException(
                status_code=404, 
                detail="Integration not found"
            )
        
        # If it's Gmail, also remove the token file
        if provider == "gmail":
            for integration in manual_integrations:
                if integration["provider"] == provider and "token_path" in integration:
                    try:
                        os.remove(integration["token_path"])
                    except Exception as e:
                        logger.warning(f"Failed to remove token file: {str(e)}")
        
        update_user(user_id, {"manual_integrations": new_integrations})
        logger.info(f"✅ Removed manual integration: {provider}")
        
        return {
            "status": "success", 
            "message": f"Removed integration {provider}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error removing manual integration: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to remove manual integration: {str(e)}"
        )

@router.get("/callback")
async def manual_callback(
    code: str = Query(None),
    state: str = Query(None),
    scope: str = Query(None),
    authuser: str = Query(None),
    prompt: str = Query(None)
):
    """
    Handle OAuth callback for manual integrations.
    """
    try:
        logger.info(f"🔄 Manual callback received: code={code}, state={state}, scope={scope}")
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state in callback")
        user_id = state
        user = get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found for user_id from state: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        client = GmailClient()
        creds = client.exchange_code(code)
        email = client.get_authenticated_email()
        manual_integrations = user.get("manual_integrations", [])
        for integration in manual_integrations:
            if integration["provider"] == "gmail" and integration["status"] == "PENDING":
                integration["status"] = "ACTIVE"
                integration["connected_at"] = datetime.now(UTC).isoformat()
                integration["email"] = email
                break
        update_user(user_id, {"manual_integrations": manual_integrations})
        logger.info(f"✅ Successfully processed callback for gmail, user {user_id}")
        frontend_success_url = os.getenv("FRONTEND_SUCCESS_URL", "http://localhost:3000/settings")
        return RedirectResponse(url=frontend_success_url, status_code=302)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in manual callback: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Callback processing failed: {str(e)}"
        )

@router.get("/gmail/emails")
async def get_gmail_emails(current_user: dict = Depends(get_current_user)):
    """Get Gmail emails for the current user."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Getting Gmail emails for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Get conversations from Gmail
        conversations = await conversation_repository.list_conversations(user_id=user_id, source="Email")
        
        # Format conversations as threads
        threads = []
        for conv in conversations:
            if conv.get("gmail_thread_id"):
                threads.append({
                    "threadId": conv["gmail_thread_id"],
                    "latest": {
                        "sender": conv.get("participants", [""])[0].split("<")[0].strip(),
                        "subject": conv.get("subject", "No Subject"),
                        "snippet": conv.get("snippet", ""),
                        "date": conv.get("created_at", "").isoformat(),
                        "messages": conv.get("messages", [])
                    }
                })
        
        return {"threads": threads}
    except Exception as e:
        logger.error(f"Error getting Gmail emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create")
async def create_manual_integration(integration_data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Create a new manual integration."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Creating manual integration for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Add integration to user's manual integrations list
        manual_integrations = user.get("manual_integrations", [])
        manual_integrations.append(integration_data)
        
        # Update user profile
        updated_user = await user_repository.update_user(user_id, {"manual_integrations": manual_integrations})
        return updated_user
    except Exception as e:
        logger.error(f"Error creating manual integration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update/{integration_id}")
async def update_manual_integration(integration_id: str, update_data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Update a manual integration."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Updating manual integration {integration_id} for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Update integration in user's manual integrations list
        manual_integrations = user.get("manual_integrations", [])
        manual_integrations = [
            {**i, **update_data} if i.get("id") == integration_id else i
            for i in manual_integrations
        ]
        
        # Update user profile
        updated_user = await user_repository.update_user(user_id, {"manual_integrations": manual_integrations})
        return updated_user
    except Exception as e:
        logger.error(f"Error updating manual integration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete/{integration_id}")
async def delete_manual_integration(integration_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a manual integration."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Deleting manual integration {integration_id} for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Remove integration from user's manual integrations list
        manual_integrations = user.get("manual_integrations", [])
        manual_integrations = [i for i in manual_integrations if i.get("id") != integration_id]
        
        # Update user profile
        updated_user = await user_repository.update_user(user_id, {"manual_integrations": manual_integrations})
        return updated_user
    except Exception as e:
        logger.error(f"Error deleting manual integration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 