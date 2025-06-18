from fastapi import FastAPI
from .api.routes import router
from .db.vector_db import QdrantWrapper
from .config import get_settings

app = FastAPI(title="GraphRAG API")

# Initialize vector database collection on startup
@app.on_event("startup")
async def startup_event():
    settings = get_settings()
    vector_db = QdrantWrapper()
    try:
        vector_db.create_collection(
            collection_name="documents",
            vector_size=384  # Size for all-MiniLM-L6-v2 model
        )
    except Exception as e:
        print(f"Warning: Collection might already exist: {str(e)}")

# Include API routes
app.include_router(router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 