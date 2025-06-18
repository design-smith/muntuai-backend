from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import logging
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

class IntegrationRepository:
    def __init__(self, client: AsyncIOMotorClient):
        self.db = client['muntuai-cluster']
        self.collection = self.db.integrations

    async def create_integration(self, integration_data: dict):
        """
        Create a new integration.
        
        Args:
            integration_data: Dictionary containing:
                - user_id: MongoDB ObjectId of the user
                - type: Type of integration (email, slack, calendar, etc.)
                - provider: Provider name (gmail, outlook, etc.)
                - name: Identifier (email address, slack ID, etc.)
                - credentials: Integration credentials/tokens
                - status: Integration status (ACTIVE, INACTIVE, etc.)
                - created_at: Timestamp
                - updated_at: Timestamp
        """
        try:
            # Ensure user_id is ObjectId
            if isinstance(integration_data.get('user_id'), str):
                integration_data['user_id'] = ObjectId(integration_data['user_id'])
            
            # Add timestamps
            integration_data['created_at'] = datetime.now(UTC)
            integration_data['updated_at'] = datetime.now(UTC)
            
            result = await self.collection.insert_one(integration_data)
            inserted_doc = await self.collection.find_one({"_id": result.inserted_id})
            if inserted_doc:
                inserted_doc["_id"] = str(inserted_doc["_id"])
                if "user_id" in inserted_doc:
                    inserted_doc["user_id"] = str(inserted_doc["user_id"])
            return inserted_doc
        except Exception as e:
            logger.error(f"Error creating integration: {str(e)}")
            raise

    async def get_integration_by_id(self, integration_id: str):
        """Get an integration by its ID."""
        try:
            integration = await self.collection.find_one({"_id": ObjectId(integration_id)})
            if integration:
                integration["_id"] = str(integration["_id"])
                if "user_id" in integration:
                    integration["user_id"] = str(integration["user_id"])
            return integration
        except Exception as e:
            logger.error(f"Error getting integration: {str(e)}")
            raise

    async def get_user_integrations(self, user_id: str):
        """Get all integrations for a user."""
        try:
            cursor = self.collection.find({"user_id": ObjectId(user_id)})
            integrations = await cursor.to_list(length=None)
            for integration in integrations:
                integration["_id"] = str(integration["_id"])
                integration["user_id"] = str(integration["user_id"])
            return integrations
        except Exception as e:
            logger.error(f"Error getting user integrations: {str(e)}")
            raise

    async def update_integration(self, integration_id: str, update_data: dict):
        """Update an integration."""
        try:
            update_data['updated_at'] = datetime.now(UTC)
            result = await self.collection.update_one(
                {"_id": ObjectId(integration_id)},
                {"$set": update_data}
            )
            if result.modified_count == 0:
                return None
            return await self.get_integration_by_id(integration_id)
        except Exception as e:
            logger.error(f"Error updating integration: {str(e)}")
            raise

    async def delete_integration(self, integration_id: str):
        """Delete an integration."""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(integration_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting integration: {str(e)}")
            raise

    async def get_integration_by_type_and_provider(self, user_id: str, integration_type: str, provider: str):
        """Get a specific integration by type and provider for a user."""
        try:
            integration = await self.collection.find_one({
                "user_id": ObjectId(user_id),
                "type": integration_type,
                "provider": provider
            })
            if integration:
                integration["_id"] = str(integration["_id"])
                integration["user_id"] = str(integration["user_id"])
            return integration
        except Exception as e:
            logger.error(f"Error getting integration by type and provider: {str(e)}")
            raise 