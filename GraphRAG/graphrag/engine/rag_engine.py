import uuid
from typing import List, Dict, Any, Optional
import threading
import time
from collections import OrderedDict
from backend.data_services.redis_cache import RedisCache
from backend.data_services.cold_storage import store_in_cold_storage, retrieve_from_cold_storage

from ..db.graph_db import Neo4jWrapper
from ..db.vector_db import QdrantWrapper
from ..embeddings.embedding import EmbeddingService
from .graph_traversal import GraphTraversal
import logging
from datetime import datetime, timedelta, UTC

class LRUCache:
    def __init__(self, max_size=1000, ttl=1800):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key in self.cache:
                value, expire = self.cache.pop(key)
                if expire > time.time():
                    self.cache[key] = (value, expire)
                    return value
                else:
                    # Expired
                    return None
            return None

    def set(self, key, value):
        with self.lock:
            expire = time.time() + self.ttl
            if key in self.cache:
                self.cache.pop(key)
            elif len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
            self.cache[key] = (value, expire)

    def delete(self, key):
        with self.lock:
            if key in self.cache:
                self.cache.pop(key)

    def clear(self):
        with self.lock:
            self.cache.clear()

# Initialize caches
node_cache = LRUCache(max_size=10000, ttl=1800)  # 30 min
embedding_cache = LRUCache(max_size=5000, ttl=3600)  # 60 min
# Temporarily comment out Redis Cache initialization
# redis_cache = RedisCache()

# --- Node Caching ---
def get_node_with_cache(node_id, node_type, graph_db):
    cache_key = f"{node_type}:{node_id}"
    cached_node = node_cache.get(cache_key)
    if cached_node is not None:
        update_node_access_timestamp(node_id, graph_db)
        return cached_node
    cached_node = redis_cache.get(cache_key)
    if cached_node is not None:
        node_cache.set(cache_key, cached_node)
        update_node_access_timestamp(node_id, graph_db)
        return cached_node
    node_data_list = graph_db.get_node(label=node_type, match_props={'id': node_id})
    node_data = node_data_list[0] if node_data_list else None
    if node_data is not None:
        node_cache.set(cache_key, node_data)
        redis_cache.set(cache_key, node_data, ttl=4*3600)
        update_node_access_timestamp(node_id, graph_db)
    return node_data

# --- Embedding Caching ---
def get_embedding_with_cache(text, embedding_service):
    text_hash = str(hash(text))
    cached_embedding = embedding_cache.get(text_hash)
    if cached_embedding is not None:
        return cached_embedding
    embedding = embedding_service.generate_embedding(text)
    embedding_cache.set(text_hash, embedding)
    return embedding

# --- High-level Operation Cache ---
def get_operation_cache(key):
    return redis_cache.get(key)

def set_operation_cache(key, value, ttl=600):
    redis_cache.set(key, value, ttl=ttl)

# --- Cypher Query Result Caching ---
def execute_query_with_cache(query, parameters, graph_db):
    import pickle
    # Only cache if this is a Cypher query
    if not query.strip().lower().startswith((
        "match", "call", "with", "unwind", "create", "merge", "set", "delete", "remove", "return", "optional"
    )):
        raise ValueError("execute_query_with_cache called with non-Cypher query string.")
    query_hash = str(hash(query + pickle.dumps(parameters).hex()))
    cache_key = f"cypher_query:{query_hash}"
    cached_result = redis_cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    result = graph_db.run_query(query, parameters)
    if is_cacheable_query(query):
        redis_cache.set(cache_key, result, ttl=calculate_ttl(query))
    return result

def is_cacheable_query(query):
    # Simple heuristic: cache read-only queries
    return query.strip().lower().startswith("match")

def calculate_ttl(query):
    # Example: longer TTL for less dynamic queries
    if "LIMIT" in query.upper():
        return 3600  # 1 hour
    return 600  # 10 min

def update_node_access_timestamp(node_id, graph_db):
    query = """
    MATCH (n) WHERE n.id = $node_id
    SET n.last_accessed_at = datetime(),
        n.access_count = COALESCE(n.access_count, 0) + 1
    """
    graph_db.execute_query(query, {"node_id": node_id})

# --- Cache Invalidation ---
def invalidate_node_cache(node_id, node_type):
    cache_key = f"{node_type}:{node_id}"
    node_cache.delete(cache_key)
    redis_cache.delete(cache_key)

def invalidate_related_query_cache(node_id):
    # For simplicity, flush all query cache (could be more granular)
    # In production, track which queries involve which nodes
    redis_cache.flush()

# --- Node/Relationship Update with Invalidation ---
def update_node_with_cache(node_id, node_type, properties, graph_db):
    result = graph_db.update_node(node_id, properties)
    invalidate_node_cache(node_id, node_type)
    # Invalidate related query cache if node has relationships
    if properties.get('relationships'):
        invalidate_related_query_cache(node_id)
    return result

def create_relationship_with_cache(source_id, source_type, target_id, target_type, rel_type, properties, graph_db):
    result = graph_db.create_relationship(source_id, target_id, rel_type, properties)
    invalidate_node_cache(source_id, source_type)
    invalidate_node_cache(target_id, target_type)
    invalidate_related_query_cache(source_id)
    invalidate_related_query_cache(target_id)
    return result

# --- Direct Node Lookup with Cache ---
def get_node(node_id, node_type, graph_db):
    return get_node_with_cache(node_id, node_type, graph_db)

# --- Pruning, Archiving, and Batch Write Stubs ---
PRUNING_THRESHOLDS = {
    "Message": {"archive_after": 90, "remove_after": 365},
    "Task": {"archive_after": 60, "remove_after": 180},
    "Person": {"archive_after": 180, "remove_after": None},
    "Organization": {"archive_after": 270, "remove_after": None},
    "Event": {"archive_after": 60, "remove_after": 180},
}

def run_pruning_job(graph_db):
    now = datetime.now(UTC)
    for entity_type, thresholds in PRUNING_THRESHOLDS.items():
        if thresholds["archive_after"] is None:
            continue
        archive_date = now - timedelta(days=thresholds["archive_after"])
        # Query for archive candidates (stub)
        # candidates = query_archive_candidates(entity_type, archive_date)
        # for batch in batch_candidates(candidates, 1000):
        #     archive_nodes(batch, entity_type, graph_db)
        if thresholds["remove_after"] is not None:
            removal_date = now - timedelta(days=thresholds["remove_after"])
            # removal_candidates = query_removal_candidates(entity_type, removal_date)
            # for batch in batch_candidates(removal_candidates, 500):
            #     remove_nodes(batch, entity_type, graph_db)

def archive_nodes(node_batch, entity_type, graph_db):
    for node_id in node_batch:
        node_data = get_node_with_cache(node_id, entity_type, graph_db)
        if not node_data:
            continue
        archive_reference = store_in_cold_storage(node_data)
        # Update node status and remove content if needed
        query = """
        MATCH (n)
        WHERE n.id = $node_id
        SET n.status = 'archived',
            n.archived_at = datetime.now(UTC),
            n.archive_reference = $archive_reference
        """
        params = {"node_id": node_id, "archive_reference": archive_reference}
        if entity_type == "Message":
            query += "\nSET n.content = NULL, n.has_archived_content = true"
        graph_db.execute_query(query, params)
        invalidate_node_cache(node_id, entity_type)

def get_node_with_archive_support(node_id, node_type, graph_db):
    node = get_node_with_cache(node_id, node_type, graph_db)
    if node is not None and node.get('has_archived_content'):
        archive_reference = node.get('archive_reference')
        if archive_reference:
            archived_content = retrieve_from_cold_storage(archive_reference)
            node['content'] = archived_content.get('content')
        update_node_access_timestamp(node_id, graph_db)
    return node

# --- Batch Write Queue (Stub) ---
class WriteQueue:
    def __init__(self, max_size=10000):
        self.queue = []
        self.max_size = max_size
    def push(self, op):
        self.queue.append(op)
        if len(self.queue) >= self.max_size:
            self.process_batch()
    def process_batch(self):
        # Group and process batched operations (stub)
        self.queue.clear()

write_queue = WriteQueue()

def queue_write_operation(operation_type, data):
    write_queue.push({
        "type": operation_type,
        "data": data,
        "timestamp": time.time()
    })

# --- Monitoring and Scheduled Jobs ---
cache_metrics = {
    'node_cache': {'get': {'hit': 0, 'miss': 0}},
    'embedding_cache': {'get': {'hit': 0, 'miss': 0}},
    'redis_cache': {'get': {'hit': 0, 'miss': 0}},
}

def monitored_cache_get(cache, key, cache_type):
    value = cache.get(key)
    if value is not None:
        cache_metrics[cache_type]['get']['hit'] += 1
    else:
        cache_metrics[cache_type]['get']['miss'] += 1
    return value

def log_cache_stats():
    for cache_type, ops in cache_metrics.items():
        hits = ops['get']['hit']
        misses = ops['get']['miss']
        total = hits + misses
        hit_rate = (hits / total) * 100 if total > 0 else 0
        logging.info(f"Cache {cache_type} hit rate: {hit_rate:.2f}% ({hits} hits, {misses} misses)")

# Schedule pruning/archiving job every 24 hours
def schedule_pruning_job(graph_db, interval_hours=24):
    def job():
        logging.info("Running scheduled pruning/archiving job...")
        run_pruning_job(graph_db)
        threading.Timer(interval_hours * 3600, job).start()
    threading.Timer(interval_hours * 3600, job).start()

# Example: start scheduled job (in production, call this from app startup)
# schedule_pruning_job(graph_db_instance)

class GraphRAGEngine:
    def __init__(
        self,
        graph_db: Optional[Neo4jWrapper] = None,
        vector_db: Optional[QdrantWrapper] = None,
        embedding_service: Optional[EmbeddingService] = None,
        collection_name: str = "muntu_knowledge",
        similarity_threshold: float = 0.7,
        max_results: int = 10
    ):
        self.graph_db = graph_db or Neo4jWrapper()
        self.vector_db = vector_db or QdrantWrapper()
        self.embedding_service = embedding_service or EmbeddingService()
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        self.max_results = max_results
        self.graph_traversal = GraphTraversal(self.graph_db)
        self._initialize_collection()

    def _initialize_collection(self) -> None:
        # For simplicity, always try to create the collection (Qdrant will not overwrite if exists)
        sample_embedding = self.embedding_service.model.encode(["Sample text"])[0]
        dimension = len(sample_embedding)
        try:
            self.vector_db.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config={"size": dimension, "distance": "Cosine"}
            )
        except Exception:
            pass

    def store_document(
        self,
        text: str,
        metadata: Dict[str, Any],
        node_type: str,
        relationships: Optional[List[Dict]] = None
    ) -> str:
        doc_id = str(uuid.uuid4())
        properties = {"id": doc_id, **metadata}
        # Only add text/content if the node type supports it
        if node_type == "Message":
            properties["content"] = text
        elif node_type in ["Document"]:  # Add other types with 'text' property if needed
            properties["text"] = text
        self.graph_db.create_node(node_type, properties)
        if relationships:
            for rel in relationships:
                self.graph_db.create_relationship(
                    from_label=node_type,
                    to_label=rel["target_type"],
                    rel_type=rel["rel_type"],
                    from_props={"id": doc_id},
                    to_props={"id": rel["target_id"]},
                    rel_props=rel.get("properties", {})
                )
        # Use embedding cache
        if text:
            embedding = get_embedding_with_cache(text, self.embedding_service)
        else:
            embedding = get_embedding_with_cache(metadata.get('name', ''), self.embedding_service)
        self.vector_db.upsert_embedding(
            collection=self.collection_name,
            id=doc_id,
            vector=embedding,
            payload={
                "text": text,
                "node_type": node_type,
                **metadata
            }
        )
        return doc_id
    
    def semantic_search(self, query_text: str, filters: Optional[Dict] = None) -> List[Dict]:
        # Use embedding cache for query embedding
        query_embedding = get_embedding_with_cache(query_text, self.embedding_service)
        vector_results = self.vector_db.search_vectors(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=self.max_results
        )
        relevant_results = [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in vector_results if r.score >= self.similarity_threshold
        ]
        return relevant_results

    def hybrid_search(
        self,
        query_text: str,
        filters: Optional[Dict] = None,
        max_hops: int = 2
    ) -> Dict[str, Any]:
        op_key = f"hybrid_search:{query_text}:{filters}:{max_hops}"
        cached_result = get_operation_cache(op_key)
        if cached_result is not None:
            return cached_result
        vector_results = self.semantic_search(query_text, filters)
        seed_node_ids = [result["id"] for result in vector_results]
        if not seed_node_ids:
            result = {"results": [], "context": {"nodes": [], "relationships": []}, "task_context": {}}
            set_operation_cache(op_key, result, ttl=600)
            return result
        graph_context = self.graph_traversal.traverse_from_seeds(
            seed_node_ids=seed_node_ids,
            max_hops=max_hops
        )
        task_context = {}
        for node in graph_context["nodes"]:
            tasks = self.graph_traversal.find_related_tasks(
                entity_id=node["id"],
                status_filter=["pending", "in_progress"]
            )
            if tasks:
                task_context[node["id"]] = tasks
        combined_results = {
            "results": vector_results,
            "context": graph_context,
            "task_context": task_context
        }
        set_operation_cache(op_key, combined_results, ttl=600)
        return combined_results

    def retrieve_with_context(
        self,
        query_text: str,
        filters: Optional[Dict] = None,
        max_hops: int = 2
    ) -> Dict[str, Any]:
        print(f"[DEBUG] retrieve_with_context called with query_text={query_text}, filters={filters}, max_hops={max_hops}")
        op_key = f"retrieve_with_context:{query_text}:{filters}:{max_hops}"
        print(f"[DEBUG] Operation cache key: {op_key}")
        cached_result = get_operation_cache(op_key)
        print(f"[DEBUG] Cached result: {cached_result}")
        if cached_result is not None:
            print(f"[DEBUG] Returning cached result of type {type(cached_result)}")
            return cached_result
        hybrid_results = self.hybrid_search(
            query_text=query_text,
            filters=filters,
            max_hops=max_hops
        )
        print(f"[DEBUG] hybrid_results: {hybrid_results}")
        print(f"[DEBUG] Type of hybrid_results: {type(hybrid_results)}")
        formatted_results = self._format_results(hybrid_results)
        print(f"[DEBUG] formatted_results: {formatted_results}")
        print(f"[DEBUG] Type of formatted_results: {type(formatted_results)}")
        # Cache the formatted results for this operation
        set_operation_cache(op_key, formatted_results, ttl=600)
        return formatted_results

    def _format_results(self, hybrid_results: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[DEBUG] _format_results called with hybrid_results: {hybrid_results}")
        vector_results = hybrid_results["results"]
        graph_context = hybrid_results["context"]
        node_map = {node["id"]: node for node in graph_context.get("nodes", [])}
        enriched_results = []
        for result in vector_results:
            result_id = result["id"]
            connections = [
                rel for rel in graph_context.get("relationships", [])
                if rel.get("source") == result_id or rel.get("target") == result_id
            ]
            connected_nodes = []
            for conn in connections:
                other_id = conn["target"] if conn["source"] == result_id else conn["source"]
                if other_id in node_map:
                    connected_nodes.append({
                        "node": node_map[other_id],
                        "relationship": conn
                    })
            enriched_results.append({
                "document": result,
                "connections": connected_nodes
            })
        print(f"[DEBUG] enriched_results: {enriched_results}")
        result_dict = {
            "results": enriched_results,
            "graph_summary": {
                "total_nodes": len(graph_context.get("nodes", [])),
                "total_relationships": len(graph_context.get("relationships", []))
            }
        } 
        print(f"[DEBUG] result_dict: {result_dict}")
        print(f"[DEBUG] Type of result_dict: {type(result_dict)}")
        return result_dict 