import re
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
import spacy

class EntityExtractor:
    def __init__(self, nlp_model="en_core_web_md", confidence_threshold=0.7):
        self.nlp = spacy.load(nlp_model)
        self.confidence_threshold = confidence_threshold
        self.custom_patterns = [
            {"label": "EMAIL", "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"},
            {"label": "PHONE", "pattern": r"(\+\d{1,2}\s?)?(\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}"},
            {"label": "URL", "pattern": r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"}
        ]
        self._add_custom_patterns()
        self.entity_type_mapping = {
            "PERSON": "Person",
            "ORG": "Organization",
            "GPE": "Location",
            "LOC": "Location",
            "FAC": "Location",
            "EMAIL": "ContactInfo",
            "PHONE": "ContactInfo",
            "URL": "ContactInfo",
            "DATE": "DateTime",
            "TIME": "DateTime",
            "MONEY": "FinancialInfo",
            "PRODUCT": "Product"
        }

    def _add_custom_patterns(self):
        pattern_matcher = self.nlp.add_pipe("entity_ruler", before="ner")
        for pattern_def in self.custom_patterns:
            pattern_matcher.add_patterns([{
                "label": pattern_def["label"],
                "pattern": [{"TEXT": {"REGEX": pattern_def["pattern"]}}]
            }])

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        doc = self.nlp(text)
        entities = []
        for ent in doc.ents:
            entity_type = self.entity_type_mapping.get(ent.label_, "Unknown")
            if entity_type == "Unknown":
                continue
            confidence = 0.8
            if confidence < self.confidence_threshold:
                continue
            entity = {
                "text": ent.text,
                "type": entity_type,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
                "confidence": confidence,
                "context": self._get_entity_context(text, ent),
                "extracted_at": datetime.now()
            }
            entities.append(entity)
        # --- Regex extraction for phone, email, url ---
        regex_types = [
            ("EMAIL", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
            ("PHONE", r"(\+\d{1,2}\s?)?(\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}"),
            ("URL", r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"),
        ]
        for label, pattern in regex_types:
            for match in re.finditer(pattern, text):
                # Check if already present
                if any(e['start_char'] == match.start() and e['end_char'] == match.end() for e in entities):
                    continue
                entity = {
                    "text": match.group(),
                    "type": "ContactInfo",
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "confidence": 0.95,
                    "context": self._get_entity_context(text, match),
                    "extracted_at": datetime.now()
                }
                entities.append(entity)
        deduplicated = self._deduplicate_entities(entities)
        return deduplicated

    def _get_entity_context(self, full_text: str, entity_span) -> str:
        # Accept both spaCy span and regex match
        if hasattr(entity_span, 'start_char') and hasattr(entity_span, 'end_char'):
            start = max(0, entity_span.start_char - 50)
            end = min(len(full_text), entity_span.end_char + 50)
        else:
            start = max(0, entity_span.start() - 50)
            end = min(len(full_text), entity_span.end() + 50)
        context = full_text[start:end]
        if start > 0:
            context = "..." + context
        if end < len(full_text):
            context = context + "..."
        return context

    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped = {}
        for entity in entities:
            key = f"{entity['type']}|{entity['text'].lower()}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(entity)
        deduplicated = []
        for entities_group in grouped.values():
            entities_group.sort(key=lambda x: x["confidence"], reverse=True)
            deduplicated.append(entities_group[0])
        return deduplicated

    def extract_relationships(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        relationships = []
        entity_spans = {}
        for entity in entities:
            span_key = f"{entity['start_char']}:{entity['end_char']}"
            entity_spans[span_key] = entity
        doc = self.nlp(text)
        for sent in doc.sents:
            sent_entities = []
            for ent in doc.ents:
                if ent.start_char >= sent.start_char and ent.end_char <= sent.end_char:
                    span_key = f"{ent.start_char}:{ent.end_char}"
                    if span_key in entity_spans:
                        sent_entities.append(entity_spans[span_key])
            if len(sent_entities) >= 2:
                for i in range(len(sent_entities)):
                    for j in range(i+1, len(sent_entities)):
                        entity1 = sent_entities[i]
                        entity2 = sent_entities[j]
                        if entity1["type"] == entity2["type"]:
                            continue
                        rel_type = self._infer_relationship_type(entity1["type"], entity2["type"])
                        if rel_type:
                            relationship = {
                                "source_entity": entity1,
                                "target_entity": entity2,
                                "relationship_type": rel_type,
                                "confidence": 0.6,
                                "extracted_from": sent.text,
                                "extracted_at": datetime.now()
                            }
                            relationships.append(relationship)
        return relationships

    def _infer_relationship_type(self, source_type: str, target_type: str) -> Optional[str]:
        relationship_mapping = {
            ("Person", "Organization"): "AFFILIATED_WITH",
            ("Organization", "Person"): "HAS_MEMBER",
            ("Person", "Location"): "LOCATED_AT",
            ("Organization", "Location"): "LOCATED_AT"
        }
        return relationship_mapping.get((source_type, target_type)) 