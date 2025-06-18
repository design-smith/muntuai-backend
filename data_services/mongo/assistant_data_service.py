from typing import Dict, List, Any, Optional
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId as bson_errors
from backend.data_services.mongo.mongo_client import get_database
# from backend.data_services.redis_cache import RedisCache

class AssistantDataService:
    def __init__(self):
        self.db = get_database()
        # Temporarily comment out Redis Cache initialization
        # self.redis_cache = RedisCache()
        self.allowed_collections = {
            'businesses': 'business',
            'chats': 'chat',
            'contacts': 'contact',
            'conversations': 'conversation',
            'events': 'event',
            'messages': 'message',
            'tasks': 'task'
        }

    def get_user_data(self, user_id: str, collection: str, query: Optional[Dict] = None) -> List[Dict]:
        """
        Get user-specific data from a collection with caching.
        """
        if collection not in self.allowed_collections:
            raise ValueError(f"Collection {collection} is not allowed for assistant access")

        # Create cache key
        cache_key = f"assistant_data:{user_id}:{collection}:{str(query)}"
        
        # Try to get from cache first
        cached_data = self.redis_cache.get(cache_key)
        if cached_data:
            return cached_data

        # Build the query with user_id filter
        mongo_query = {"user_id": user_id}
        if query:
            mongo_query.update(query)

        # Get data from MongoDB
        collection_name = self.allowed_collections[collection]
        data = list(self.db[collection_name].find(mongo_query))

        # Cache the results
        self.redis_cache.set(cache_key, data, ttl=300)  # Cache for 5 minutes

        return data

    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive user context from all allowed collections.
        """
        context = {}
        
        # Convert user_id to ObjectId if it's not already
        try:
            mongo_user_id = ObjectId(user_id)
        except (bson_errors, TypeError):
            # If not a valid ObjectId, try to find user by other fields
            user_doc = self.db['user'].find_one({"$or": [
                {"_id": user_id},
                {"email": user_id},
                {"supabase_id": user_id}
            ]})
            if user_doc and "_id" in user_doc:
                mongo_user_id = user_doc["_id"]
            else:
                print(f"[DEBUG] Could not find user with ID: {user_id}")
                return context

        # Get user document
        user_doc = self.db['user'].find_one({"_id": mongo_user_id})
        if user_doc:
            # Extract all resume-related fields
            resume_fields = [k for k in user_doc.keys() if k.startswith('resume_')]
            if resume_fields:
                context['resume'] = {
                    field: user_doc[field] 
                    for field in resume_fields 
                    if user_doc[field] is not None
                }
                # Add raw text if available
                if 'resume_rawText' in user_doc:
                    context['resume']['raw_text'] = user_doc['resume_rawText']
        
        # Then get other collections
        for collection in self.allowed_collections:
            try:
                data = self.get_user_data(str(mongo_user_id), collection)
                context[collection] = data
            except Exception as e:
                print(f"Error fetching {collection} data: {str(e)}")
                context[collection] = []
        return context

    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format the context data into a prompt-friendly string with clear structure.
        """
        formatted_context = []
        
        # First format resume data if available
        if 'resume' in context:
            formatted_context.append("\nRESUME INFORMATION:")
            resume = context['resume']
            
            # If we have raw text, use that first
            if 'raw_text' in resume:
                formatted_context.append(resume['raw_text'])
            else:
                # Otherwise format the structured resume data
                for key, value in resume.items():
                    if key != 'raw_text':  # Skip raw_text as it's handled above
                        formatted_name = key.replace('resume_', '').replace('_', ' ').title()
                        formatted_context.append(f"\n{formatted_name}:")
                        if isinstance(value, list):
                            for item in value:
                                formatted_context.append(f"- {item}")
                        else:
                            formatted_context.append(str(value))
            
            formatted_context.append("")  # Add blank line
        
        # Then format other collections
        for collection, data in context.items():
            if collection == 'resume' or not data:
                continue
                
            formatted_context.append(f"\n{collection.upper()} INFORMATION:")
            
            # Format each item in the collection
            for item in data:
                # Remove sensitive fields
                item = {k: v for k, v in item.items() if k not in ['_id', 'user_id', 'password', 'api_key']}
                
                # Format based on collection type
                if collection == 'contacts':
                    formatted_context.append(f"Contact: {item.get('name', 'Unknown')}")
                    if 'email' in item:
                        formatted_context.append(f"  Email: {item['email']}")
                    if 'phone' in item:
                        formatted_context.append(f"  Phone: {item['phone']}")
                    if 'notes' in item:
                        formatted_context.append(f"  Notes: {item['notes']}")
                
                elif collection == 'tasks':
                    formatted_context.append(f"Task: {item.get('title', 'Untitled')}")
                    formatted_context.append(f"  Status: {item.get('status', 'Unknown')}")
                    if 'due_date' in item:
                        formatted_context.append(f"  Due: {item['due_date']}")
                    if 'description' in item:
                        formatted_context.append(f"  Description: {item['description']}")
                
                elif collection == 'events':
                    formatted_context.append(f"Event: {item.get('title', 'Untitled')}")
                    formatted_context.append(f"  Start: {item.get('start_time', 'Unknown')}")
                    formatted_context.append(f"  End: {item.get('end_time', 'Unknown')}")
                    if 'description' in item:
                        formatted_context.append(f"  Description: {item['description']}")
                
                elif collection == 'messages':
                    formatted_context.append(f"Message: {item.get('content', 'No content')}")
                    formatted_context.append(f"  From: {item.get('sender', 'Unknown')}")
                    formatted_context.append(f"  Time: {item.get('timestamp', 'Unknown')}")
                
                elif collection == 'conversations':
                    formatted_context.append(f"Conversation: {item.get('title', 'Untitled')}")
                    formatted_context.append(f"  Status: {item.get('status', 'Unknown')}")
                    if 'last_message' in item:
                        formatted_context.append(f"  Last Message: {item['last_message']}")
                
                elif collection == 'businesses':
                    formatted_context.append(f"Business: {item.get('name', 'Unknown')}")
                    if 'description' in item:
                        formatted_context.append(f"  Description: {item['description']}")
                    if 'industry' in item:
                        formatted_context.append(f"  Industry: {item['industry']}")
                
                else:
                    # Default formatting for other collections
                    formatted_context.append(f"- {str(item)}")
                
                formatted_context.append("")  # Add blank line between items
        
        return "\n".join(formatted_context)

# Create a singleton instance
assistant_data_service = AssistantDataService()

# Export functions for easier access
def get_user_context(user_id: str) -> Dict[str, Any]:
    return assistant_data_service.get_user_context(user_id)

def format_context_for_prompt(context: Dict[str, Any]) -> str:
    return assistant_data_service.format_context_for_prompt(context) 