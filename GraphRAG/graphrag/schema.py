from .neo4j_wrapper import Neo4jWrapper

def initialize_schema():
    """Initialize the graph database schema."""
    graph_db = Neo4jWrapper()
    
    try:
        # Create User node type
        graph_db.create_node_type("User", {
            "id": "string",
            "email": "string",
            "first_name": "string",
            "last_name": "string",
            "phone": "string",
            "resume_summary": "string",
            "resume_skills": "list",
            "resume_languages": "list",
            "resume_links": "list",
            "composio_integrations": "list"
        })
        
        # Create WorkExperience node type
        graph_db.create_node_type("WorkExperience", {
            "id": "string",
            "company": "string",
            "title": "string",
            "start_date": "string",
            "end_date": "string",
            "description": "string"
        })
        
        # Create Education node type
        graph_db.create_node_type("Education", {
            "id": "string",
            "institution": "string",
            "degree": "string",
            "field": "string",
            "start_date": "string",
            "end_date": "string"
        })
        
        # Create relationship types
        graph_db.create_relationship_type("HAS_EXPERIENCE")
        graph_db.create_relationship_type("HAS_EDUCATION")
        
        # Create indexes
        graph_db.create_index("User", "id")
        graph_db.create_index("WorkExperience", "id")
        graph_db.create_index("Education", "id")
        
    except Exception as e:
        print(f"Error initializing schema: {str(e)}")
        raise
    finally:
        graph_db.close() 