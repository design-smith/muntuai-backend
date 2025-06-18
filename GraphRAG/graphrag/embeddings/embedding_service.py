from .embedding import EmbeddingService

# Create a singleton instance
_embedding_service = EmbeddingService()

def get_embedding(text: str) -> list:
    """
    Get embedding for a single text using the singleton EmbeddingService instance.
    
    Args:
        text: The text to generate embedding for
        
    Returns:
        List of floats representing the embedding vector
    """
    # Use the synchronous method since we're in a non-async context
    return _embedding_service._embed_batch([text])[0] 