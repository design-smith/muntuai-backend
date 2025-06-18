from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
import traceback
import os
from .routers import (
    chat, users, businesses, contacts, conversations, 
    messages, events, assistants, channels, tasks, 
    auth, integrations_router, webhooks_router, billing,
    manual_integrations_router
)
from .routers.auth_utils import get_current_user, security
import logging
from dotenv import load_dotenv
from backend.GraphRAG.graphrag.schema import initialize_schema
from backend.tasks.email_sync import sync_emails_task
import asyncio

load_dotenv()
# Configure logging first
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Muntu AI API",
    description="Backend API for Muntu AI application",
    version="1.0.0"
)

# Enhanced CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins during development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# Enhanced request logging middleware
@app.middleware("http")
async def log_requests_and_errors(request: Request, call_next):
    logger.info(f"🔥 {request.method} {request.url}")
    
    # Log request headers for debugging
    logger.info(f"Headers: {dict(request.headers)}")
    
    try:
        response = await call_next(request)
        logger.info(f"✅ Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"❌ Request failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Request processing error: {str(e)}"}
        )

# Include routers with error handling
try:
    app.include_router(auth.router)  # Auth first
    app.include_router(users.router)
    app.include_router(businesses.router)
    app.include_router(contacts.router)
    app.include_router(conversations.router, prefix="/api")
    app.include_router(messages.router)
    app.include_router(events.router)
    app.include_router(assistants.router)
    app.include_router(channels.router)
    app.include_router(tasks.router)
    app.include_router(chat.router, prefix="/api")
    app.include_router(integrations_router.router)
    app.include_router(manual_integrations_router.router)
    app.include_router(webhooks_router.router)
    app.include_router(billing.router)
    logger.info("✅ All routers loaded successfully")
except Exception as e:
    logger.error(f"❌ Failed to load routers: {str(e)}")
    logger.error(f"Traceback: {traceback.format_exc()}")

@app.get("/")
async def root():
    
    return {"message": "Welcome to Muntu AI API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2025-05-23"}

# Test endpoint to verify CORS
@app.get("/test-cors")
async def test_cors():
    return {"message": "CORS is working", "timestamp": "2025-05-23"}

# Test authenticated endpoint
@app.get("/test-auth")
async def test_auth(current_user: dict = Depends(get_current_user)):
    return {"message": "Authentication working", "user": current_user}

@app.get("/test-output")
def test_output_endpoint():
    print("--- TEST OUTPUT ENDPOINT HIT ---")
    return {"message": "Test output successful!"}

@app.on_event("startup")
async def show_routes():
    logger.info("🚀 MUNTU AI API STARTING UP")
    logger.info("🚀 ROUTES LOADED:")

    for route in app.router.routes:
        try:
            methods = ','.join(route.methods) if hasattr(route, 'methods') else 'WebSocket'
            logger.info(f"  {route.path} [{methods}]")
        except Exception as e:
            logger.error(f"Error processing route: {e}")
    logger.info("🚀 SERVER READY")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    # Initialize GraphRAG schema
    initialize_schema()
    # Start the email synchronization task
    asyncio.create_task(sync_emails_task())
    logger.info("✅ Email synchronization task started.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 MUNTU AI API SHUTTING DOWN")