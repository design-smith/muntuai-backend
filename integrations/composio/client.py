import logging
import time
from composio_openai import ComposioToolSet
import os
import urllib.parse # Already present, ensuring it's used

class ComposioIntegrationClient:
    """
    Composio integration logic for initiating OAuth connections and managing connection status.
    """
    def __init__(self):
        self.toolset = ComposioToolSet()  # Uses COMPOSIO_API_KEY from env

    def initiate_connection(self, user_id: str, provider: str, integration_id: str = None) -> str:
        """
        Initiates an OAuth connection for the given user and provider.

        Args:
            user_id (str): The ID of the user initiating the connection.
            provider (str): The name of the provider (e.g., 'gmail').
            integration_id (str, optional): The integration ID for the provider. Defaults to None.

        Returns:
            str: The redirect URL for the OAuth flow.

        Raises:
            Exception: If the redirect URL is not available.
        """
        try:
            toolset = ComposioToolSet()
            # Map provider to integration_id
            if provider == "gmail":
                integration_id = os.getenv("COMPOSIO_GMAIL_INTEGRATION_ID")
            elif provider == "outlook":
                integration_id = os.getenv("COMPOSIO_OUTLOOK_INTEGRATION_ID")
            elif provider == "slack":
                integration_id = os.getenv("COMPOSIO_SLACK_INTEGRATION_ID")
            elif provider == "google_calendar":
                integration_id = os.getenv("COMPOSIO_GOOGLE_CALENDAR_INTEGRATION_ID")
            elif provider == "fireflies":
                integration_id = os.getenv("COMPOSIO_FIREFLIES_INTEGRATION_ID")
            elif provider == "calendly":
                integration_id = os.getenv("COMPOSIO_CALENDLY_INTEGRATION_ID")
            elif provider == "discord":
                integration_id = os.getenv("COMPOSIO_DISCORD_INTEGRATION_ID")
            # Add more providers as needed
            if not integration_id:
                raise Exception(f"No integration_id configured for provider {provider}")
            connection_info = toolset.initiate_connection(
                integration_id=integration_id,
                entity_id=user_id
            )
        
            redirect_url = getattr(connection_info, 'redirectUrl', None)
            if not redirect_url:
                raise Exception(f"Failed to get redirect URL from Composio for provider {provider} and user {user_id}.")
            logging.info(f"Redirect URL for user {user_id} and provider {provider}: {redirect_url}")
            return redirect_url
        except Exception as e:
            logging.error(f"Error initiating connection for user {user_id} and provider {provider}: {str(e)}")
            raise

    def poll_connection_status(self, user_id: str, provider: str, timeout: int = 60) -> str:
        """
        Polls the connection status until it becomes active or the timeout is reached.

        Args:
            user_id (str): The ID of the user.
            provider (str): The name of the provider.
            timeout (int): The maximum time to wait in seconds. Defaults to 60.

        Returns:
            str: The connection ID if the connection becomes active.

        Raises:
            TimeoutError: If the connection does not become active within the timeout period.
        """
        
        try:
            entity = self.toolset.get_entity(id=user_id)
            for poll_num in range(timeout):
                connections = entity.get_connections()
                logging.info(f"[poll_connection_status] Poll {poll_num+1}/{timeout}: Found {len(connections)} connections for user {user_id}")
                for connection in connections:
                    logging.info(f"[poll_connection_status] Connection: app_name={connection.app_name}, status={connection.status}, id={connection.id}")
                    if connection.app_name == provider and connection.status == "ACTIVE":
                        logging.info(f"Connection active for user {user_id} and provider {provider}: {connection.id}")
                        return connection.id
                time.sleep(1)
            raise TimeoutError(f"Connection for user {user_id} and provider {provider} did not become active within {timeout} seconds.")
        except Exception as e:
            logging.error(f"Error polling connection status for user {user_id} and provider {provider}: {str(e)}")
            raise