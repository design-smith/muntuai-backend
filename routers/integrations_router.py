from fastapi import APIRouter, Request, Query, HTTPException, Depends, Header, Body
from fastapi.responses import JSONResponse, RedirectResponse # Added RedirectResponse
import logging
import traceback
from backend.routers.auth_utils import get_current_user, security
from backend.data_services.mongo.user_repository import update_user, get_user_by_pending_connection, UserRepository
from jose import jwt, JWTError
import os
from urllib.parse import parse_qs, unquote # Added unquote
from datetime import datetime, UTC # Added datetime, UTC

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])

# Initialize repositories
user_repository = UserRepository()

@router.get("/connect")
async def connect_integration(
    request: Request, 
    provider: str = Query(...), 
    search_range: int = Query(None),
    token: str = Query(None),
    authorization: str = Header(None)
):
    """
    Initiate an OAuth connection for the given provider (e.g., gmail) using Composio.
    Returns a redirect URL for the user to complete the OAuth flow.
    Accepts token as query param or Authorization header.
    """
    try:
        logger.info(f"🔗 Connect request for provider: {provider}")
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
            logger.info(f"Decoding JWT using secret: {secret[:8]}... (truncated)")
            payload = jwt.decode(jwt_token, secret, audience="authenticated", algorithms=["HS256"])
            logger.info(f"Decoded JWT payload: {payload}")
            user_id = payload.get("sub") or payload.get("user_id")
            logger.info(f"Extracted user_id from JWT: {user_id}")
            user = await user_repository.get_user_by_id(user_id)
            if not user:
                logger.error(f"User not found for user_id from JWT: {user_id}")
                raise HTTPException(status_code=404, detail="User not found")
            # Always use Supabase ID for Composio
            composio_entity_id = user.get("auth", {}).get("provider_id", user_id)
        else:
            logger.error("No authentication provided (neither Authorization header nor token param)")
            raise HTTPException(status_code=403, detail="Not authenticated")

        # Store search_range in user preferences if provided
        if search_range is not None:
            integration_preferences = user.get("integration_preferences", {})
            integration_preferences[provider] = integration_preferences.get(provider, {})
            integration_preferences[provider]["search_range"] = search_range
            update_user(user_id, {"integration_preferences": integration_preferences})
            logger.info(f"Set search_range={search_range} for provider={provider} in user preferences.")
        # Store a pending connection in the user's record
        composio_integrations = user.get("composio_integrations", [])
        composio_integrations.append({
            "provider": provider,
            "status": "PENDING",
            "created_at": datetime.now(UTC).isoformat()
        })
        update_user(user_id, {"composio_integrations": composio_integrations})
        logger.info(f"Added PENDING integration for user {user_id}, provider {provider}")
        # Import here to avoid circular imports
        try:
            from backend.integrations.composio.client import ComposioIntegrationClient
        except ImportError as e:
            logger.error(f"Failed to import ComposioIntegrationClient: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Integration service unavailable"
            )
        composio_client = ComposioIntegrationClient()
        redirect_url = composio_client.initiate_connection(composio_entity_id, provider)
        if not redirect_url:
            raise HTTPException(
                status_code=500, 
                detail="Failed to get redirect URL from Composio."
            )
        logger.info(f"✅ Generated redirect URL for {provider}")
        return JSONResponse({"redirect_url": redirect_url})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in connect_integration: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Integration connection failed: {str(e)}"
        )

@router.get("/callback")
async def composio_callback(
    code: str = Query(None),
    state: str = Query(None),
    scope: str = Query(None),
    authuser: str = Query(None),
    prompt: str = Query(None)
):
    """
    Handle Composio's redirect after OAuth. Accepts standard OAuth2 parameters.
    Parse provider and user_id from the state parameter if present.
    """
    try:
        logger.info(f"🔄 Callback received: code={code}, state={state}, scope={scope}, authuser={authuser}, prompt={prompt}")
        provider = None
        user_id = None
        if state:
            # Decode the URL-encoded state string first
            decoded_state = unquote(state)
            parsed_state = parse_qs(decoded_state)
            provider = parsed_state.get('provider', [None])[0]
            user_id = parsed_state.get('user_id', [None])[0]
            logger.info(f"Parsed from state: provider={provider}, user_id={user_id}")

        # If provider or user_id is missing, try to infer from DB
        if not provider or not user_id:
            from backend.data_services.mongo.user_repository import get_user_by_pending_connection
            user, provider = get_user_by_pending_connection()
            if not user or not provider:
                logger.error("Provider or User ID missing from state parameter and could not be inferred from DB.")
                raise HTTPException(status_code=400, detail="Missing provider or user_id in callback state.")
            user_id = str(user["_id"])
            logger.info(f"Inferred from DB: provider={provider}, user_id={user_id}")
        else:
            user = await user_repository.get_user_by_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found during callback processing.")
                raise HTTPException(status_code=404, detail="User not found")
        # Always use Supabase ID for Composio
        composio_entity_id = user.get("auth", {}).get("provider_id", user_id)
        # Import ComposioIntegrationClient here to avoid circular imports if needed
        from backend.integrations.composio.client import ComposioIntegrationClient
        composio_client = ComposioIntegrationClient()
        # Poll Composio for connection status
        logger.info(f"Polling connection status for user {composio_entity_id}, provider {provider}...")
        connection_id = composio_client.poll_connection_status(composio_entity_id, provider)

        # Update user's database record with the new integration
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User {user_id} not found during callback processing.")
            raise HTTPException(status_code=404, detail="User not found")
        
        composio_integrations = user.get("composio_integrations", [])
        
        # Check if this connection already exists to prevent duplicates
        existing_connection = next((
            item for item in composio_integrations
            if item.get("connection_id") == connection_id or (item.get("provider") == provider and item.get("status") == "ACTIVE")
        ), None)
        
        if existing_connection:
            logger.info(f"Connection for provider {provider} (ID: {connection_id}) already exists and is active for user {user_id}. Updating if necessary.")
            # Update existing entry if details changed (e.g., connection_id was initially None)
            for item in composio_integrations:
                if item.get("provider") == provider: # Assuming provider is unique per user for active connections
                    item["connection_id"] = connection_id
                    item["status"] = "ACTIVE"
                    break
        else:
            composio_integrations.append({
                "provider": provider,
                "connection_id": connection_id,
                "status": "ACTIVE",
                "connected_at": datetime.now(UTC).isoformat()
            })
            logger.info(f"Added new integration for user {user_id}: provider={provider}, connection_id={connection_id}")

        update_user(user_id, {"composio_integrations": composio_integrations})
        logger.info(f"✅ Successfully processed callback for {provider}, user {user_id}. Connection ID: {connection_id}")

        # Redirect to frontend dashboard or a success page
        # Ensure FRONTEND_SUCCESS_URL is set in your environment variables
        frontend_success_url = os.getenv("FRONTEND_SUCCESS_URL", "http://localhost:3000/settings")
        return RedirectResponse(url=frontend_success_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in callback: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Callback processing failed: {str(e)}"
        )

@router.get("/list")
async def list_integrations(current_user: dict = Depends(get_current_user)):
    """
    List all composio integrations for the current user.
    """
    try:
        logger.info(f"📋 Listing integrations for user: {current_user.get('user_id')}")
        
        user_id = current_user["user_id"]
        user = await user_repository.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        integrations = user.get("composio_integrations", [])
        logger.info(f"✅ Found {len(integrations)} integrations")
        
        return {"integrations": integrations}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing integrations: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to list integrations: {str(e)}"
        )

@router.delete("/{connection_id}")
async def remove_integration(
    connection_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a composio integration by connection_id for the current user.
    """
    try:
        logger.info(f"🗑️ Removing integration: {connection_id}")
        
        user_id = current_user["user_id"]
        user = await user_repository.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        composio_integrations = user.get("composio_integrations", [])
        original_count = len(composio_integrations)
        
        new_integrations = [
            i for i in composio_integrations 
            if i["connection_id"] != connection_id
        ]
        
        if len(new_integrations) == original_count:
            raise HTTPException(
                status_code=404, 
                detail="Integration not found"
            )
        
        update_user(user_id, {"composio_integrations": new_integrations})
        logger.info(f"✅ Removed integration: {connection_id}")
        
        return {
            "status": "success", 
            "message": f"Removed integration {connection_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error removing integration: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to remove integration: {str(e)}"
        )

# Test endpoint for debugging
@router.get("/test")
async def test_integrations():
    """Test endpoint to verify integrations router is working"""
    return {
        "status": "working", 
        "message": "Integrations router is operational",
        "timestamp": "2025-05-23"
    }

@router.post("/connect")
async def connect_integration(integration_data: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Connect a new integration."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Connecting integration for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Add integration to user's integrations list
        integrations = user.get("integrations", [])
        integrations.append(integration_data)
        
        # Update user profile
        updated_user = await user_repository.update_user(user_id, {"integrations": integrations})
        return updated_user
    except Exception as e:
        logger.error(f"Error connecting integration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/disconnect/{integration_id}")
async def disconnect_integration(integration_id: str, current_user: dict = Depends(get_current_user)):
    """Disconnect an integration."""
    try:
        user_id = current_user["user_id"]
        email = current_user["email"]
        logger.info(f"Disconnecting integration {integration_id} for user_id: {user_id}, email: {email}")
        
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found in MongoDB for user_id: {user_id}, email: {email}")
            raise HTTPException(status_code=404, detail="User not found in MongoDB.")
        
        # Remove integration from user's integrations list
        integrations = user.get("integrations", [])
        integrations = [i for i in integrations if i.get("id") != integration_id]
        
        # Update user profile
        updated_user = await user_repository.update_user(user_id, {"integrations": integrations})
        return updated_user
    except Exception as e:
        logger.error(f"Error disconnecting integration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))