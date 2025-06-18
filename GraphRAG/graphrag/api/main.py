from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router as main_router
from .composio_routes import router as composio_router
from GraphRAG.graphrag.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Muntu AI GraphRAG API",
    description="API for Muntu AI's GraphRAG system for multi-channel communication",
    version="1.0.0"
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(main_router)
app.include_router(composio_router)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"} 