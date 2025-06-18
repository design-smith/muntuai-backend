import os
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from GraphRAG.graphrag.db.graph_db import Neo4jWrapper
from mongo_to_neo4j_sync import COLLECTIONS, COLLECTION_LABEL_MAP, RELATIONSHIP_MAP

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")


def verify_and_repair():
    print("[VERIFY] Starting periodic sync verification...")
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    neo4j = Neo4jWrapper()

    # 1. Ensure all MongoDB docs have a Neo4j node
    for coll in COLLECTIONS:
        label = COLLECTION_LABEL_MAP[coll]
        print(f"[VERIFY] Checking collection: {coll}")
        for doc in db[coll].find():
            doc_id = str(doc["_id"])
            # Check node
            nodes = neo4j.get_node(label, {"id": doc_id})
            if not nodes:
                print(f"[REPAIR] Missing node in Neo4j for {label} id={doc_id}. Creating...")
                neo4j.create_node(label, {**doc, "id": doc_id})
            # Check relationships
            for (map_coll, fk, from_label, rel_type, to_label, from_field, to_field) in RELATIONSHIP_MAP:
                if map_coll == coll and fk in doc and doc[fk]:
                    from_id = str(doc[fk])
                    to_id = doc_id
                    rels = neo4j.get_relationship(from_label, to_label, rel_type, {from_field: from_id}, {to_field: to_id})
                    if not rels:
                        print(f"[REPAIR] Missing relationship {rel_type} {from_label}({from_id}) -> {to_label}({to_id}). Creating...")
                        try:
                            neo4j.create_relationship(from_label, to_label, rel_type, {from_field: from_id}, {to_field: to_id})
                        except Exception as e:
                            print(f"[REPAIR] Relationship create error: {e}")

    # 2. Remove orphaned Neo4j nodes (no corresponding MongoDB doc)
    for coll in COLLECTIONS:
        label = COLLECTION_LABEL_MAP[coll]
        all_nodes = neo4j.get_node(label, {})
        mongo_ids = set(str(doc["_id"]) for doc in db[coll].find())
        for node in all_nodes:
            node_id = node.get("id")
            if node_id and node_id not in mongo_ids:
                print(f"[REPAIR] Orphaned node in Neo4j for {label} id={node_id}. Deleting...")
                neo4j.delete_node(label, {"id": node_id})

    # 3. Remove orphaned relationships (where either node is missing)
    # (This is handled by Neo4j's DETACH DELETE, but you can add more logic if needed)

    neo4j.close()
    print("[VERIFY] Sync verification and repair complete.")

if __name__ == "__main__":
    verify_and_repair() 