import logging
from typing import List, Dict, Any
from fastembed import TextEmbedding
from backend.config import get_settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for batch embedding generation with fastembed caching."""
    
    _model = None

    @classmethod
    def get_model(cls):
        """Get or initialize the embedding model (singleton)."""
        if cls._model is None:
            settings = get_settings()
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            cls._model = TextEmbedding(settings.EMBEDDING_MODEL)
        return cls._model

    @classmethod
    def embed_texts(cls, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Batch generate embeddings for texts."""
        if not texts:
            return []
        model = cls.get_model()
        logger.info(f"Generating embeddings for {len(texts)} texts.")
        embeddings = list(model.embed(texts, batch_size=batch_size))
        return [e.tolist() for e in embeddings]

    @classmethod
    def embed_query(cls, query: str) -> List[float]:
        """Embed a single query."""
        model = cls.get_model()
        return list(model.embed([query]))[0].tolist()

    @classmethod
    def embed_and_store(cls, chunks: List[Dict[str, Any]]) -> int:
        """Embed chunk texts and store in vector database."""
        from backend.database.vector_store import VectorStore
        
        if not chunks:
            return 0
            
        texts = [chunk["text"] for chunk in chunks]
        embeddings = cls.embed_texts(texts)
        
        return VectorStore.add_documents(chunks, embeddings)
