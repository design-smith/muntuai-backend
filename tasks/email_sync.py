from backend.integrations.manual.gmail_client import GmailClient
from backend.data_services.mongo.conversation_repository import create_conversation, get_collection
from backend.data_services.mongo.chat_repository import add_message, get_chat_by_id, create_chat
from backend.data_services.mongo.user_repository import list_users
from backend.routers.chat import broadcast_message
from datetime import datetime, UTC
import asyncio
import logging
from google.oauth2.credentials import Credentials
import json
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def sync_emails_task():
    logger.info("Starting email synchronization task...")
    
    # Initialize integration_repo here
    from backend.data_services.mongo.integration_repository import IntegrationRepository
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    integration_repo = IntegrationRepository(client)

    while True:
        users = list_users()
        if not users:
            logger.info("No users found. Skipping email sync.")
            await asyncio.sleep(60)
            continue

        for user in users:
            user_id = str(user['_id'])
            user_email = user["email"]
            
            # Get Gmail integration for this user
            gmail_integration = await integration_repo.get_integration_by_type_and_provider(
                user_id, "email", "gmail"
            )

            if not gmail_integration:
                #logger.warning(f"No active Gmail integration found for user {user_id}. Skipping email sync.")
                continue

            creds_data = gmail_integration.get("credentials")
            if not creds_data:
                logger.error(f"No credentials found for Gmail integration for user {user_id}. Skipping email sync.")
                continue

            # Log initial type and content of creds_data
            logger.debug(f"Initial creds_data type for user {user_id}: {type(creds_data)}")
            logger.debug(f"Initial creds_data content for user {user_id}: {creds_data}")

            # Ensure credentials are a dictionary
            if isinstance(creds_data, str):
                logger.debug(f"Attempting to parse creds_data as JSON for user {user_id}...")
                try:
                    creds_data = json.loads(creds_data)
                    logger.debug(f"Successfully parsed creds_data as JSON for user {user_id}. New type: {type(creds_data)}")
                except json.JSONDecodeError as e:
                    logger.exception(f"Failed to decode credentials for user {user_id}: {e}. Skipping email sync.")
                    continue

            # Log creds_data type and content AFTER potential parsing
            logger.debug(f"Creds_data type BEFORE items() call for user {user_id}: {type(creds_data)}")
            logger.debug(f"Creds_data content BEFORE items() call for user {user_id}: {creds_data}")

            # Convert base64 encoded bytes back to bytes for Google's Credentials object
            restored_creds = {}
            for k, v in creds_data.items():
                if isinstance(v, str) and (k == 'token' or k == 'refresh_token' or k == 'id_token'): # Adjust keys as needed
                    try:
                        restored_creds[k] = base64.b64decode(v)
                    except Exception as e:
                        logger.warning(f"Failed to base64 decode credential part {k} for user {user_id}: {e}")
                        restored_creds[k] = v # Keep as string if decoding fails
                else:
                    restored_creds[k] = v

            try:
                # Initialize Gmail client
                gmail_client = GmailClient()
                await gmail_client.initialize(restored_creds) # Pass the dictionary directly
                
                # Fetch emails
                threads = await gmail_client.get_emails()
                emails = threads.get('emails', [])
                
                conversations_collection = get_collection("conversations")
                chats_collection = get_collection("chats")

                for email in emails:
                    thread_id = email.get('threadId')
                    if not thread_id:
                        logger.warning(f"Email {email.get('id')} has no threadId. Skipping.")
                        continue

                    conversation_doc = conversations_collection.find_one({"thread_id": thread_id, "user_id": user_id})
                    
                    if not conversation_doc:
                        logger.info(f"New conversation detected for threadId: {thread_id} for user {user_id}")
                        conversation_data = {
                            "user_id": user_id, 
                            "source": "Email",
                            "subject": email.get('subject', 'No Subject'),
                            "participants": [email.get('sender', 'Unknown')],
                            "thread_id": thread_id,
                            "created_at": datetime.fromisoformat(email['date'].replace('Z', '+00:00')[:-6]) if 'date' in email else datetime.now(UTC),
                            "updated_at": datetime.now(UTC),
                            "status": "active"
                        }
                        new_conversation = create_conversation(conversation_data)
                        conversation_doc = new_conversation
                        logger.info(f"Created new conversation with ID: {conversation_doc['_id']}")
                        await broadcast_message({"type": "new_conversation", "conversation": str(new_conversation['_id']), "user_id": user_id})

                    chat_doc = chats_collection.find_one({"conversation_id": conversation_doc['_id'], "user_id": user_id})
                    if not chat_doc:
                        logger.info(f"No chat document found for conversation {conversation_doc['_id']}. Creating one.")
                        chat_data = {
                            "user_id": user_id,
                            "assistant_id": "default_assistant_id", 
                            "conversation_id": conversation_doc['_id'], 
                            "messages": [],
                            "created_at": datetime.now(UTC),
                            "updated_at": datetime.now(UTC),
                        }
                        chat_doc = create_chat(chat_data)
                        logger.info(f"Created new chat with ID: {chat_doc['_id']}")
                        await broadcast_message({"type": "new_chat", "chat": str(chat_doc['_id']), "user_id": user_id})

                    message_data = {
                        "sender": email.get('sender', 'Unknown'),
                        "text": email.get('body', ''),
                        "timestamp": datetime.fromisoformat(email['date'].replace('Z', '+00:00')[:-6]) if 'date' in email else datetime.now(UTC),
                        "source": "Email",
                        "gmail_message_id": email.get('id')
                    }
                    
                    message_exists = any(m.get('gmail_message_id') == message_data['gmail_message_id'] for m in chat_doc.get('messages', []))

                    if not message_exists:
                        logger.info(f"Adding new message to chat {chat_doc['_id']} for email {email.get('id')}")
                        await add_message(str(chat_doc['_id']), message_data)
                        await broadcast_message({"type": "new_message", "chat_id": str(chat_doc['_id']), "message": message_data, "user_id": user_id})
                    else:
                        logger.info(f"Message {email.get('id')} already exists in chat {chat_doc['_id']}. Skipping.")

            except Exception as e:
                logger.error(f"Error during email synchronization for user {user_id}: {e}", exc_info=True)
        
        await asyncio.sleep(30) 