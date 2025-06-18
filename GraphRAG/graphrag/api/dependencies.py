from fastapi import Depends
from ..db.graph_db import Neo4jWrapper
from ..db.vector_db import QdrantWrapper
from ..embeddings.embedding import EmbeddingService
from ..engine.rag_engine import GraphRAGEngine
from ..engine.entity_extraction import EntityExtractor
from ..engine.entity_resolution import EntityResolutionEngine
# from ..engine.entity_resolution import EntityProcessor  # To be implemented
from GraphRAG.graphrag.config import get_settings

def get_graph_db():
    settings = get_settings()
    db = Neo4jWrapper()
    try:
        yield db
    finally:
        db.close()

def get_vector_db():
    db = QdrantWrapper()
    yield db

def get_embedding_service():
    service = EmbeddingService()
    yield service

def get_rag_engine(
    graph_db: Neo4jWrapper = Depends(get_graph_db),
    vector_db: QdrantWrapper = Depends(get_vector_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    engine = GraphRAGEngine(
        graph_db=graph_db,
        vector_db=vector_db,
        embedding_service=embedding_service
    )
    yield engine

# Placeholder for entity processor dependency
# def get_entity_processor(
#     graph_db: Neo4jWrapper = Depends(get_graph_db),
#     vector_db: QdrantWrapper = Depends(get_vector_db),
#     embedding_service: EmbeddingService = Depends(get_embedding_service)
# ):
#     processor = EntityProcessor(
#         graph_db=graph_db,
#         vector_db=vector_db,
#         embedding_service=embedding_service
#     )
#     yield processor

def get_entity_resolution_engine(
    graph_db: Neo4jWrapper = Depends(get_graph_db),
    vector_db: QdrantWrapper = Depends(get_vector_db),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
):
    engine = EntityResolutionEngine(
        graph_db=graph_db,
        vector_db=vector_db,
        embedding_service=embedding_service
    )
    yield engine 