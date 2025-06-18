import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tempfile
import time
import pytest
from fastapi.testclient import TestClient
from backend.data_services.redis_cache import RedisCache
from backend.data_services.cold_storage import store_in_cold_storage, retrieve_from_cold_storage
from backend.GraphRAG.graphrag.engine.rag_engine import LRUCache, invalidate_node_cache, node_cache, redis_cache
from backend.GraphRAG.graphrag.api.main import app

client = TestClient(app)

# --- LRUCache Tests ---
def test_lru_cache_basic():
    cache = LRUCache(max_size=2, ttl=2)
    cache.set('a', 1)
    assert cache.get('a') == 1
    cache.set('b', 2)
    cache.set('c', 3)  # 'a' should be evicted
    assert cache.get('a') is None
    assert cache.get('b') == 2
    assert cache.get('c') == 3
    time.sleep(2.1)
    assert cache.get('b') is None  # Expired

# --- RedisCache Tests ---
def test_redis_cache_basic():
    cache = RedisCache(db=15)  # Use a test DB
    cache.set('foo', {'bar': 1}, ttl=2)
    assert cache.get('foo') == {'bar': 1}
    cache.delete('foo')
    assert cache.get('foo') is None
    cache.set('foo', 123, ttl=1)
    time.sleep(1.1)
    assert cache.get('foo') is None
    cache.flush()

# --- Cold Storage Tests ---
def test_cold_storage(tmp_path):
    node = {'id': 'testnode', 'content': 'hello'}
    os.environ['COLD_STORAGE_DIR'] = str(tmp_path)
    ref = store_in_cold_storage(node)
    loaded = retrieve_from_cold_storage(ref)
    assert loaded['id'] == 'testnode'
    assert loaded['content'] == 'hello'

# --- Cache Invalidation ---
def test_invalidate_node_cache():
    node_cache.set('Test:1', {'id': 1})
    redis_cache.set('Test:1', {'id': 1})
    invalidate_node_cache(1, 'Test')
    assert node_cache.get('Test:1') is None
    assert redis_cache.get('Test:1') is None

# --- Admin Endpoints ---
def test_admin_prune_auth():
    # No auth
    r = client.post('/api/admin/prune')
    assert r.status_code == 401
    # Wrong auth
    r = client.post('/api/admin/prune', auth=('bad', 'creds'))
    assert r.status_code == 403
    # Correct auth
    r = client.post('/api/admin/prune', auth=('admin', 'changeme'))
    assert r.status_code == 202
    assert r.json()['status'] == 'pruning job triggered'

def test_admin_archive_auth():
    # No auth
    r = client.post('/api/admin/archive', json={'entity_type': 'Test', 'node_ids': ['1','2']})
    assert r.status_code == 401
    # Wrong auth
    r = client.post('/api/admin/archive', json={'entity_type': 'Test', 'node_ids': ['1','2']}, auth=('bad', 'creds'))
    assert r.status_code == 403
    # Correct auth
    r = client.post('/api/admin/archive', json={'entity_type': 'Test', 'node_ids': ['1','2']}, auth=('admin', 'changeme'))
    assert r.status_code == 202
    assert r.json()['status'] == 'archive job triggered' 