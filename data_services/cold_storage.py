import os
import pickle
import gzip
from typing import Any

# Always use the cold_storage directory inside the backend folder
COLD_STORAGE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cold_storage')
COLD_STORAGE_DIR = os.path.abspath(COLD_STORAGE_DIR)
os.makedirs(COLD_STORAGE_DIR, exist_ok=True)

def store_in_cold_storage(node_data: Any) -> str:
    node_id = node_data.get("id")
    archive_reference = os.path.join(COLD_STORAGE_DIR, f"{node_id}.pkl.gz")
    with gzip.open(archive_reference, "wb") as f:
        pickle.dump(node_data, f)
    return archive_reference

def retrieve_from_cold_storage(archive_reference: str) -> Any:
    with gzip.open(archive_reference, "rb") as f:
        node_data = pickle.load(f)
    return node_data 