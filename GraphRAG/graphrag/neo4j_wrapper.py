from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

class Neo4jWrapper:
    def __init__(self):
        """Initialize Neo4j connection."""
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        
    def close(self):
        """Close the database connection."""
        self.driver.close()
        
    def create_node_type(self, node_type, properties):
        """Create a node type with properties."""
        with self.driver.session() as session:
            # Create constraints for required properties
            for prop_name, prop_type in properties.items():
                if prop_type == "string":
                    session.run(
                        f"CREATE CONSTRAINT {node_type}_{prop_name}_constraint IF NOT EXISTS "
                        f"FOR (n:{node_type}) REQUIRE n.{prop_name} IS NOT NULL"
                    )
                    
    def create_relationship_type(self, relationship_type):
        """Create a relationship type."""
        with self.driver.session() as session:
            # Neo4j doesn't support constraints on relationship types directly
            # Instead, we'll create a unique constraint on the relationship type name
            session.run(
                f"CREATE CONSTRAINT {relationship_type}_constraint IF NOT EXISTS "
                f"FOR ()-[r:{relationship_type}]-() "
                f"REQUIRE r.type IS UNIQUE"
            )
            
    def create_index(self, node_type, property_name):
        """Create an index on a property."""
        with self.driver.session() as session:
            session.run(
                f"CREATE INDEX {node_type}_{property_name}_index IF NOT EXISTS "
                f"FOR (n:{node_type}) ON (n.{property_name})"
            )
            
    def create_node(self, node_type, properties):
        """Create a node with properties."""
        with self.driver.session() as session:
            query = (
                f"CREATE (n:{node_type} $properties) "
                "RETURN n"
            )
            session.run(query, properties=properties)
            
    def update_node(self, node_type, node_id, properties):
        """Update a node's properties."""
        with self.driver.session() as session:
            query = (
                f"MATCH (n:{node_type} {{id: $node_id}}) "
                "SET n += $properties "
                "RETURN n"
            )
            session.run(query, node_id=node_id, properties=properties)
            
    def create_relationship(self, from_type, from_id, to_type, to_id, relationship_type):
        """Create a relationship between two nodes."""
        with self.driver.session() as session:
            query = (
                f"MATCH (a:{from_type} {{id: $from_id}}), "
                f"(b:{to_type} {{id: $to_id}}) "
                f"CREATE (a)-[r:{relationship_type}]->(b) "
                "RETURN r"
            )
            session.run(query, from_id=from_id, to_id=to_id) 