from typing import List, Dict, Any, Optional

class GraphTraversal:
    def __init__(self, graph_db):
        self.graph_db = graph_db
        self.max_nodes_per_hop = 25

    def traverse_from_seeds(
        self,
        seed_node_ids: List[str],
        max_hops: int = 2,
        max_nodes_per_hop: int = 25,
        relationship_types: Optional[List[str]] = None,
        node_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Breadth-first multi-hop traversal from seed nodes, with relationship/node type filtering and cycle avoidance.
        """
        visited = set()
        nodes = []
        relationships = []
        queue = [(node_id, 0) for node_id in seed_node_ids]
        self.max_nodes_per_hop = max_nodes_per_hop

        rel_filter = self._build_relationship_filter(relationship_types)
        node_filter = self._build_node_filter(node_types)

        while queue:
            current_id, hop = queue.pop(0)
            if hop > max_hops or current_id in visited:
                continue
            visited.add(current_id)
            results = self._expand_from_node(current_id, hop, max_hops, rel_filter, node_filter)
            for record in results:
                m = record.get('m')
                r = record.get('r')
                if m and m['id'] not in visited:
                    nodes.append(m)
                    queue.append((m['id'], hop + 1))
                if r:
                    relationships.append(r)
                if len(nodes) >= max_nodes_per_hop:
                    break
            if len(nodes) >= max_nodes_per_hop:
                break
        return {"nodes": nodes, "relationships": relationships}

    def _expand_from_node(self, node_id: str, current_hop: int, max_hops: int,
                         relationship_filter: str = "", node_filter: str = ""):
        """Expand a single hop from the given node using Cypher."""
        query = f"""
        MATCH (n)-[r{relationship_filter}]->(m{node_filter})
        WHERE n.id = $node_id
        RETURN m, r
        UNION
        MATCH (m{node_filter})-[r{relationship_filter}]->(n)
        WHERE n.id = $node_id
        RETURN m, r
        LIMIT $limit
        """
        return self.graph_db.run_query(query, {"node_id": node_id, "limit": self.max_nodes_per_hop})

    def _build_relationship_filter(self, relationship_types: Optional[List[str]]) -> str:
        if relationship_types:
            rels = '|'.join(relationship_types)
            return f":{rels}"
        return ""

    def _build_node_filter(self, node_types: Optional[List[str]]) -> str:
        if node_types:
            types = ':'.join(node_types)
            return f":{types}"
        return ""

    def find_related_tasks(self, entity_id: str, status_filter: Optional[List[str]] = None):
        """Find tasks related to a specific entity (by RELATED_TO or EXTRACTED_FROM)."""
        status_clause = ""
        if status_filter:
            status_list = ", ".join([f"'{s}'" for s in status_filter])
            status_clause = f"AND task.status IN [{status_list}]"
        query = f"""
        MATCH (entity)-[:RELATED_TO]-(task:Task)
        WHERE entity.id = $entity_id {status_clause}
        RETURN task
        UNION
        MATCH (entity)<-[:MENTIONED_IN]-(msg:Message)<-[:EXTRACTED_FROM]-(task:Task)
        WHERE entity.id = $entity_id {status_clause}
        RETURN task
        """
        return self.graph_db.run_query(query, {"entity_id": entity_id})

    def find_task_dependencies(self, task_id: str):
        """Find tasks that the given task depends on (DEPENDS_ON)."""
        query = """
        MATCH (task:Task)-[r:DEPENDS_ON]->(dep:Task)
        WHERE task.id = $task_id
        RETURN dep, r
        """
        return self.graph_db.run_query(query, {"task_id": task_id})

    def find_user_context(self, entity_id: str, user_id: str):
        """Find paths connecting an entity to the user, prioritizing USER_* relationships."""
        query = """
        MATCH p = shortestPath((user:User)-[*..4]-(entity))
        WHERE user.id = $user_id AND entity.id = $entity_id
        RETURN p
        """
        return self.graph_db.run_query(query, {"user_id": user_id, "entity_id": entity_id}) 