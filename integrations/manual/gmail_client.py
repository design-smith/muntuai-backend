from typing import Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from .base_client import BaseIntegrationClient
import os
import pickle
import json
from dotenv import load_dotenv
import base64
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GmailClient(BaseIntegrationClient):
    """
    Gmail integration client for manual connection.
    Handles authentication and data fetching from Gmail API using environment variables.
    """
    
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/calendar.events',
        'https://www.googleapis.com/auth/calendar.readonly',
    ]
    
    def __init__(self, user_credentials: Dict[str, Any] = None):
        load_dotenv()
        self.service = None
        self.creds = None

        # Client secrets from environment variables
        self.client_config = {
            'installed': {
                'client_id': os.getenv('GOOGLE_CLIENT_ID'),
                'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'auth_provider_x509_cert_url': 'https://www.googleapis.com/oauth2/v1/certs',
                'redirect_uris': ['http://localhost:8000/manual-integrations/callback']
            }
        }
        
        # Create a temporary file for client secrets for the flow object
        self.temp_credentials_path = 'temp_client_secrets.json'
        with open(self.temp_credentials_path, 'w') as f:
            json.dump(self.client_config, f)
            
        super().__init__({'credentials_path': self.temp_credentials_path})

        if user_credentials:
            # If user_credentials are provided, build the Credentials object directly
            try:
                self.creds = Credentials.from_authorized_user_info(user_credentials, self.SCOPES)
                self.service = build('gmail', 'v1', credentials=self.creds)
            except Exception as e:
                self.log_error(e, "Failed to initialize Gmail service with provided credentials")
        self.service = None
    
    async def disconnect(self):
        """Disconnects the Gmail client and cleans up resources."""
        logger.info("Disconnecting Gmail client...")
        self.service = None
        self.creds = None
        if os.path.exists(self.temp_credentials_path):
            try:
                os.remove(self.temp_credentials_path)
                logger.info(f"Removed temporary client secrets file: {self.temp_credentials_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary client secrets file {self.temp_credentials_path}: {e}")

    def get_required_credentials(self) -> list:
        return ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET']
    
    def get_auth_url(self, state=None):
        flow = Flow.from_client_secrets_file(
            self.temp_credentials_path,
            scopes=self.SCOPES,
            redirect_uri='http://localhost:8000/manual-integrations/callback'
        )
        auth_url, flow_state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state
        )
        # Optionally, store flow_state for CSRF protection
        self._flow_state = flow_state
        return auth_url, flow_state

    def exchange_code(self, code):
        flow = Flow.from_client_secrets_file(
            self.temp_credentials_path,
            scopes=self.SCOPES,
            redirect_uri='http://localhost:8000/manual-integrations/callback'
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Ensure refresh_token is present (Google may not return it if user previously consented)
        # This part might need to be adjusted if credentials are always stored in DB
        # For now, keeping it to handle cases where initial refresh_token might be missing from Google's side
        if not creds.refresh_token:
            # If no refresh token from current exchange, try to find a stored one if applicable
            # This logic should ideally be handled by the database retrieval layer.
            import warnings
            warnings.warn('No refresh_token received from Google. User may need to remove app access and re-consent.')
        
        self.creds = creds # Store credentials on the instance
        self.service = build('gmail', 'v1', credentials=self.creds)
        return creds # Return credentials for storage
    
    async def connect(self):
        # This method is no longer used for the web server flow. Connection is established on init or exchange_code.
        return self.service is not None
    
    async def is_connected(self) -> bool:
        if self.service is None:
            return False
        try:
            # Attempt a lightweight API call to check connection
            self.service.users().getProfile(userId='me').execute()
            return True
        except Exception as e:
            self.log_error(e, "Gmail service connection check failed")
            self.service = None # Invalidate service if check fails
            return False
    
    async def fetch_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        if not self.service:
            raise Exception("Not connected to Gmail")
        
        try:
            # Build query for date range if provided
            query = ""
            if start_date:
                query += f"after:{start_date} "
            if end_date:
                query += f"before:{end_date}"
            
            # Fetch messages
            results = self.service.users().messages().list(
                userId='me',
                q=query.strip() if query else None
            ).execute()
            
            messages = results.get('messages', [])
            email_data = []
            
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()
                
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                # Get message body
                body = ''
                if 'parts' in msg['payload']:
                    for part in msg['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            data = part['body'].get('data', '')
                            if data:
                                body = base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
                            break
                elif 'body' in msg['payload']:
                    data = msg['payload']['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
                
                email_data.append({
                    'id': message['id'],
                    'threadId': message['threadId'],
                    'subject': subject,
                    'sender': sender,
                    'date': date,
                    'body': body
                })
            
            return {
                'emails': email_data,
                'total': len(email_data)
            }
            
        except Exception as e:
            self.log_error(e, "Failed to fetch Gmail data")
            raise 

    def get_authenticated_email(self):
        if not self.service:
            raise Exception("Gmail service not initialized")
        profile = self.service.users().getProfile(userId='me').execute()
        return profile.get('emailAddress') 

    async def initialize(self, credentials_json: str):
        """Initialize the Gmail client with credentials from the database."""
        try:
            credentials = Credentials.from_authorized_user_info(
                json.loads(credentials_json), self.SCOPES
            )
            
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            
            self.service = build('gmail', 'v1', credentials=credentials)
            return True
        except Exception as e:
            logger.error(f"Error initializing Gmail client: {str(e)}")
            raise

    async def get_user_info(self, credentials: Credentials):
        """Get user info from Gmail."""
        try:
            service = build('gmail', 'v1', credentials=credentials)
            profile = service.users().getProfile(userId='me').execute()
            return profile
        except Exception as e:
            logger.error(f"Error getting user info: {str(e)}")
            raise

    async def get_emails(self, max_results: int = 10):
        """Get recent emails from Gmail."""
        try:
            if not self.service:
                raise Exception("Gmail client not initialized")

            # Get recent messages
            results = self.service.users().messages().list(
                userId='me',
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            threads = []

            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me',
                    id=message['id'],
                    format='full'
                ).execute()

                # Get thread ID
                thread_id = msg['threadId']

                # Get headers
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

                # Get message body
                body = ''
                if 'parts' in msg['payload']:
                    for part in msg['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            body = part['body'].get('data', '')
                            break
                elif 'body' in msg['payload']:
                    body = msg['payload']['body'].get('data', '')

                # Add to threads
                thread = {
                    'threadId': thread_id,
                    'latest': {
                        'sender': sender,
                        'subject': subject,
                        'snippet': body[:120] if body else '',
                        'date': date
                    },
                    'messages': [{
                        'sender': sender,
                        'body': body,
                        'subject': subject,
                        'date': date,
                        'id': message['id']
                    }]
                }
                threads.append(thread)

            return threads
        except Exception as e:
            logger.error(f"Error getting emails: {str(e)}")
            raise 