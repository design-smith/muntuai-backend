from neo4j import GraphDatabase
from backend.GraphRAG.graphrag.config import get_settings
from backend.GraphRAG.graphrag.db.graph_schema import NODE_TYPES, RELATIONSHIP_TYPES

class Neo4jWrapper:
    def __init__(self):
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    
    def close(self):
        self.driver.close()
    
    def create_node(self, label: str, properties: dict):
        # Validate node type and properties
        if label not in NODE_TYPES:
            raise ValueError(f"Unknown node type: {label}")
        for prop in properties:
            if prop not in NODE_TYPES[label]:
                raise ValueError(f"Invalid property '{prop}' for node type '{label}'")
        with self.driver.session() as session:
            query = (
                f"CREATE (n:{label} $properties) "
                "RETURN n"
            )
            result = session.run(query, properties=properties)
            return result.single()
    
    def merge_node(self, label: str, properties: dict):
        """
        Create a node if it doesn't exist, or update it if it does.
        Uses the 'id' property as the unique identifier.
        """
        if label not in NODE_TYPES:
            raise ValueError(f"Unknown node type: {label}")
        for prop in properties:
            if prop not in NODE_TYPES[label]:
                raise ValueError(f"Invalid property '{prop}' for node type '{label}'")
        
        with self.driver.session() as session:
            query = (
                f"MERGE (n:{label} {{id: $id}}) "
                "SET n += $properties "
                "RETURN n"
            )
            result = session.run(query, id=properties['id'], properties=properties)
            return result.single()
    
    def node_exists(self, label: str, match_props: dict) -> bool:
        """
        Check if a node exists with the given properties.
        """
        with self.driver.session() as session:
            query = (
                f"MATCH (n:{label}) WHERE " +
                " AND ".join([f"n.{k} = ${k}" for k in match_props.keys()]) +
                " RETURN count(n) as count"
            )
            result = session.run(query, **match_props)
            return result.single()["count"] > 0
    
    def get_node(self, label: str, match_props: dict):
        """
        Get a single node matching the given properties.
        Returns None if no node is found.
        """
        with self.driver.session() as session:
            query = (
                f"MATCH (n:{label}) WHERE " +
                " AND ".join([f"n.{k} = ${k}" for k in match_props.keys()]) +
                " RETURN n"
            )
            result = session.run(query, **match_props)
            record = result.single()
            return record["n"] if record else None

    def create_relationship(self, from_label: str, to_label: str, rel_type: str, 
                          from_props: dict, to_props: dict, rel_props: dict = None):
        # Validate relationship type and properties
        if rel_type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unknown relationship type: {rel_type}")
        valid_sources = RELATIONSHIP_TYPES[rel_type]["valid_sources"]
        valid_targets = RELATIONSHIP_TYPES[rel_type]["valid_targets"]
        if from_label not in valid_sources or to_label not in valid_targets:
            raise ValueError(f"Invalid source/target for relationship {rel_type}: {from_label} -> {to_label}")
        for prop in (rel_props or {}):
            if prop not in RELATIONSHIP_TYPES[rel_type]["properties"]:
                raise ValueError(f"Invalid property '{prop}' for relationship type '{rel_type}'")
        with self.driver.session() as session:
            query = (
                f"MATCH (a:{from_label}), (b:{to_label}) "
                "WHERE a.id = $from_id AND b.id = $to_id "
                f"CREATE (a)-[r:{rel_type} $rel_props]->(b) "
                "RETURN r"
            )
            result = session.run(query, 
                               from_id=from_props['id'],
                               to_id=to_props['id'],
                               rel_props=rel_props or {})
            return result.single()

    def merge_relationship(self, from_label: str, to_label: str, rel_type: str,
                         from_props: dict, to_props: dict, rel_props: dict = None):
        """
        Create a relationship if it doesn't exist, or update it if it does.
        """
        if rel_type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unknown relationship type: {rel_type}")
        valid_sources = RELATIONSHIP_TYPES[rel_type]["valid_sources"]
        valid_targets = RELATIONSHIP_TYPES[rel_type]["valid_targets"]
        if from_label not in valid_sources or to_label not in valid_targets:
            raise ValueError(f"Invalid source/target for relationship {rel_type}: {from_label} -> {to_label}")
        for prop in (rel_props or {}):
            if prop not in RELATIONSHIP_TYPES[rel_type]["properties"]:
                raise ValueError(f"Invalid property '{prop}' for relationship type '{rel_type}'")
        
        with self.driver.session() as session:
            query = (
                f"MATCH (a:{from_label}), (b:{to_label}) "
                "WHERE a.id = $from_id AND b.id = $to_id "
                f"MERGE (a)-[r:{rel_type}]->(b) "
                "SET r += $rel_props "
                "RETURN r"
            )
            result = session.run(query,
                               from_id=from_props['id'],
                               to_id=to_props['id'],
                               rel_props=rel_props or {})
            return result.single()

    def update_node(self, label: str, match_props: dict, update_props: dict):
        with self.driver.session() as session:
            set_clause = ", ".join([f"n.{k} = $update_{k}" for k in update_props.keys()])
            query = (
                f"MATCH (n:{label}) WHERE " +
                " AND ".join([f"n.{k} = ${k}" for k in match_props.keys()]) +
                f" SET {set_clause} RETURN n"
            )
            params = {**match_props, **{f"update_{k}": v for k, v in update_props.items()}}
            result = session.run(query, **params)
            return [record["n"] for record in result]

    def delete_node(self, label: str, match_props: dict):
        with self.driver.session() as session:
            query = (
                f"MATCH (n:{label}) WHERE " +
                " AND ".join([f"n.{k} = ${k}" for k in match_props.keys()]) +
                " DETACH DELETE n"
            )
            session.run(query, **match_props)

    def get_relationship(self, from_label: str, to_label: str, rel_type: str, from_props: dict, to_props: dict):
        with self.driver.session() as session:
            query = (
                f"MATCH (a:{from_label})-[r:{rel_type}]->(b:{to_label}) "
                "WHERE "
                + " AND ".join([f"a.{k} = $from_{k}" for k in from_props.keys()])
                + " AND "
                + " AND ".join([f"b.{k} = $to_{k}" for k in to_props.keys()])
                + " RETURN r"
            )
            params = {**{f"from_{k}": v for k, v in from_props.items()}, **{f"to_{k}": v for k, v in to_props.items()}}
            result = session.run(query, **params)
            return [record["r"] for record in result]

    def delete_relationship(self, from_label: str, to_label: str, rel_type: str, from_props: dict, to_props: dict):
        with self.driver.session() as session:
            query = (
                f"MATCH (a:{from_label})-[r:{rel_type}]->(b:{to_label}) "
                "WHERE "
                + " AND ".join([f"a.{k} = $from_{k}" for k in from_props.keys()])
                + " AND "
                + " AND ".join([f"b.{k} = $to_{k}" for k in to_props.keys()])
                + " DELETE r"
            )
            params = {**{f"from_{k}": v for k, v in from_props.items()}, **{f"to_{k}": v for k, v in to_props.items()}}
            session.run(query, **params)

    def run_query(self, query: str, parameters: dict = None):
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record for record in result]

    def traverse_from_nodes(self, node_ids: list, max_hops: int = 2) -> dict:
        """
        Traverse the graph from the given node IDs up to max_hops, returning a subgraph (nodes, relationships, paths).
        """
        with self.driver.session() as session:
            query = f'''
            MATCH (start)
            WHERE start.id IN $node_ids
            MATCH p = (start)-[*1..{max_hops}]-(n)
            WITH collect(DISTINCT n) + collect(DISTINCT start) AS ns, collect(DISTINCT relationships(p)) AS rels
            UNWIND ns AS node
            UNWIND rels AS rel_list
            UNWIND rel_list AS rel
            RETURN collect(DISTINCT node) AS nodes, collect(DISTINCT rel) AS relationships
            '''
            result = session.run(query, {"node_ids": node_ids})
            record = result.single()
            nodes = record["nodes"] if record and "nodes" in record else []
            relationships = record["relationships"] if record and "relationships" in record else []
            node_dicts = [
                {"id": n.get("id"), "labels": list(n.labels), **dict(n)} for n in nodes
            ]
            rel_dicts = [
                {
                    "type": r.type,
                    "source": r.start_node.get("id"),
                    "target": r.end_node.get("id"),
                    **dict(r)
                } for r in relationships
            ]
            return {"nodes": node_dicts, "relationships": rel_dicts}

    def get_all_nodes(self) -> list:
        """
        Get all nodes from the database with their properties and labels.
        
        Returns:
            List of dictionaries containing node data
        """
        with self.driver.session() as session:
            query = """
            MATCH (n)
            RETURN n
            """
            result = session.run(query)
            nodes = []
            for record in result:
                node = record["n"]
                nodes.append({
                    "id": node.get("id"),
                    "labels": list(node.labels),
                    **dict(node)
                })
            return nodes

if __name__ == "__main__":
    print("Testing Neo4j connectivity...")
    try:
        db = Neo4jWrapper()
        # Try a simple query
        result = db.run_query("RETURN 1 AS test")
        print("Connection successful! Result:", result[0]["test"] if result else None)
        db.close()
    except Exception as e:
        print("Connection failed:", e) 