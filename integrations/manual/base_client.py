from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional

class BaseIntegrationClient(ABC):
    """
    Base class for all manual integration clients.
    Provides common functionality and interface for all integrations.
    """
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize the integration client with credentials.
        
        Args:
            credentials (Dict[str, Any]): Dictionary containing necessary credentials
        """
        self.credentials = credentials
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection with the service.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from the service.
        
        Returns:
            bool: True if disconnection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if the client is connected to the service.
        
        Returns:
            bool: True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    async def fetch_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch data from the service.
        
        Args:
            start_date (Optional[str]): Start date for data fetch
            end_date (Optional[str]): End date for data fetch
            
        Returns:
            Dict[str, Any]: Fetched data
        """
        pass
    
    def validate_credentials(self) -> bool:
        """
        Validate the provided credentials.
        
        Returns:
            bool: True if credentials are valid, False otherwise
        """
        required_fields = self.get_required_credentials()
        return all(field in self.credentials for field in required_fields)
    
    @abstractmethod
    def get_required_credentials(self) -> list:
        """
        Get list of required credential fields.
        
        Returns:
            list: List of required credential field names
        """
        pass
    
    def log_error(self, error: Exception, context: str = ""):
        """
        Log an error with context.
        
        Args:
            error (Exception): The error to log
            context (str): Additional context about the error
        """
        self.logger.error(f"{context}: {str(error)}") 