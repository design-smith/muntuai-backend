import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.GraphRAG.graphrag.db.graph_db import Neo4jWrapper
from backend.GraphRAG.graphrag.db.graph_schema import (
    initialize_graph_schema, NODE_TYPES, RELATIONSHIP_TYPES,
    classify_communication_context, infer_relationship_from_communication
)
from datetime import datetime

def cleanup_test_nodes():
    neo4j = Neo4jWrapper()
    with neo4j.driver.session() as session:
        session.run("MATCH (n) WHERE n.id IN ['p1', 'p2', 'p3', 'p4', 'u1', 'u2'] DETACH DELETE n")
    neo4j.close()

def test_schema_initialization():
    print("Testing schema initialization...")
    neo4j = Neo4jWrapper()
    initialize_graph_schema(neo4j)
    print("Schema initialized.")
    neo4j.close()

def test_node_creation():
    print("Testing node creation (valid/invalid)...")
    cleanup_test_nodes()
    neo4j = Neo4jWrapper()
    # Valid node
    try:
        neo4j.create_node("Person", {"id": "p1", "name": "Alice", "email": "alice@example.com"})
        print("Valid node creation: PASS")
    except Exception as e:
        print("Valid node creation: FAIL", e)
    # Invalid node type
    try:
        neo4j.create_node("Alien", {"id": "a1"})
        print("Invalid node type: FAIL")
    except Exception:
        print("Invalid node type: PASS")
    # Invalid property
    try:
        neo4j.create_node("Person", {"id": "p2", "foo": "bar"})
        print("Invalid property: FAIL")
    except Exception:
        print("Invalid property: PASS")
    neo4j.close()

def test_relationship_creation():
    print("Testing relationship creation (valid/invalid)...")
    cleanup_test_nodes()
    neo4j = Neo4jWrapper()
    # Create nodes for relationship
    neo4j.create_node("User", {"id": "u1", "name": "User1", "email": "user1@example.com"})
    neo4j.create_node("Person", {"id": "p3", "name": "Bob", "email": "bob@example.com"})
    # Valid relationship
    try:
        neo4j.create_relationship(
            from_label="User", to_label="Person", rel_type="USER_KNOWS",
            from_props={"id": "u1"}, to_props={"id": "p3"},
            rel_props={"relationship_strength": 0.8}
        )
        print("Valid relationship creation: PASS")
    except Exception as e:
        print("Valid relationship creation: FAIL", e)
    # Invalid relationship type
    try:
        neo4j.create_relationship(
            from_label="User", to_label="Person", rel_type="ALIEN_CONTACT",
            from_props={"id": "u1"}, to_props={"id": "p3"}
        )
        print("Invalid relationship type: FAIL")
    except Exception:
        print("Invalid relationship type: PASS")
    # Invalid property
    try:
        neo4j.create_relationship(
            from_label="User", to_label="Person", rel_type="USER_KNOWS",
            from_props={"id": "u1"}, to_props={"id": "p3"},
            rel_props={"foo": "bar"}
        )
        print("Invalid relationship property: FAIL")
    except Exception:
        print("Invalid relationship property: PASS")
    neo4j.close()

def test_context_classification():
    print("Testing context classification...")
    tags = classify_communication_context(
        message_content="Let's meet for a research project with the professor.",
        sender="alice@university.edu",
        recipients=["bob@university.edu"],
        channel="email"
    )
    print("Context tags:", tags)

def test_relationship_inference():
    print("Testing relationship inference...")
    cleanup_test_nodes()
    neo4j = Neo4jWrapper()
    # Create nodes
    neo4j.create_node("User", {"id": "u2", "name": "User2", "email": "user2@example.com"})
    neo4j.create_node("Person", {"id": "p4", "name": "Carol", "email": "carol@example.com"})
    # Message history
    message_history = [
        {"timestamp": datetime(2023, 1, 1), "sentiment": 0.5, "channel_id": "email"},
        {"timestamp": datetime(2023, 2, 1), "sentiment": 0.7, "channel_id": "email"},
        {"timestamp": datetime(2023, 3, 1), "sentiment": 0.9, "channel_id": "slack"}
    ]
    context_tags = ["professional", "project"]
    infer_relationship_from_communication("u2", "p4", message_history, context_tags, neo4j)
    print("Relationship inference: PASS (check Neo4j for USER_KNOWS rel)")
    neo4j.close()

if __name__ == "__main__":
    test_schema_initialization()
    test_node_creation()
    test_relationship_creation()
    test_context_classification()
    test_relationship_inference() 