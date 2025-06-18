import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.GraphRAG.graphrag.embeddings.embedding import EmbeddingService
import asyncio

async def main():
    # Initialize the service
    embedding_service = EmbeddingService()
    
    # Generate embeddings for single text
    text = "Meeting scheduled with John regarding the quarterly review"
    embedding = await embedding_service.embed(text)
    print(f"Embedding dimension: {len(embedding)}")
    
    # Generate embeddings for a batch of texts
    texts = [
        "Schedule a meeting with Sarah for tomorrow at 2 PM",
        "Please review the quarterly financial report",
        "Meeting scheduled with John regarding the quarterly review"
    ]
    embeddings = await embedding_service.embed(texts)
    print(f"Batch embedding count: {len(embeddings)}")
    
    # Find similar texts
    query = "Can we meet to discuss the financial results?"
    similar_texts = await embedding_service.find_similar_texts(query, texts)
    print(f"Most similar text: {similar_texts[0]['text']}")
    print(f"Similarity score: {similar_texts[0]['similarity']:.4f}")

# Run the example
if __name__ == "__main__":
    asyncio.run(main()) 