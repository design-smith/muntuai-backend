from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from ..engine.rag_engine import GraphRAGEngine, run_pruning_job, archive_nodes
from .models import (
    GraphQueryRequest, GraphAddRequest, EntityResponse, GraphQueryResponse,
    EntityResolutionRequest, EntityMergeRequest, BatchResolutionRequest, BatchResolutionResult
)
from .dependencies import get_rag_engine, get_entity_resolution_engine
# from .dependencies import get_entity_processor  # Uncomment when EntityProcessor is implemented
# from ..engine.entity_resolution import EntityProcessor
from fastapi import status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

router = APIRouter(prefix="/api", tags=["graphrag"])
rag_engine = GraphRAGEngine()

security = HTTPBasic()

ADMIN_USERNAME = "admin"  # In production, use env vars or a secure vault
ADMIN_PASSWORD = "changeme"  # In production, use env vars or a secure vault

def is_admin(credentials: HTTPBasicCredentials) -> bool:
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    return correct_username and correct_password

class DocumentInput(BaseModel):
    document_id: str
    content: str
    metadata: Dict[str, Any]

class QueryInput(BaseModel):
    query: str
    limit: int = 5

class AdminArchiveRequest(BaseModel):
    entity_type: str
    node_ids: List[str]

@router.post("/index")
async def index_document(document: DocumentInput):
    try:
        rag_engine.index_document(
            document_id=document.document_id,
            content=document.content,
            metadata=document.metadata
        )
        return {"status": "success", "message": "Document indexed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query", response_model=GraphQueryResponse)
async def query_graph(
    request: GraphQueryRequest,
    rag_engine = Depends(get_rag_engine)
):
    """
    Query the GraphRAG engine with natural language
    """
    try:
        results = rag_engine.retrieve_with_context(
            query_text=request.query,
            filters=None,
            max_hops=2
        )
        response = {
            "results": results.get("results", []),
            "summary": results.get("graph_summary", {})
        }
        if request.include_entities and "entities" in results:
            response["entities"] = results["entities"]
        if request.include_tasks and "tasks" in results:
            response["tasks"] = results["tasks"]
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add", response_model=EntityResponse)
async def add_to_graph(
    request: GraphAddRequest,
    # entity_processor = Depends(get_entity_processor)  # Uncomment when implemented
):
    """
    Add a new entity to the graph
    """
    try:
        # Placeholder: implement entity_processor.process_entity when available
        # entity = entity_processor.process_entity(
        #     entity_data=request.entity.dict(),
        #     user_id=request.user_id,
        #     source=request.source
        # )
        entity = {"id": "mock_id", "type": request.entity.type, "text": request.entity.text, "metadata": request.entity.metadata or {}, "relevance_score": 1.0, "relationships": request.entity.relationships or []}
        return entity
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entity/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: str,
    rag_engine = Depends(get_rag_engine)
):
    """
    Get entity details by ID
    """
    try:
        entity = rag_engine.graph_db.get_node(label=None, match_props={"id": entity_id})
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        # Format as EntityResponse
        return {"id": entity_id, "type": entity[0].get("type", "Unknown"), "text": entity[0].get("name", ""), "metadata": entity[0], "relevance_score": 1.0, "relationships": []}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entities", response_model=List[EntityResponse])
async def search_entities(
    query: str = Query(..., description="Search query for entities"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(10, description="Maximum number of results"),
    rag_engine = Depends(get_rag_engine)
):
    """
    Search for entities by text and type
    """
    try:
        # Placeholder: implement rag_engine.search_entities when available
        # entities = rag_engine.search_entities(query_text=query, entity_type=entity_type, limit=limit)
        entities = []
        return entities
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hello")
async def hello():
    return {"message": "GraphRAG API is up!"}

# Full endpoints to be implemented after entity resolution and processor are in place 

# --- Entity Resolution Endpoints ---
@router.post("/entity-resolution/resolve", response_model=EntityResponse)
async def resolve_entity(
    request: EntityResolutionRequest,
    engine = Depends(get_entity_resolution_engine)
):
    """
    Resolve a single entity using multi-strategy matching.
    """
    try:
        match = engine.resolve_entity(request.entity, request.entity_type)
        if match:
            return {
                "id": match.get("id", ""),
                "type": request.entity_type,
                "text": match.get("name", match.get("text", "")),
                "metadata": match,
                "relevance_score": 1.0,
                "relationships": []
            }
        else:
            raise HTTPException(status_code=404, detail="No matching entity found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/entity-resolution/merge", response_model=EntityResponse)
async def merge_entities(
    request: EntityMergeRequest,
    engine = Depends(get_entity_resolution_engine)
):
    """
    Merge two entities, preserving relationships and data.
    """
    try:
        merged = engine.merge_entities(
            source_id=request.source_id,
            target_id=request.target_id,
            entity_type=request.entity_type,
            merge_strategy=request.merge_strategy
        )
        return {
            "id": merged.get("id", ""),
            "type": request.entity_type,
            "text": merged.get("name", merged.get("text", "")),
            "metadata": merged,
            "relevance_score": 1.0,
            "relationships": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/entity-resolution/batch", response_model=List[BatchResolutionResult])
async def batch_resolve_entities(
    request: BatchResolutionRequest,
    engine = Depends(get_entity_resolution_engine)
):
    """
    Run batch entity resolution for a given type.
    """
    try:
        results = engine.batch_resolve_entities(
            entity_type=request.entity_type,
            match_threshold=request.match_threshold,
            limit=request.limit
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 

# --- Admin Endpoints ---
@router.post("/admin/prune", status_code=status.HTTP_202_ACCEPTED, tags=["admin"], summary="Trigger pruning job", description="Trigger the scheduled pruning and archiving job immediately. Requires admin authentication.")
async def admin_prune(
    credentials: HTTPBasicCredentials = Depends(security),
    rag_engine = Depends(get_rag_engine)
):
    """
    Trigger the scheduled pruning and archiving job immediately. Requires admin authentication.
    """
    if not is_admin(credentials):
        raise HTTPException(status_code=403, detail="Admin access required")
    run_pruning_job(rag_engine.graph_db)
    return {"status": "pruning job triggered"}

@router.post("/admin/archive", status_code=status.HTTP_202_ACCEPTED, tags=["admin"], summary="Archive nodes", description="Archive a batch of nodes by type and IDs. Requires admin authentication.")
async def admin_archive(
    req: AdminArchiveRequest,
    credentials: HTTPBasicCredentials = Depends(security),
    rag_engine = Depends(get_rag_engine)
):
    """
    Archive a batch of nodes by type and IDs. Requires admin authentication.
    """
    if not is_admin(credentials):
        raise HTTPException(status_code=403, detail="Admin access required")
    archive_nodes(req.node_ids, req.entity_type, rag_engine.graph_db)
    return {"status": "archive job triggered", "archived": req.node_ids} 