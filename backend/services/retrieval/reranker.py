import logging
from typing import List, Dict, Any
from sentence_transformers import CrossEncoder
from backend.config import get_settings

logger = logging.getLogger(__name__)

class RerankerService:
    """Service to rerank retrieved documents using a cross-encoder."""
    
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            settings = get_settings()
            logger.info(f"Loading reranker model: {settings.RERANKER_MODEL}")
            cls._model = CrossEncoder(settings.RERANKER_MODEL)
        return cls._model

    @classmethod
    def rerank(cls, query: str, chunks: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Rerank a list of chunks against a query.
        
        Args:
            query: The user query.
            chunks: List of chunk dictionaries (must contain 'text').
            top_k: Number of top chunks to return.
            
        Returns:
            Reranked and sorted list of chunks.
        """
        if not chunks:
            return []
            
        model = cls.get_model()
        pairs = [[query, chunk["text"]] for chunk in chunks]
        
        # Predict similarity scores
        scores = model.predict(pairs)
        
        # Combine scores with chunks
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)
            
        # Sort by rerank score descending
        sorted_chunks = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        
        return sorted_chunks[:top_k]
