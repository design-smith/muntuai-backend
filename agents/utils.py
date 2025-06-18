from datetime import datetime
import pytz
import re

def get_current_datetime(timezone="UTC"):
    """
    Get the current datetime information for a specific timezone.
    
    Args:
        timezone (str): The timezone to get the datetime for (default: "UTC")
        
    Returns:
        dict: A dictionary containing datetime information including:
            - current_time: Current time in ISO format
            - current_date: Current date in YYYY-MM-DD format
            - timezone: The timezone used
            - weekday: The current day of the week
    """
    # Get the timezone
    tz = pytz.timezone(timezone)
    
    # Get current datetime in the specified timezone
    current_dt = datetime.now(tz)
    
    return {
        "current_time": current_dt.isoformat(),
        "current_date": current_dt.strftime("%Y-%m-%d"),
        "timezone": timezone,
        "weekday": current_dt.strftime("%A")
    }

def format_datetime_for_prompt(datetime_info):
    """
    Format datetime information into a human-readable string for prompts.
    
    Args:
        datetime_info (dict): Dictionary containing datetime information
        
    Returns:
        str: Formatted datetime string
    """
    current_dt = datetime.fromisoformat(datetime_info["current_time"])
    
    return (
        f"Current time: {current_dt.strftime('%I:%M %p')} "
        f"({datetime_info['timezone']})\n"
        f"Current date: {datetime_info['current_date']} ({datetime_info['weekday']})"
    )

def extract_citation_targets(context):
    """
    Extract node titles and IDs from the context for citation enforcement.
    Args:
        context (dict): The context dict from context_builder.format_for_agent
    Returns:
        List[Tuple[str, str]]: List of (title, id) pairs
    """
    targets = []
    for r in context.get("raw", {}).get("results", []):
        doc = r.get("document", {})
        title = doc.get("title") or doc.get("name") or doc.get("text") or "(no title)"
        node_id = doc.get("id")
        if node_id:
            targets.append((title, node_id))
    return targets

def response_has_citation(response, citation_targets):
    """
    Check if the response contains at least one citation from the citation_targets.
    Args:
        response (str): The agent's response
        citation_targets (List[Tuple[str, str]]): List of (title, id) pairs
    Returns:
        bool: True if at least one citation is present
    """
    for title, node_id in citation_targets:
        if node_id and node_id in response:
            return True
        if title and title in response:
            return True
    return False

def refine_response(response):
    """
    Refine the response to be concise, human-like, and free of emojis/AI mannerisms.
    - Remove emojis
    - Remove phrases like 'As an AI', 'I'm an AI', etc.
    - Remove excessive politeness or filler
    - Make the response more direct
    Args:
        response (str): The agent's response
    Returns:
        str: Refined response
    """
    # Remove emojis
    response = re.sub(r'[\U00010000-\U0010ffff\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+', '', response)
    # Remove AI disclaimers
    response = re.sub(r"(As an AI|I'm an AI|As an artificial intelligence|I am an AI language model)[^\n\.]*[\n\.]?", '', response, flags=re.IGNORECASE)
    # Remove excessive politeness
    response = re.sub(r"(please|thank you|you're welcome|let me know if you need anything else)[\.,!\s]*", '', response, flags=re.IGNORECASE)
    # Remove filler phrases
    response = re.sub(r"(Here is|Here are|The following|Below is|Below are)[\s:]*", '', response, flags=re.IGNORECASE)
    # Remove multiple spaces
    response = re.sub(r' +', ' ', response)
    # Strip leading/trailing whitespace
    response = response.strip()
    return response 