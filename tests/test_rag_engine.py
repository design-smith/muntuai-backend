import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.GraphRAG.graphrag.engine.rag_engine import GraphRAGEngine

async def main():
    engine = GraphRAGEngine()

    def print_collection_info():
        stats = engine.vector_db.client.get_collection(engine.collection_name)
        print(f"Collection '{engine.collection_name}' stats: vectors count = {stats.vectors_count}")

    # Create two people and a message connecting them
    alice_id = engine.store_document(
        text="Alice is a data scientist at Acme Corp.",
        metadata={"name": "Alice", "title": "data scientist"},
        node_type="Person"
    )
    print(f"After Alice upsert:")
    print_collection_info()

    bob_id = engine.store_document(
        text="Bob is a product manager at Acme Corp.",
        metadata={"name": "Bob", "title": "product manager"},
        node_type="Person"
    )
    print(f"After Bob upsert:")
    print_collection_info()

    msg_id = engine.store_document(
        text="Alice sent a report to Bob about Q2 results.",
        metadata={"sender_id": alice_id},
        node_type="Message"
    )
    # Create relationships from Person to Message
    engine.graph_db.create_relationship(
        from_label="Person",
        to_label="Message",
        rel_type="AUTHORED",
        from_props={"id": alice_id},
        to_props={"id": msg_id},
        rel_props={}
    )
    engine.graph_db.create_relationship(
        from_label="Person",
        to_label="Message",
        rel_type="RECEIVED",
        from_props={"id": bob_id},
        to_props={"id": msg_id},
        rel_props={}
    )
    print(f"After Message upsert:")
    print_collection_info()

    print(f"Created Alice (id={alice_id}), Bob (id={bob_id}), Message (id={msg_id})")

    # Test semantic search
    print("\nSemantic search for 'report results':")
    # Print raw vector search results (before filtering)
    query_embedding = engine.embedding_service.model.encode(["report results"])[0]
    print(f"Query vector size: {len(query_embedding)}")
    raw_results = engine.vector_db.search_vectors(
        collection_name=engine.collection_name,
        query_vector=query_embedding,
        limit=engine.max_results
    )
    print("Raw vector search results:")
    for r in raw_results:
        print({"id": r.id, "score": r.score, "payload": r.payload})

    # Now print filtered semantic search results
    results = engine.semantic_search("report results")
    print("Filtered semantic search results:")
    for r in results:
        print(r)

    # Test hybrid search (semantic + graph)
    print("\nHybrid search for 'report results':")
    hybrid = engine.retrieve_with_context("report results")
    print(hybrid)

    # --- Traversal Test Cases ---
    print("\n--- Traversal: Person to Tasks and Messages ---")
    # Create a task and message related to Alice
    task_id = engine.store_document(
        text="Prepare Q2 report for Acme Corp.",
        metadata={"title": "Prepare Q2 report", "status": "pending"},
        node_type="Task"
    )
    # Link task to Alice (ASSIGNED_TO) and Bob (USER_MANAGES)
    engine.graph_db.create_relationship(
        from_label="Task",
        to_label="Person",
        rel_type="ASSIGNED_TO",
        from_props={"id": task_id},
        to_props={"id": alice_id},
        rel_props={}
    )
    engine.graph_db.create_relationship(
        from_label="User",
        to_label="Task",
        rel_type="USER_MANAGES",
        from_props={"id": bob_id},
        to_props={"id": task_id},
        rel_props={}
    )
    traversal_result = engine.graph_traversal.traverse_from_seeds(
        seed_node_ids=[alice_id],
        max_hops=2
    )
    print("Traversal from Alice (Person):", traversal_result)

    print("\n--- Traversal: Event to Preparation Tasks ---")
    # Create an event and a preparation task
    event_id = engine.store_document(
        text="Q2 Planning Meeting at Acme Corp.",
        metadata={"title": "Q2 Planning Meeting"},
        node_type="Event"
    )
    prep_task_id = engine.store_document(
        text="Prepare slides for Q2 Planning Meeting.",
        metadata={"title": "Prepare slides", "status": "pending"},
        node_type="Task",
        relationships=[
            {"target_type": "Event", "target_id": event_id, "rel_type": "RELATED_TO"}
        ]
    )
    traversal_result = engine.graph_traversal.traverse_from_seeds(
        seed_node_ids=[event_id],
        max_hops=2
    )
    print("Traversal from Event:", traversal_result)

    print("\n--- Traversal: Message to Mentioned Entities and Extracted Tasks ---")
    # Create a message mentioning Bob and extracted task
    mention_msg_id = engine.store_document(
        text="Bob, please review the Q2 slides.",
        metadata={"sender_id": alice_id},
        node_type="Message"
    )
    extracted_task_id = engine.store_document(
        text="Review Q2 slides.",
        metadata={"title": "Review Q2 slides", "status": "pending"},
        node_type="Task",
        relationships=[
            {"target_type": "Message", "target_id": mention_msg_id, "rel_type": "EXTRACTED_FROM"}
        ]
    )
    traversal_result = engine.graph_traversal.traverse_from_seeds(
        seed_node_ids=[mention_msg_id],
        max_hops=2
    )
    print("Traversal from Message:", traversal_result)

    print("\n--- User-Centric Traversal: Context for Upcoming Meeting ---")
    # Find user-centric context for Alice and the event
    user_context = engine.graph_traversal.find_user_context(
        entity_id=event_id,
        user_id=alice_id
    )
    print("User-centric context (Alice to Event):", user_context)

    print("\n--- Task Dependency Traversal ---")
    # Create dependent tasks
    dep_task_id = engine.store_document(
        text="Gather Q2 financial data.",
        metadata={"title": "Gather Q2 data", "status": "pending"},
        node_type="Task"
    )
    engine.graph_db.create_relationship(
        from_label="Task",
        to_label="Task",
        rel_type="DEPENDS_ON",
        from_props={"id": prep_task_id},
        to_props={"id": dep_task_id},
        rel_props={"dependency_type": "data", "blocking": True}
    )
    deps = engine.graph_traversal.find_task_dependencies(prep_task_id)
    print("Task dependencies for prep_task:", deps)

    print("\n--- Edge Case: Traversal from Nonexistent Node ---")
    traversal_result = engine.graph_traversal.traverse_from_seeds(
        seed_node_ids=["nonexistent_id_12345"],
        max_hops=2
    )
    print("Traversal from nonexistent node:", traversal_result)

if __name__ == "__main__":
    asyncio.run(main()) 