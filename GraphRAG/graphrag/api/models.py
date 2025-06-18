from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# Request Models
class GraphQueryRequest(BaseModel):
    query: str
    user_id: str
    max_results: Optional[int] = 10
    include_entities: Optional[bool] = True
    include_tasks: Optional[bool] = True
    
class EntityRequest(BaseModel):
    text: str
    type: str
    metadata: Optional[Dict[str, Any]] = None
    relationships: Optional[List[Dict[str, Any]]] = None
    
class GraphAddRequest(BaseModel):
    entity: EntityRequest
    user_id: str
    source: Optional[str] = "api"
    
class EntityResolutionRequest(BaseModel):
    entity: Dict[str, Any]
    entity_type: str

class EntityMergeRequest(BaseModel):
    source_id: str
    target_id: str
    entity_type: str
    merge_strategy: str = "newer_wins"

class BatchResolutionRequest(BaseModel):
    entity_type: str
    match_threshold: float = 0.7
    limit: int = 1000

# Response Models
class EntityResponse(BaseModel):
    id: str
    type: str
    text: str
    metadata: Dict[str, Any]
    relevance_score: Optional[float] = None
    relationships: Optional[List[Dict[str, Any]]] = None
    
class GraphQueryResponse(BaseModel):
    results: List[Dict[str, Any]]
    entities: Optional[List[EntityResponse]] = None
    tasks: Optional[List[Dict[str, Any]]] = None
    summary: Dict[str, Any]

class BatchResolutionResult(BaseModel):
    source_id: str
    target_id: str
    match_score: float
    entity_type: str 