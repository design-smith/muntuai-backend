# Node type definitions for universal GraphRAG schema
# Each node type is a dict of property names and types (for documentation and validation)

NODE_TYPES = {
    "User": {
        "id": "string",
        "name": "string",
        "email": "string",
        "created_at": "datetime",
        "profile": "json",
        "first_name": "string",
        "last_name": "string",
        "resume_summary": "string"
    },
    "Person": {
        "id": "string",
        "name": "string",
        "email": "string",
        "phone": "string",
        "title": "string",
        "organization_id": "string",
        "first_contact_date": "datetime",
        "last_contact_date": "datetime",
        "source": "string",
        "embedding_id": "string",
        "created_at": "datetime"
    },
    "Organization": {
        "id": "string",
        "name": "string",
        "type": "string",
        "website": "string",
        "description": "string",
        "location": "string",
        "embedding_id": "string",
        "created_at": "datetime"
    },
    "Skill": {
        "id": "string",
        "name": "string",
        "category": "string",
        "created_at": "datetime"
    },
    "Certification": {
        "id": "string",
        "name": "string",
        "issuer": "string",
        "issue_date": "datetime",
        "expiry_date": "datetime",
        "created_at": "datetime"
    },
    "Language": {
        "id": "string",
        "name": "string",
        "proficiency": "string",
        "created_at": "datetime"
    },
    "Message": {
        "id": "string",
        "content": "string",
        "sender_id": "string",
        "channel_id": "string",
        "thread_id": "string",
        "timestamp": "datetime",
        "read_status": "string",
        "has_attachments": "boolean",
        "sentiment": "float",
        "intent": "string",
        "is_actionable": "boolean",
        "reply_to_id": "string",
        "embedding_id": "string",
        "created_at": "datetime"
    },
    "Event": {
        "id": "string",
        "title": "string",
        "description": "string",
        "start_time": "datetime",
        "end_time": "datetime",
        "location": "string",
        "embedding_id": "string",
        "created_at": "datetime"
    },
    "Location": {
        "id": "string",
        "name": "string",
        "address": "string",
        "coordinates": "list[float]",
        "type": "string",
        "embedding_id": "string"
    },
    "Task": {
        "id": "string",
        "title": "string",
        "status": "string",          # "pending", "in_progress", "completed", "canceled"
        "created_date": "datetime", # When the task was created (by AI or user)
        "source_type": "string",    # "ai_generated", "user_created", "extracted_email", etc.
        "description": "string",
        "priority": "string",       # "high", "medium", "low"
        "due_date": "datetime",     # Deadline if applicable
        "completion_date": "datetime", # When marked complete
        "horizon": "string",        # "daily", "weekly", "monthly"
        "recurrence": "string",     # For recurring tasks
        "estimated_time": "float",  # Time estimate to complete (hours)
        "tags": "list[string]",     # Array of topic/project tags
        "confidence_score": "float",# AI's confidence in extracted tasks
        "assignee_id": "string",
        "creator_id": "string",
        "is_actionable": "boolean",
        "reminder_date": "datetime",
        "embedding_id": "string",
        "created_at": "datetime"
    },
    "Channel": {
        "id": "string",
        "name": "string",
        "type": "string",
        "provider": "string",
        "is_connected": "boolean",
        "connection_status": "string",
        "last_synced": "datetime",
        "credentials_id": "string",
        "settings": "json",
        "embedding_id": "string",
        "created_at": "datetime"
    },
    "Thread": {
        "id": "string",
        "title": "string",
        "status": "string",
        "created_date": "datetime",
        "last_updated": "datetime",
        "channel_id": "string",
        "external_id": "string",
        "participants_count": "int",
        "message_count": "int",
        "embedding_id": "string",
        "created_at": "datetime"
    }
}

def cypher_constraints_for_node_types(node_types=NODE_TYPES):
    """
    Generate Cypher statements for unique constraints and indexes for each node type.
    """
    cypher = []
    for label, props in node_types.items():
        # Unique constraint on id
        cypher.append(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE;")
        # Indexes for key properties (except id)
        for prop in props:
            if prop != "id":
                cypher.append(f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.{prop});")
    return cypher

# Universal relationship types for any user context
RELATIONSHIP_TYPES = {
    # User-centric relationships
    "USER_KNOWS": {
        "valid_sources": ["User"],
        "valid_targets": ["Person"],
        "properties": ["relationship_strength", "first_contact_date", "last_contact_date", "communication_frequency", "channels", "context_tags"]
    },
    "USER_CONNECTED_TO": {
        "valid_sources": ["User"],
        "valid_targets": ["Organization"],
        "properties": ["connection_type", "start_date", "active", "context_tags"]
    },
    "USER_COMMUNICATES_VIA": {
        "valid_sources": ["User"],
        "valid_targets": ["Channel"],
        "properties": ["frequency", "last_used", "primary", "usage_pattern"]
    },
    "USER_PARTICIPATES_IN": {
        "valid_sources": ["User"],
        "valid_targets": ["Event"],
        "properties": ["role", "status", "importance", "recurrence"]
    },
    "USER_VISITS": {
        "valid_sources": ["User"],
        "valid_targets": ["Location"],
        "properties": ["visit_frequency", "last_visit", "context_tags", "typical_duration"]
    },
    "USER_MANAGES": {
        "valid_sources": ["User"],
        "valid_targets": ["Task"],
        "properties": ["assignment_date", "reminder_set", "priority_override"]
    },
    # Entity-to-entity relationships
    "CONNECTED_TO": {
        "valid_sources": ["Person"],
        "valid_targets": ["Person"],
        "properties": ["relationship_context", "inferred_closeness", "communication_frequency"]
    },
    "AFFILIATED_WITH": {
        "valid_sources": ["Person"],
        "valid_targets": ["Organization"],
        "properties": ["affiliation_type", "inferred_role", "context_tags"]
    },
    "PARTICIPATES_IN": {
        "valid_sources": ["Person"],
        "valid_targets": ["Event"],
        "properties": ["role", "status", "invited_by"]
    },
    "LOCATED_AT": {
        "valid_sources": ["Person", "Organization", "Event"],
        "valid_targets": ["Location"],
        "properties": ["relationship_type", "frequency", "context_tags"]
    },
    # Communication relationships
    "AUTHORED": {
        "valid_sources": ["Person", "User"],
        "valid_targets": ["Message"],
        "properties": ["timestamp", "channel_id", "message_type", "context_tags"]
    },
    "RECEIVED": {
        "valid_sources": ["Person", "User"],
        "valid_targets": ["Message"],
        "properties": ["timestamp", "read_status", "delivery_status"]
    },
    "MENTIONED_IN": {
        "valid_sources": ["Person", "Organization", "Location", "Event"],
        "valid_targets": ["Message"],
        "properties": ["mention_context", "sentiment", "significance"]
    },
    "RELATED_TO": {
        "valid_sources": ["Task"],
        "valid_targets": ["Event", "Message", "Organization", "Location"],
        "properties": ["relationship_type", "relevance_score"]
    },
    # Identity resolution
    "SAME_AS": {
        "valid_sources": ["Person", "Organization"],
        "valid_targets": ["Person", "Organization"],
        "properties": ["match_confidence", "evidence_sources", "channels"]
    },
    "EXTRACTED_FROM": {
        "valid_sources": ["Task"],
        "valid_targets": ["Message", "Event"],
        "properties": ["extraction_method", "confidence_score", "extracted_text"]
    },
    "ASSIGNED_TO": {
        "valid_sources": ["Task"],
        "valid_targets": ["Person"],
        "properties": ["assignment_date", "status", "assigned_by"]
    },
    "DEPENDS_ON": {
        "valid_sources": ["Task"],
        "valid_targets": ["Task"],
        "properties": ["dependency_type", "blocking"]
    },
    "MODIFIED_BY": {
        "valid_sources": ["Task"],
        "valid_targets": ["User"],
        "properties": ["modification_date", "modification_type", "previous_state"]
    },
    "HAS_SUBTASK": {
        "valid_sources": ["Task"],
        "valid_targets": ["Task"],
        "properties": ["creation_date", "completion_dependency"]
    },
    # Resume-specific relationships
    "HAS_SKILL": {
        "valid_sources": ["User"],
        "valid_targets": ["Skill"],
        "properties": ["proficiency", "years_experience", "last_used"]
    },
    "HAS_CERTIFICATION": {
        "valid_sources": ["User"],
        "valid_targets": ["Certification"],
        "properties": ["issue_date", "expiry_date", "verification_url"]
    },
    "SPEAKS": {
        "valid_sources": ["User"],
        "valid_targets": ["Language"],
        "properties": ["proficiency", "is_native"]
    },
    "WORKED_AT": {
        "valid_sources": ["User"],
        "valid_targets": ["Organization"],
        "properties": ["title", "start_date", "end_date", "location", "skills_used"]
    },
    "LEARNT_AT": {
        "valid_sources": ["User"],
        "valid_targets": ["Organization"],
        "properties": ["degree", "start_date", "end_date", "location", "description"]
    }
}

# Key relationship indexes
RELATIONSHIP_INDEXES = [
    {"rel_type": "USER_KNOWS", "property": "last_contact_date"},
    {"rel_type": "AUTHORED", "property": "timestamp"},
    {"rel_type": "RECEIVED", "property": "timestamp"},
    {"rel_type": "USER_PARTICIPATES_IN", "property": "status"},
    {"rel_type": "USER_MANAGES", "property": "assignment_date"},
    {"rel_type": "USER_MANAGES", "property": "reminder_set"},
    {"rel_type": "USER_MANAGES", "property": "priority_override"},
    {"rel_type": "EXTRACTED_FROM", "property": "confidence_score"},
    {"rel_type": "ASSIGNED_TO", "property": "status"},
    {"rel_type": "DEPENDS_ON", "property": "dependency_type"},
    {"rel_type": "DEPENDS_ON", "property": "blocking"},
    {"rel_type": "RELATED_TO", "property": "relevance_score"},
    {"rel_type": "MODIFIED_BY", "property": "modification_date"},
    {"rel_type": "HAS_SUBTASK", "property": "creation_date"},
    {"rel_type": "SAME_AS", "property": "match_confidence"}
]

def cypher_indexes_for_relationships(rel_indexes=RELATIONSHIP_INDEXES):
    """
    Generate Cypher statements for relationship property indexes.
    """
    cypher = []
    for idx in rel_indexes:
        rel_type = idx["rel_type"]
        prop = idx["property"]
        cypher.append(f"CREATE INDEX IF NOT EXISTS FOR ()-[r:{rel_type}]-() ON (r.{prop});")
    return cypher

def initialize_graph_schema(neo4j_wrapper):
    """
    Initialize the Neo4j schema: create all node constraints, indexes, and relationship indexes.
    Usage: from graph_schema import initialize_graph_schema; initialize_graph_schema(Neo4jWrapper())
    """
    node_cypher = cypher_constraints_for_node_types()
    rel_cypher = cypher_indexes_for_relationships()
    with neo4j_wrapper.driver.session() as session:
        for stmt in node_cypher + rel_cypher:
            try:
                session.run(stmt)
            except Exception as e:
                print(f"Schema init error for: {stmt}\n{e}")

# --- Context Classification and Relationship Inference Utilities ---

CONTEXT_TAGS = {
    # Academic context
    "academic": ["classmate", "professor", "advisor", "study_group", "course", "research", "thesis"],
    # Professional context
    "professional": ["colleague", "manager", "report", "client", "vendor", "partner", "interview"],
    # Social context
    "social": ["friend", "family", "community", "hobby", "group", "social_event"],
    # Health context
    "health": ["doctor", "appointment", "treatment", "wellness", "exercise"],
    # Content topics
    "topics": ["project", "meeting", "deadline", "proposal", "payment", "invoice", "assignment", "paper", "application", "travel", "booking"]
}

def classify_communication_context(message_content, sender, recipients, channel):
    """
    Analyze message to determine appropriate context tags.
    Placeholder: Replace nlp_service.extract_key_phrases with your NLP pipeline.
    """
    # Placeholder: simple keyword matching
    key_phrases = message_content.lower().split()
    matched_tags = []
    for phrase in key_phrases:
        for context, tags in CONTEXT_TAGS.items():
            for tag in tags:
                if tag in phrase:
                    matched_tags.append(tag)
    # Add channel-based context
    if "@university.edu" in sender or any("@university.edu" in r for r in recipients):
        matched_tags.append("academic")
    return list(set(matched_tags))

def infer_relationship_from_communication(user_id, person_id, message_history, context_tags, graph_db):
    """
    Infer the nature of a relationship based on communication patterns and content.
    Placeholder: Replace analyze_message_timing and analyze_sentiment_pattern with your logic.
    """
    from datetime import datetime
    frequency = len(message_history)
    last_contact = max(msg["timestamp"] for msg in message_history)
    first_contact = min(msg["timestamp"] for msg in message_history)
    # Placeholder: simple sentiment pattern
    sentiment_pattern = sum(msg.get("sentiment", 0) for msg in message_history) / max(1, frequency)
    # Placeholder: simple relationship strength
    strength = min(1.0, frequency / 100 + sentiment_pattern / 10)
    channels = list(set(msg.get("channel_id") for msg in message_history if msg.get("channel_id")))
    graph_db.create_relationship(
        from_label="User",
        to_label="Person",
        rel_type="USER_KNOWS",
        from_props={"id": user_id},
        to_props={"id": person_id},
        rel_props={
            "relationship_strength": strength,
            "first_contact_date": first_contact,
            "last_contact_date": last_contact,
            "communication_frequency": frequency,
            "channels": channels,
            "context_tags": context_tags
        }
    ) 