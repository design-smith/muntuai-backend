import logging
from typing import List, Dict, Any, Union, Optional
import asyncio
import hashlib

from sentence_transformers import SentenceTransformer
from ..config import get_settings

class EmbeddingService:
    """Service to generate vector embeddings from text (async, batch, normalized, versioned)"""
    
    def __init__(
        self, 
        model_name: str = "all-MiniLM-L6-v2",
        cache_size: int = 1000,
        embedding_dim: int = 384
    ):
        """
        Initialize the embedding service.
        
        Args:
            model_name: Name of the SentenceTransformers model to use
            cache_size: Maximum number of embeddings to cache
            embedding_dim: Dimension of the embedding vectors
        """
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self.cache_size = cache_size
        
        # Lazy-loaded model (initialized on first use)
        self._model = None
        
        # Simple in-memory cache
        self._cache = {}
        
        logging.info(f"Initialized embedding service with model: {model_name}")
    
    @property
    def model(self):
        """Lazy-load the model only when first needed"""
        if self._model is None:
            logging.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    @property
    def model_version(self) -> str:
        """Return the model name and version info (if available)"""
        try:
            version = getattr(self.model, 'version', None)
            if version:
                return f"{self.model_name}:{version}"
        except Exception:
            pass
        return self.model_name

    def embedding_metadata(self) -> Dict[str, Any]:
        """Return metadata about the embedding model/config for tracking/versioning."""
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "embedding_dim": self.embedding_dim
        }
    
    def _generate_cache_key(self, text: str) -> str:
        """Generate a deterministic cache key for a text"""
        # Use hash for efficient storage
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    async def embed(
        self, 
        text: Union[str, List[str]]
    ) -> Union[List[float], List[List[float]]]:
        """
        Generate normalized embeddings for text(s) (async, batch, cached).
        
        Args:
            text: Single text or list of texts to embed
            
        Returns:
            Vector embedding(s) as list of floats
        """
        # Determine if input is single text or batch
        is_single = isinstance(text, str)
        texts = [text] if is_single else text
        
        # Check cache for each text
        results = []
        texts_to_embed = []
        text_indices = []
        
        for i, t in enumerate(texts):
            cache_key = self._generate_cache_key(t)
            if cache_key in self._cache:
                # Use cached embedding
                results.append(self._cache[cache_key])
            else:
                # Mark for embedding
                texts_to_embed.append(t)
                text_indices.append(i)
        
        # Generate embeddings for texts not in cache
        if texts_to_embed:
            # Use asyncio to avoid blocking
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                self._embed_batch,
                texts_to_embed
            )
            
            # Update cache with new embeddings
            for text, embedding in zip(texts_to_embed, embeddings):
                cache_key = self._generate_cache_key(text)
                self._cache[cache_key] = embedding
                
                # Simple cache size management (LRU not implemented here)
                if len(self._cache) > self.cache_size:
                    # Remove a random item (in production, use LRU)
                    self._cache.pop(next(iter(self._cache)))
            
            # Insert new embeddings into results at correct positions
            for i, embedding in zip(text_indices, embeddings):
                # Extend results list if needed
                while len(results) <= i:
                    results.append(None)
                results[i] = embedding
        
        # Return single embedding or list based on input type
        return results[0] if is_single else results
    
    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized embeddings for a batch of texts (synchronous)"""
        # Preprocess texts
        processed_texts = [self._preprocess_text(t) for t in texts]
        
        # Generate embeddings
        embeddings = self.model.encode(
            processed_texts,
            convert_to_tensor=False,  # Return as list
            normalize_embeddings=True  # Always normalize for cosine similarity
        )
        
        # Convert to Python lists
        return embeddings.tolist()
    
    def _preprocess_text(self, text: str) -> str:
        """Preprocess text before embedding"""
        # Simple preprocessing
        processed = text.strip()
        
        # Truncate very long texts (model has token limits)
        if len(processed) > 10000:
            processed = processed[:10000]
            
        return processed
    
    def calculate_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between two normalized embeddings"""
        # Since embeddings are normalized, dot product = cosine similarity
        return sum(a * b for a, b in zip(embedding1, embedding2))
    
    async def find_similar_texts(
        self,
        query_text: str,
        candidate_texts: List[str],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find the most similar texts to a query.
        
        Args:
            query_text: The text to compare against
            candidate_texts: List of texts to compare with
            top_k: Number of top results to return
            
        Returns:
            List of dicts with text and similarity score
        """
        # Get embeddings
        query_embedding = await self.embed(query_text)
        candidate_embeddings = await self.embed(candidate_texts)
        
        # Calculate similarities
        similarities = [
            self.calculate_similarity(query_embedding, emb)
            for emb in candidate_embeddings
        ]
        
        # Sort by similarity (descending)
        results = sorted(
            [
                {"text": text, "similarity": similarity}
                for text, similarity in zip(candidate_texts, similarities)
            ],
            key=lambda x: x["similarity"],
            reverse=True
        )
        
        # Return top k
        return results[:top_k]

    # Deprecated: use async embed instead
    def generate_embedding(self, text: str) -> list:
        import warnings
        warnings.warn("Use await embed(text) instead. This is a sync, non-cached, non-versioned fallback.", DeprecationWarning)
        return self.model.encode([text], normalize_embeddings=True)[0].tolist()
    
    def generate_embeddings(self, texts: list[str]) -> list:
        import warnings
        warnings.warn("Use await embed(texts) instead. This is a sync, non-cached, non-versioned fallback.", DeprecationWarning)
        return self.model.encode(texts, normalize_embeddings=True).tolist() 