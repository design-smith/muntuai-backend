from typing import Dict, Optional
from ...data_services.mongo.user_repository import UserRepository
import logging
from ...data_services.mongo.mongo_client import get_collection
from datetime import datetime, timedelta, UTC

logger = logging.getLogger(__name__)

# Initialize repositories
user_repository = UserRepository()

def process_email_payload(payload):
    """
    Process and route incoming email payloads.
    This function normalizes, filters, and routes the email data to the AI assistant and storage/indexing.

    Args:
        payload (dict): The email payload received from the webhook.

    Returns:
        None
    """
    try:
        # Normalize the payload (e.g., extract relevant fields)
        email_data = {
            "subject": payload.get("subject"),
            "sender": payload.get("from"),
            "recipient": payload.get("to"),
            "body": payload.get("body"),
            "timestamp": payload.get("timestamp"),
        }

        # Filter the payload (e.g., exclude spam/unsubscribe emails)
        if "unsubscribe" in email_data["body"].lower():
            logging.info("Email ignored due to unsubscribe content.")
            return

        # Route the email to the AI assistant for processing
        logging.info(f"Routing email to AI assistant: {email_data}")
        # Call AI assistant processing function (to be implemented)
        # process_with_ai_assistant(email_data)

        # Store the email in the database or indexing system
        logging.info("Storing email in the database.")
        # store_email_in_database(email_data)

    except Exception as e:
        logging.error(f"Failed to process email payload: {str(e)}")
        raise

def fetch_provider_data_with_range(user_id, provider):
    """
    Fetch messages/events/emails from a provider for a user, respecting the user's search_range preference.
    """
    user = get_user_by_id(user_id)
    if not user:
        logging.error(f"User {user_id} not found for provider sync.")
        return []
    prefs = user.get("integration_preferences", {}).get(provider, {})
    days = prefs.get("search_range", 5)  # default to 30 days
    start_date = datetime.now(UTC) - timedelta(days=days)
    logging.info(f"Fetching data for user {user_id}, provider {provider}, from {start_date.isoformat()} to now.")
    # TODO: Call Composio API for the provider, passing start_date as the lower bound
    # Example: composio_client.fetch_messages(user_id, provider, start_date)
    # For now, just log and return empty list
    return []

def sync_all_providers_for_user(user_id):
    """
    Sync all connected providers for a user, respecting their preferences.
    """
    user = get_user_by_id(user_id)
    if not user:
        logging.error(f"User {user_id} not found for provider sync.")
        return
    integrations = user.get("composio_integrations", [])
    if not integrations:
        logging.info(f"No integrations found for user {user_id}.")
        return
    for integration in integrations:
        provider = integration.get("provider")
        if not provider:
            continue
        logging.info(f"Syncing provider {provider} for user {user_id}...")
        results = fetch_provider_data_with_range(user_id, provider)
        logging.info(f"Fetched {len(results)} items from {provider} for user {user_id}.")

async def process_incoming_data(user_id: str, data: Dict) -> Optional[Dict]:
    """Process incoming data from Composio."""
    try:
        # Get user data
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            return None
        
        # Process data
        # TODO: Implement actual data processing logic
        return {
            "status": "success",
            "message": "Data processed successfully",
            "data": data
        }
    except Exception as e:
        logger.error(f"Error processing incoming data: {str(e)}")
        return None

async def handle_webhook(user_id: str, webhook_data: Dict) -> Optional[Dict]:
    """Handle incoming webhook from Composio."""
    try:
        # Get user data
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            return None
        
        # Process webhook data
        # TODO: Implement actual webhook handling logic
        return {
            "status": "success",
            "message": "Webhook handled successfully",
            "data": webhook_data
        }
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        return None

async def process_email_payload(user_id: str, email_data: Dict) -> Optional[Dict]:
    """Process incoming email payload from Composio."""
    try:
        # Get user data
        user = await user_repository.get_user_by_id(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            return None
        
        # Process email data
        # TODO: Implement actual email processing logic
        return {
            "status": "success",
            "message": "Email processed successfully",
            "data": email_data
        }
    except Exception as e:
        logger.error(f"Error processing email payload: {str(e)}")
        return None