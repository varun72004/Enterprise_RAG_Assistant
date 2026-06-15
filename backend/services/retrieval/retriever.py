import logging
from typing import List, Dict, Any
from backend.config import get_settings
from backend.services.embedding_service import EmbeddingService
from backend.database.vector_store import VectorStore
from backend.services.retrieval.reranker import RerankerService

logger = logging.getLogger(__name__)

class ContextCompressor:
    """A lightweight context compressor that extracts relevant sentences."""
    
    @staticmethod
    def compress(query: str, text: str) -> str:
        """
        Extract sentences from the text that contain query terms.
        If no exact overlap, returns the original text to preserve context.
        """
        query_terms = set(query.lower().split())
        sentences = [s.strip() for s in text.split(". ") if s.strip()]
        
        relevant_sentences = []
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(term in sentence_lower for term in query_terms if len(term) > 3):
                relevant_sentences.append(sentence)
                
        if relevant_sentences:
            return ". ".join(relevant_sentences) + "."
        return text

class RetrieverService:
    """Advanced retrieval pipeline: Vector Search -> Reranking -> Compression."""

    @classmethod
    def retrieve(cls, query: str) -> List[Dict[str, Any]]:
        settings = get_settings()
        
        # 1. Embed Query
        logger.info(f"Retrieving context for query: {query}")
        query_embedding = EmbeddingService.embed_query(query)
        
        # 2. Vector Search (Top 10)
        initial_results = VectorStore.query(
            embedding=query_embedding,
            top_k=settings.TOP_K_RESULTS
        )
        
        if not initial_results:
            logger.warning("No context found in VectorStore.")
            return []
            
        # 3. Rerank (Top 3)
        reranked_results = RerankerService.rerank(
            query=query, 
            chunks=initial_results, 
            top_k=settings.TOP_K_RERANK
        )
        
        # 4. Context Compression
        for result in reranked_results:
            result["original_text"] = result["text"]
            result["text"] = ContextCompressor.compress(query, result["text"])
            
        logger.info(f"Retrieved and compressed {len(reranked_results)} chunks.")
        return reranked_results
