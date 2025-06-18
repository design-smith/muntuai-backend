from backend.GraphRAG.graphrag.db.graph_db import Neo4jWrapper
from datetime import datetime

def sync_user_to_graph(user_doc):
    """Sync user data to graph database."""
    if not user_doc:
        return

    # Initialize graph database connection
    graph_db = Neo4jWrapper()

    try:
        # Extract basic user properties
        properties = {
            "id": str(user_doc["_id"]),
            "email": user_doc.get("email", ""),
            "first_name": user_doc.get("first_name", ""),
            "last_name": user_doc.get("last_name", ""),
            "phone": user_doc.get("phone", ""),
        }

        # Handle resume data if it exists
        resume = user_doc.get("resume", {})
        if resume:
            # Add summary
            if resume.get("summary"):
                properties["resume_summary"] = resume["summary"]
            
            # Add skills as a list
            if resume.get("skills"):
                properties["resume_skills"] = resume["skills"]
            
            # Add languages as a list
            if resume.get("languages"):
                properties["resume_languages"] = resume["languages"]
            
            # Add links as a list
            if resume.get("links"):
                properties["resume_links"] = resume["links"]

        # Add composio integrations if they exist
        if "composio_integrations" in user_doc:
            properties["composio_integrations"] = user_doc["composio_integrations"]

        # Create or update user node
        try:
            graph_db.create_node("User", properties)
        except Exception as e:
            print(f"Error creating user node: {e}")
            # If node creation fails, try to update existing node
            try:
                graph_db.update_node("User", properties["id"], properties)
            except Exception as update_error:
                print(f"Error updating user node: {update_error}")

        # Create relationships for work experience
        if resume and "work_experience" in resume:
            for exp in resume["work_experience"]:
                exp_properties = {
                    "id": f"{properties['id']}_exp_{exp.get('company', '').lower().replace(' ', '_')}",
                    "company": exp.get("company", ""),
                    "title": exp.get("title", ""),
                    "start_date": exp.get("start_date", ""),
                    "end_date": exp.get("end_date", ""),
                    "description": exp.get("description", "")
                }
                try:
                    graph_db.create_node("WorkExperience", exp_properties)
                    graph_db.create_relationship(
                        "User", properties["id"],
                        "WorkExperience", exp_properties["id"],
                        "HAS_EXPERIENCE"
                    )
                except Exception as e:
                    print(f"Error creating work experience node: {e}")

        # Create relationships for education
        if resume and "education" in resume:
            for edu in resume["education"]:
                edu_properties = {
                    "id": f"{properties['id']}_edu_{edu.get('institution', '').lower().replace(' ', '_')}",
                    "institution": edu.get("institution", ""),
                    "degree": edu.get("degree", ""),
                    "field": edu.get("field", ""),
                    "start_date": edu.get("start_date", ""),
                    "end_date": edu.get("end_date", "")
                }
                try:
                    graph_db.create_node("Education", edu_properties)
                    graph_db.create_relationship(
                        "User", properties["id"],
                        "Education", edu_properties["id"],
                        "HAS_EDUCATION"
                    )
                except Exception as e:
                    print(f"Error creating education node: {e}")

    except Exception as e:
        print(f"Error in sync_user_to_graph: {e}")
        raise
    finally:
        graph_db.close()

def delete_user_from_graph(user_id):
    """
    Delete a User node in Neo4j by user_id (MongoDB _id as string).
    """
    graph_db = Neo4jWrapper()
    graph_db.delete_node("User", {"id": str(user_id)})
    graph_db.close()

# --- BUSINESS ---
def sync_business_to_graph(business_doc):
    graph_db = Neo4jWrapper()
    node_id = str(business_doc["_id"])
    user_id = str(business_doc["user_id"])
    properties = {
        "id": node_id,
        "name": business_doc.get("name"),
        "created_at": business_doc.get("created_at").isoformat() if business_doc.get("created_at") else None,
    }
    existing = graph_db.get_node("Organization", {"id": node_id})
    if existing:
        graph_db.update_node("Organization", {"id": node_id}, properties)
    else:
        graph_db.create_node("Organization", properties)
        # Relationship: USER_CONNECTED_TO
        graph_db.create_relationship("User", "Organization", "USER_CONNECTED_TO", {"id": user_id}, {"id": node_id})
    graph_db.close()

def delete_business_from_graph(business_id):
    graph_db = Neo4jWrapper()
    graph_db.delete_node("Organization", {"id": str(business_id)})
    graph_db.close()

# --- CONTACT ---
def sync_contact_to_graph(contact_doc):
    graph_db = Neo4jWrapper()
    node_id = str(contact_doc["_id"])
    user_id = str(contact_doc["user_id"])
    properties = {
        "id": node_id,
        "name": contact_doc.get("name"),
        "email": contact_doc.get("email"),
        "created_at": contact_doc.get("created_at").isoformat() if contact_doc.get("created_at") else None,
    }
    existing = graph_db.get_node("Person", {"id": node_id})
    if existing:
        graph_db.update_node("Person", {"id": node_id}, properties)
    else:
        graph_db.create_node("Person", properties)
        # Relationship: USER_KNOWS
        graph_db.create_relationship("User", "Person", "USER_KNOWS", {"id": user_id}, {"id": node_id})
    graph_db.close()

def delete_contact_from_graph(contact_id):
    graph_db = Neo4jWrapper()
    graph_db.delete_node("Person", {"id": str(contact_id)})
    graph_db.close()

# --- CONVERSATION ---
def sync_conversation_to_graph(conversation_doc):
    graph_db = Neo4jWrapper()
    node_id = str(conversation_doc["_id"])
    properties = {
        "id": node_id,
        "status": conversation_doc.get("status"),
        "created_at": conversation_doc.get("created_at").isoformat() if conversation_doc.get("created_at") else None,
    }
    existing = graph_db.get_node("Thread", {"id": node_id})
    if existing:
        graph_db.update_node("Thread", {"id": node_id}, properties)
    else:
        graph_db.create_node("Thread", properties)
    graph_db.close()

def delete_conversation_from_graph(conversation_id):
    graph_db = Neo4jWrapper()
    graph_db.delete_node("Thread", {"id": str(conversation_id)})
    graph_db.close()

# --- MESSAGE ---
def sync_message_to_graph(message_doc):
    graph_db = Neo4jWrapper()
    node_id = str(message_doc["_id"])
    conversation_id = str(message_doc.get("conversation_id"))
    sender_id = str(message_doc.get("sender_id", ""))
    # Store content as a string (text) property only
    content = message_doc.get("content")
    if isinstance(content, dict):
        content_str = content.get("text", "")
    else:
        content_str = str(content) if content else ""
    properties = {
        "id": node_id,
        "content": content_str,
        "timestamp": message_doc.get("timestamp").isoformat() if message_doc.get("timestamp") else None,
        "sender_id": sender_id,
        "channel_id": str(message_doc.get("channel_id", "")),
    }
    existing = graph_db.get_node("Message", {"id": node_id})
    if existing:
        graph_db.update_node("Message", {"id": node_id}, properties)
    else:
        graph_db.create_node("Message", properties)
        # Relationship: AUTHORED (User or Person to Message)
        if sender_id:
            graph_db.create_relationship("User", "Message", "AUTHORED", {"id": sender_id}, {"id": node_id})
    graph_db.close()

def delete_message_from_graph(message_id):
    graph_db = Neo4jWrapper()
    graph_db.delete_node("Message", {"id": str(message_id)})
    graph_db.close()

# --- EVENT ---
def sync_event_to_graph(event_doc):
    graph_db = Neo4jWrapper()
    node_id = str(event_doc["_id"])
    user_id = str(event_doc["user_id"])
    properties = {
        "id": node_id,
        "title": event_doc.get("title"),
        "start_time": event_doc.get("start_time").isoformat() if event_doc.get("start_time") else None,
        "created_at": event_doc.get("created_at").isoformat() if event_doc.get("created_at") else None,
    }
    existing = graph_db.get_node("Event", {"id": node_id})
    if existing:
        graph_db.update_node("Event", {"id": node_id}, properties)
    else:
        graph_db.create_node("Event", properties)
        # Relationship: USER_PARTICIPATES_IN
        graph_db.create_relationship("User", "Event", "USER_PARTICIPATES_IN", {"id": user_id}, {"id": node_id})
    graph_db.close()

def delete_event_from_graph(event_id):
    graph_db = Neo4jWrapper()
    graph_db.delete_node("Event", {"id": str(event_id)})
    graph_db.close()

# --- CHANNEL ---
def sync_channel_to_graph(channel_doc):
    graph_db = Neo4jWrapper()
    node_id = str(channel_doc["_id"])
    user_id = str(channel_doc.get("user_id", ""))
    properties = {
        "id": node_id,
        "name": channel_doc.get("name"),
        "type": channel_doc.get("type"),
        "created_at": channel_doc.get("created_at").isoformat() if channel_doc.get("created_at") else None,
    }
    existing = graph_db.get_node("Channel", {"id": node_id})
    if existing:
        graph_db.update_node("Channel", {"id": node_id}, properties)
    else:
        graph_db.create_node("Channel", properties)
        if user_id:
            graph_db.create_relationship("User", "Channel", "USER_COMMUNICATES_VIA", {"id": user_id}, {"id": node_id})
    graph_db.close()

def delete_channel_from_graph(channel_id):
    graph_db = Neo4jWrapper()
    graph_db.delete_node("Channel", {"id": str(channel_id)})
    graph_db.close()

# --- TASK ---
def sync_task_to_graph(task_doc):
    graph_db = Neo4jWrapper()
    node_id = str(task_doc["_id"])
    user_id = str(task_doc.get("user_id", ""))
    properties = {
        "id": node_id,
        "title": task_doc.get("title"),
        "created_date": task_doc.get("created_at").isoformat() if task_doc.get("created_at") else None,
    }
    existing = graph_db.get_node("Task", {"id": node_id})
    if existing:
        graph_db.update_node("Task", {"id": node_id}, properties)
    else:
        graph_db.create_node("Task", properties)
        if user_id:
            graph_db.create_relationship("User", "Task", "USER_MANAGES", {"id": user_id}, {"id": node_id})
    graph_db.close()

def delete_task_from_graph(task_id):
    graph_db = Neo4jWrapper()
    graph_db.delete_node("Task", {"id": str(task_id)})
    graph_db.close()

# --- CHAT ---
def sync_chat_to_graph(chat_doc):
    graph_db = Neo4jWrapper()
    node_id = str(chat_doc["_id"])
    properties = {
        "id": node_id,
        "created_at": chat_doc.get("created_at").isoformat() if chat_doc.get("created_at") else None,
    }
    existing = graph_db.get_node("Thread", {"id": node_id})
    if existing:
        graph_db.update_node("Thread", {"id": node_id}, properties)
    else:
        graph_db.create_node("Thread", properties)
    graph_db.close()

def delete_chat_from_graph(chat_id):
    graph_db = Neo4jWrapper()
    graph_db.delete_node("Thread", {"id": str(chat_id)})
    graph_db.close() 