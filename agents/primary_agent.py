import os
from dotenv import load_dotenv
import autogen
from backend.agents.calendar_agent import get_calendar_agent
from backend.agents.intent_classifier import get_intent_classifier_agent, classify_intent
from backend.agents.prompt_builder import build_personalized_prompt
from backend.GraphRAG.graphrag.engine.context_builder import GraphRAGContextBuilder
from backend.GraphRAG.graphrag.engine.rag_engine import GraphRAGEngine
from composio_openai import ComposioToolSet, Action
from backend.data_services.mongo.assistant_repository import get_assistant_by_id
from backend.agents.utils import extract_citation_targets, response_has_citation, refine_response
from backend.data_services.mongo.user_repository import UserRepository
from bson import ObjectId, errors as bson_errors
from backend.data_services.mongo.assistant_data_service import get_user_context, format_context_for_prompt
import json
from backend.agents.search_agent import get_search_agent
from typing import Dict, Any, Optional
import logging

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize repositories
user_repository = UserRepository()

def get_primary_agent(assistant_id=None, user_id=None, context_builder=None):
    """Returns a configured primary agent that can delegate tasks, using assistant config from MongoDB."""
    # Get MongoDB user ID
    try:
        mongo_user_id = str(ObjectId(user_id))
    except (bson_errors.InvalidId, TypeError):
        user_doc = get_user_by_id(user_id)
        if user_doc and user_doc.get("_id"):
            mongo_user_id = str(user_doc["_id"])
        else:
            mongo_user_id = str(user_id)

    # Get assistant configuration if provided
    assistant_config = None
    if assistant_id:
        assistant_config = get_assistant_by_id(assistant_id)
        if not assistant_config:
            raise ValueError(f"Assistant {assistant_id} not found")
        if user_id and str(assistant_config.get('user_id')) != str(user_id):
            raise ValueError("Unauthorized: Assistant does not belong to user")
        if not assistant_config.get('isActive', True):
            raise ValueError("Assistant is inactive and cannot be used.")

    # Build personalized system prompt
    system_message = build_personalized_prompt(mongo_user_id, assistant_id)

    # Configure the DeepSeek API
    config_list = [
        {
            "model": "deepseek-chat",
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "base_url": "https://api.deepseek.com/v1"
        }
    ]

    # Initialize the calendar agent
    calendar_agent = get_calendar_agent()
    
    # Initialize GraphRAG engine and context builder if not provided
    if context_builder is None:
        graph_rag_engine = GraphRAGEngine()
        context_builder = GraphRAGContextBuilder(graph_rag_engine)

    # Initialize Composio ToolSet
    toolset = ComposioToolSet()

    # Fetch email-related tools
    email_tools = toolset.get_tools(actions=[
        Action.GMAIL_FETCH_EMAILS,
        Action.GMAIL_SEND_EMAIL
    ])

    # Create the primary agent
    primary_agent = autogen.UserProxyAgent(
        name=assistant_config.get('name', 'AI_Assistant').replace(' ', '_') if assistant_config else 'AI_Assistant',
        system_message=system_message,
        llm_config={
            "config_list": config_list,
            "temperature": 0.7,
        },
        human_input_mode="NEVER",
        code_execution_config={
            "use_docker": False,
            "last_n_messages": 3,
            "work_dir": "workspace"
        }
    )

    # Add calendar agent, context builder, and email tools to the primary agent's context
    primary_agent.calendar_agent = calendar_agent
    primary_agent.context_builder = context_builder
    primary_agent.email_tools = email_tools
    primary_agent.intent_classifier = get_intent_classifier_agent()
    primary_agent.user_id = mongo_user_id

    return primary_agent

def process_request(agent, request, user_id="user1", assistant_id=None):
    """Process a user request through the primary agent, using intent classification and smart delegation."""
    # Always use the MongoDB _id for retrieval
    try:
        mongo_user_id = str(ObjectId(user_id))
    except (bson_errors.InvalidId, TypeError):
        user_doc = get_user_by_id(user_id)
        if user_doc and user_doc.get("_id"):
            mongo_user_id = str(user_doc["_id"])
        else:
            mongo_user_id = str(user_id)
    print(f"[DEBUG] Using MongoDB user_id for retrieval: {mongo_user_id}")

    # Prepare context for intent classification
    context = {
        'history': agent.chat_history if hasattr(agent, 'chat_history') else [],
        'user_info': get_user_context(mongo_user_id)
    }

    # Classify intent
    intent = classify_intent(agent.intent_classifier, request, context)
    print(f"[DEBUG] Classified intent: {intent}")

    # Handle based on intent
    if intent == "calendar":
        # Delegate to calendar agent
        return agent.calendar_agent.generate_reply(
            messages=[{"role": "user", "content": request}],
            sender=agent
        )

    elif intent == "search":
        # Get context from GraphRAG
        graphrag_context = agent.context_builder.format_for_agent(
            query=request,
            user_id=mongo_user_id,
            agent_type="primary"
        )
        
        # Get user context
        user_context = get_user_context(mongo_user_id)
        formatted_user_context = format_context_for_prompt(user_context)
        
        # Combine all context for final response
        final_context = f"""Based on the search results and user context, please provide a comprehensive response.
Be friendly and natural in your response, but focus on being helpful and accurate.

USER CONTEXT:
{formatted_user_context}

SEARCH RESULTS:
{json.dumps(graphrag_context['raw'], indent=2)}

Original request: {request}"""

        return agent.generate_reply(
            messages=[{
                "role": "user",
                "content": request
            }, {
                "role": "system",
                "content": final_context
            }],
            sender=agent
        )

    else:  # basic intent (includes greetings, smalltalk, and general queries)
        # Use the basic AI assistant with resume context
        system_context = f"""You are an assistant. You have access to the user's resume and conversation history.
Your primary role is to:
1. Use the conversation history and resume context to provide personalized responses
2. Maintain a friendly and professional tone
3. Be proactive in offering relevant assistance based on the user's background

CONVERSATION HISTORY:
{agent.chat_history if hasattr(agent, 'chat_history') else 'No previous messages'}

Current request: {request}"""

        response = agent.generate_reply(
            messages=[{
                "role": "user",
                "content": request
            }, {
                "role": "system",
                "content": system_context
            }],
            sender=agent
        )
        
        # Update chat history
        if not hasattr(agent, 'chat_history'):
            agent.chat_history = []
        agent.chat_history.append({"role": "user", "content": request})
        agent.chat_history.append({"role": "assistant", "content": response})
        
        # Keep only last 10 messages in history
        agent.chat_history = agent.chat_history[-10:]
        
        return response

def handle_email_tasks(agent, task, user_id="user1"):
    """Handle email-related tasks like fetching, reading, and drafting responses."""
    if task == "fetch_emails":
        # Use the GMAIL_FETCH_EMAILS tool to fetch new emails
        response = agent.email_tools[0].execute()
        return response

    elif task == "draft_response":
        # Draft a response to an email
        email_content = "Provide the email content here."
        draft = agent.generate_reply(
            messages=[{
                "role": "user",
                "content": f"Draft a response to this email: {email_content}"
            }],
            sender=agent
        )
        return draft

    elif task == "send_email":
        # Use the GMAIL_SEND_EMAIL tool to send an email
        email_data = {
            "recipient": "recipient@example.com",
            "subject": "Subject of the email",
            "body": "Body of the email"
        }
        response = agent.email_tools[1].execute(params=email_data)
        return response

    return "Task not recognized."

async def get_primary_agent(user_id: str) -> Optional[Dict]:
    """Get the primary agent for a user."""
    try:
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.warning(f"No user found for ID: {user_id}")
            return None
        
        # Get primary agent from user document
        primary_agent = user.get("primary_agent")
        if not primary_agent:
            logger.warning(f"No primary agent found for user: {user_id}")
            return None
        
        return primary_agent
    except Exception as e:
        logger.error(f"Error getting primary agent: {str(e)}")
        return None

async def process_request(user_id: str, request_data: Dict) -> Dict:
    """Process a request using the user's primary agent."""
    try:
        # Get user and primary agent
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"No user found for ID: {user_id}")
        
        primary_agent = user.get("primary_agent")
        if not primary_agent:
            raise ValueError(f"No primary agent found for user: {user_id}")
        
        # Process request using primary agent
        # TODO: Implement actual request processing logic
        return {
            "status": "success",
            "message": "Request processed successfully",
            "data": request_data
        }
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise