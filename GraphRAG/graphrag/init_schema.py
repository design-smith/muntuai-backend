import os
import sys

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.GraphRAG.graphrag.db.graph_db import Neo4jWrapper
from backend.GraphRAG.graphrag.db.graph_schema import initialize_graph_schema

def main():
    print("Initializing Neo4j schema...")
    try:
        # Initialize Neo4j connection
        neo4j = Neo4jWrapper()
        
        # Initialize schema (creates constraints and indexes)
        initialize_graph_schema(neo4j)
        
        print("Schema initialization completed successfully!")
    except Exception as e:
        print(f"Error initializing schema: {e}")
    finally:
        if 'neo4j' in locals():
            neo4j.close()

if __name__ == "__main__":
    main() 