import os
import autogen
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_intent_classifier_agent():
    """Returns an intent classification agent that categorizes user input."""
    config_list = [
        {
            "model": "deepseek-chat",
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "base_url": "https://api.deepseek.com/v1"
        }
    ]
    
    return autogen.UserProxyAgent(
        name="IntentClassifier",
        system_message="""You are an intent classification agent.
Your job is to classify user input into one of the following intents:

- greeting: Simple greetings, hellos, how are you, etc.
- calendar: Scheduling, appointments, reminders, time-related queries
- email: Email composition, reading, sending, managing
- search: Information seeking, knowledge queries, fact-finding
- smalltalk: Casual conversation, personal questions, chit-chat
- task: Specific tasks or actions the user wants to perform
- general: General questions or requests that don't fit other categories
- unknown: Unclear or ambiguous requests

Consider the following when classifying:
1. Context matters - same words can have different intents
2. Be precise but not overly specific
3. Default to 'general' if unsure
4. Consider user's history and context

Respond with ONLY the intent label. DO NOT explain or add anything else.""",
        llm_config={
            "config_list": config_list,
            "temperature": 0.2
        },
        human_input_mode="NEVER",
        code_execution_config={
            "use_docker": False,
            "last_n_messages": 2,
            "work_dir": "workspace"
        }
    )

def classify_intent(agent, message: str, context: dict = None) -> str:
    """
    Classify the intent of a user message.
    
    Args:
        agent: The intent classifier agent
        message: The user's message
        context: Optional context including conversation history and user info
    
    Returns:
        str: The classified intent
    """
    # Prepare context-aware prompt
    context_str = ""
    if context:
        if context.get('history'):
            context_str += f"\nRecent conversation:\n{context['history']}\n"
        if context.get('user_info'):
            context_str += f"\nUser context:\n{context['user_info']}\n"
    
    # Get classification
    response = agent.generate_reply(
        messages=[{
            "role": "user", 
            "content": f"{context_str}Classify this message: {message}"
        }],
        sender=agent
    )
    
    # Clean and validate response
    intent = response.strip().lower()
    valid_intents = ['greeting', 'calendar', 'email', 'search', 'smalltalk', 'task', 'general', 'unknown']
    
    # If response isn't a valid intent, default to general
    if intent not in valid_intents:
        return 'general'
    
    return intent 