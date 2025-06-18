from typing import Dict, List, Any, Optional, Tuple
import uuid
from datetime import datetime
import numpy as np
from thefuzz import fuzz
from thefuzz import process

class EntityResolutionEngine:
    def __init__(
        self, 
        graph_db, 
        vector_db, 
        embedding_service,
        similarity_threshold=0.85,
        fuzzy_match_threshold=85
    ):
        """
        Initialize the entity resolution engine
        """
        self.graph_db = graph_db
        self.vector_db = vector_db
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.fuzzy_match_threshold = fuzzy_match_threshold

    def resolve_entity(
        self, 
        entity_data: Dict[str, Any], 
        entity_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to resolve an entity with existing entities using multiple strategies
        """
        exact_match = self._match_by_identifiers(entity_data, entity_type)
        if exact_match:
            return exact_match
        fuzzy_match = self._match_by_fuzzy_name(entity_data, entity_type)
        if fuzzy_match:
            return fuzzy_match
        semantic_match = self._match_by_embedding(entity_data, entity_type)
        if semantic_match:
            return semantic_match
        relationship_match = self._match_by_relationships(entity_data, entity_type)
        if relationship_match:
            return relationship_match
        return None

    def _match_by_identifiers(
        self, 
        entity_data: Dict[str, Any], 
        entity_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Match entity by exact identifiers (email, phone, etc.)
        """
        identifiers = []
        if entity_type == "Person":
            if "email" in entity_data:
                identifiers.append(("email", entity_data["email"]))
            if "phone" in entity_data:
                normalized_phone = self._normalize_phone(entity_data["phone"])
                identifiers.append(("phone", normalized_phone))
            if "social_handles" in entity_data:
                for platform, handle in entity_data["social_handles"].items():
                    identifiers.append((f"social_handles.{platform}", handle))
        elif entity_type == "Organization":
            if "website" in entity_data:
                identifiers.append(("website", self._normalize_url(entity_data["website"])))
            if "domain" in entity_data:
                identifiers.append(("domain", entity_data["domain"]))
            if "tax_id" in entity_data:
                identifiers.append(("tax_id", entity_data["tax_id"]))
        elif entity_type == "Location":
            if "coordinates" in entity_data:
                identifiers.append(("coordinates", entity_data["coordinates"]))
            if "address" in entity_data and "postal_code" in entity_data:
                identifiers.append(("address", entity_data["address"]))
                identifiers.append(("postal_code", entity_data["postal_code"]))
        for property_name, value in identifiers:
            if not value:
                continue
            query = f"""
            MATCH (e:{entity_type})
            WHERE e.{property_name} = $value
            RETURN e
            LIMIT 1
            """
            result = self.graph_db.run_query(query, {"value": value})
            if result and len(result) > 0:
                return result[0]["e"]
        return None

    def _match_by_fuzzy_name(
        self, 
        entity_data: Dict[str, Any], 
        entity_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Match entity by fuzzy name matching
        """
        name_field = "name" if "name" in entity_data else "text"
        if name_field not in entity_data:
            return None
        entity_name = entity_data[name_field]
        query = f"""
        MATCH (e:{entity_type})
        RETURN e.id AS id, e.{name_field} AS name
        LIMIT 100
        """
        candidates = self.graph_db.run_query(query)
        if not candidates:
            return None
        candidate_names = [(c["id"], c["name"]) for c in candidates if c["name"]]
        if not candidate_names:
            return None
        matches = process.extractBests(
            entity_name,
            [c[1] for c in candidate_names],
            scorer=fuzz.token_sort_ratio,
            score_cutoff=self.fuzzy_match_threshold,
            limit=3
        )
        if not matches:
            return None
        best_match_name = matches[0][0]
        for c_id, c_name in candidate_names:
            if c_name == best_match_name:
                best_match_id = c_id
                break
        else:
            return None
        entity_query = f"""
        MATCH (e:{entity_type})
        WHERE e.id = $id
        RETURN e
        """
        entity_result = self.graph_db.run_query(entity_query, {"id": best_match_id})
        if entity_result and len(entity_result) > 0:
            return entity_result[0]["e"]
        return None

    def _match_by_embedding(
        self, 
        entity_data: Dict[str, Any], 
        entity_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Match entity by embedding similarity
        """
        name_field = "name" if "name" in entity_data else "text"
        if name_field not in entity_data:
            return None
        entity_text = entity_data[name_field]
        if "description" in entity_data:
            entity_text += " " + entity_data["description"]
        entity_embedding = self.embedding_service.get_embedding(entity_text)
        search_results = self.vector_db.search(
            collection_name=entity_type,
            query_vector=entity_embedding,
            limit=5
        )
        for result in search_results:
            if result["score"] >= self.similarity_threshold:
                entity_id = result["payload"]["id"]
                entity_query = f"""
                MATCH (e:{entity_type})
                WHERE e.id = $id
                RETURN e
                """
                entity_result = self.graph_db.run_query(entity_query, {"id": entity_id})
                if entity_result and len(entity_result) > 0:
                    return entity_result[0]["e"]
        return None

    def _match_by_relationships(
        self, 
        entity_data: Dict[str, Any], 
        entity_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Match entity by its relationships to other entities
        """
        if "relationships" not in entity_data or not entity_data["relationships"]:
            return None
        related_entities = []
        for rel in entity_data["relationships"]:
            if "target_id" in rel:
                related_entities.append(rel["target_id"])
        if not related_entities:
            return None
        query = f"""
        MATCH (e:{entity_type})-[]-(other)
        WHERE other.id IN $related_ids
        WITH e, count(other) AS shared_count
        WHERE shared_count >= 2
        RETURN e, shared_count
        ORDER BY shared_count DESC
        LIMIT 1
        """
        result = self.graph_db.run_query(query, {"related_ids": related_entities})
        if result and len(result) > 0:
            return result[0]["e"]
        return None

    def merge_entities(
        self,
        source_id: str,
        target_id: str,
        entity_type: str,
        merge_strategy: str = "newer_wins"
    ) -> Dict[str, Any]:
        """
        Merge two entities, preserving relationships and data
        """
        source_query = f"""
        MATCH (e:{entity_type})
        WHERE e.id = $id
        RETURN e
        """
        source_result = self.graph_db.run_query(source_query, {"id": source_id})
        target_result = self.graph_db.run_query(source_query, {"id": target_id})
        if not source_result or not target_result:
            raise ValueError(f"One or both entities not found: {source_id}, {target_id}")
        source_entity = source_result[0]["e"]
        target_entity = target_result[0]["e"]
        merged_properties = self._merge_properties(
            source_entity, 
            target_entity, 
            merge_strategy
        )
        update_query = f"""
        MATCH (e:{entity_type})
        WHERE e.id = $id
        SET e += $properties
        RETURN e
        """
        updated_target = self.graph_db.run_query(
            update_query, 
            {
                "id": target_id,
                "properties": merged_properties
            }
        )
        self._transfer_relationships(source_id, target_id, entity_type)
        mark_merged_query = f"""
        MATCH (e:{entity_type})
        WHERE e.id = $id
        SET e.merged = true, 
            e.merged_into = $target_id,
            e.merged_at = $merged_at
        """
        self.graph_db.run_query(
            mark_merged_query, 
            {
                "id": source_id,
                "target_id": target_id,
                "merged_at": datetime.now().isoformat()
            }
        )
        self._update_entity_embedding(target_id, entity_type, merged_properties)
        merged_query = f"""
        MATCH (e:{entity_type})
        WHERE e.id = $id
        RETURN e
        """
        merged_result = self.graph_db.run_query(merged_query, {"id": target_id})
        return merged_result[0]["e"]

    def _merge_properties(
        self,
        source_entity: Dict[str, Any],
        target_entity: Dict[str, Any],
        merge_strategy: str
    ) -> Dict[str, Any]:
        """
        Merge properties from source to target entity
        """
        merged = {}
        for key, value in target_entity.items():
            if key not in ["id", "labels"]:
                merged[key] = value
        for key, value in source_entity.items():
            if key in ["id", "labels"]:
                continue
            if key not in merged:
                merged[key] = value
            else:
                if merge_strategy == "newer_wins":
                    if key.endswith("_at") or key == "timestamp":
                        source_date = source_entity.get(key)
                        target_date = merged.get(key)
                        if source_date and target_date:
                            if isinstance(source_date, str):
                                source_date = datetime.fromisoformat(source_date)
                            if isinstance(target_date, str):
                                target_date = datetime.fromisoformat(target_date)
                            merged[key] = source_date if source_date > target_date else target_date
                        else:
                            merged[key] = merged[key]
                    elif key == "confidence":
                        merged[key] = max(value, merged[key])
                    else:
                        if not merged[key] and value:
                            merged[key] = value
                elif merge_strategy == "source_wins":
                    merged[key] = value
                elif merge_strategy == "target_wins":
                    pass
        merged["merged_count"] = (target_entity.get("merged_count", 0) or 0) + 1
        return merged

    def _transfer_relationships(
        self,
        source_id: str,
        target_id: str,
        entity_type: str
    ) -> None:
        """
        Transfer all relationships from source to target entity
        """
        outgoing_query = f"""
        MATCH (source:{entity_type})-[r]->(target)
        WHERE source.id = $source_id
        RETURN type(r) AS rel_type, r AS rel, target
        """
        incoming_query = f"""
        MATCH (source)-[r]->(target:{entity_type})
        WHERE target.id = $source_id
        RETURN type(r) AS rel_type, r AS rel, source
        """
        outgoing_rels = self.graph_db.run_query(outgoing_query, {"source_id": source_id})
        incoming_rels = self.graph_db.run_query(incoming_query, {"source_id": source_id})
        for rel in outgoing_rels:
            rel_type = rel["rel_type"]
            rel_props = {k: v for k, v in rel["rel"].items() if k not in ["id", "source", "target", "type"]}
            target_node = rel["target"]
            check_query = f"""
            MATCH (source:{entity_type})-[r:{rel_type}]->(target)
            WHERE source.id = $source_id AND target.id = $target_id
            RETURN count(r) AS rel_count
            """
            check_result = self.graph_db.run_query(
                check_query, 
                {
                    "source_id": target_id, 
                    "target_id": target_node["id"]
                }
            )
            rel_exists = check_result[0]["rel_count"] > 0
            if not rel_exists:
                create_query = f"""
                MATCH (source:{entity_type}), (target)
                WHERE source.id = $source_id AND target.id = $target_id
                CREATE (source)-[r:{rel_type} $props]->(target)
                """
                self.graph_db.run_query(
                    create_query, 
                    {
                        "source_id": target_id, 
                        "target_id": target_node["id"],
                        "props": rel_props
                    }
                )
        for rel in incoming_rels:
            rel_type = rel["rel_type"]
            rel_props = {k: v for k, v in rel["rel"].items() if k not in ["id", "source", "target", "type"]}
            source_node = rel["source"]
            check_query = f"""
            MATCH (source)-[r:{rel_type}]->(target:{entity_type})
            WHERE source.id = $source_id AND target.id = $target_id
            RETURN count(r) AS rel_count
            """
            check_result = self.graph_db.run_query(
                check_query, 
                {
                    "source_id": source_node["id"], 
                    "target_id": target_id
                }
            )
            rel_exists = check_result[0]["rel_count"] > 0
            if not rel_exists:
                create_query = f"""
                MATCH (source), (target:{entity_type})
                WHERE source.id = $source_id AND target.id = $target_id
                CREATE (source)-[r:{rel_type} $props]->(target)
                """
                self.graph_db.run_query(
                    create_query, 
                    {
                        "source_id": source_node["id"], 
                        "target_id": target_id,
                        "props": rel_props
                    }
                )

    def _update_entity_embedding(
        self,
        entity_id: str,
        entity_type: str,
        entity_properties: Dict[str, Any]
    ) -> None:
        """
        Update entity embedding in the vector database
        """
        text_to_embed = entity_properties.get("name", "") or entity_properties.get("text", "")
        if "description" in entity_properties:
            text_to_embed += " " + entity_properties["description"]
        if not text_to_embed:
            return
        embedding = self.embedding_service.get_embedding(text_to_embed)
        self.vector_db.upsert_embedding(
            collection=entity_type,
            id=entity_id,
            vector=embedding,
            payload={
                "id": entity_id,
                "text": text_to_embed[:100],
                "type": entity_type
            }
        )

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number by removing non-digits"""
        return ''.join(c for c in phone if c.isdigit())

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing http/https and trailing slashes"""
        url = url.lower()
        for prefix in ["https://", "http://", "www."]:
            if url.startswith(prefix):
                url = url[len(prefix):]
        return url.rstrip("/")

    def _normalize_name(self, name: str) -> str:
        """Normalize personal name for matching"""
        name = name.lower()
        prefixes = ["mr.", "mrs.", "ms.", "dr.", "prof."]
        suffixes = ["jr.", "sr.", "phd", "md", "dds", "esq"]
        name_parts = name.split()
        if name_parts and name_parts[0].rstrip(".") in prefixes:
            name_parts = name_parts[1:]
        if name_parts and name_parts[-1].rstrip(".") in suffixes:
            name_parts = name_parts[:-1]
        return " ".join(name_parts)

    def batch_resolve_entities(
        self,
        entity_type: str,
        match_threshold: float = 0.7,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Run batch resolution on entities of a specific type
        """
        query = f"""
        MATCH (e:{entity_type})
        WHERE NOT exists(e.merged) OR e.merged = false
        RETURN e
        LIMIT $limit
        """
        entities = self.graph_db.run_query(query, {"limit": limit})
        merge_candidates = []
        processed_pairs = set()
        for i, entity1 in enumerate(entities):
            entity1_data = entity1["e"]
            for j in range(i + 1, len(entities)):
                entity2_data = entities[j]["e"]
                pair_key = tuple(sorted([entity1_data["id"], entity2_data["id"]]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                match_score = self._calculate_entity_similarity(entity1_data, entity2_data)
                if match_score >= match_threshold:
                    merge_candidates.append({
                        "source_id": entity1_data["id"],
                        "target_id": entity2_data["id"],
                        "match_score": match_score,
                        "entity_type": entity_type
                    })
        return merge_candidates

    def _calculate_entity_similarity(
        self,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> float:
        """
        Calculate similarity score between two entities
        """
        text_field = "name" if "name" in entity1 else "text"
        if text_field not in entity1 or text_field not in entity2:
            return 0.0
        text1 = entity1[text_field]
        text2 = entity2[text_field]
        name_similarity = fuzz.token_sort_ratio(text1, text2) / 100.0
        relationship_similarity = self._calculate_relationship_overlap(
            entity1["id"], 
            entity2["id"]
        )
        property_similarity = self._calculate_property_similarity(entity1, entity2)
        weights = {
            "name": 0.6,
            "relationships": 0.3,
            "properties": 0.1
        }
        combined_score = (
            weights["name"] * name_similarity +
            weights["relationships"] * relationship_similarity +
            weights["properties"] * property_similarity
        )
        return combined_score

    def _calculate_relationship_overlap(self, entity1_id: str, entity2_id: str) -> float:
        """
        Calculate relationship overlap between two entities
        """
        query = """
        MATCH (e)-[r]-(other)
        WHERE e.id = $entity_id
        RETURN other.id AS related_id
        """
        related1 = self.graph_db.run_query(query, {"entity_id": entity1_id})
        related2 = self.graph_db.run_query(query, {"entity_id": entity2_id})
        if not related1 or not related2:
            return 0.0
        related_ids1 = set(item["related_id"] for item in related1)
        related_ids2 = set(item["related_id"] for item in related2)
        intersection = len(related_ids1.intersection(related_ids2))
        union = len(related_ids1.union(related_ids2))
        if union == 0:
            return 0.0
        return intersection / union

    def _calculate_property_similarity(
        self,
        entity1: Dict[str, Any],
        entity2: Dict[str, Any]
    ) -> float:
        """
        Calculate property similarity between two entities
        """
        important_props = [
            "email", "phone", "title", "role", "company", 
            "website", "address", "description"
        ]
        matches = 0
        total = 0
        for prop in important_props:
            val1 = entity1.get(prop)
            val2 = entity2.get(prop)
            if val1 is None and val2 is None:
                continue
            total += 1
            if val1 and val2 and val1 == val2:
                matches += 1
        if total == 0:
            return 0.0
        return matches / total 