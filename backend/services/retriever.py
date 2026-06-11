"""Retrieval service for finding relevant document chunks."""

from __future__ import annotations

import logging
from collections import defaultdict

from backend.config import get_settings
from backend.services.embedding_service import embed_query
from backend.database.vector_store import query as vector_query

logger = logging.getLogger(__name__)


def _keyword_score(query: str, text: str) -> float:
    """Simple keyword overlap score for hybrid search.
    
    Computes the fraction of query words found in the text.
    
    Args:
        query: The user's question.
        text: The chunk text.
        
    Returns:
        Score between 0.0 and 1.0.
    """
    query_words = set(query.lower().split())
    text_lower = text.lower()
    
    if not query_words:
        return 0.0
    
    matches = sum(1 for word in query_words if word in text_lower)
    return matches / len(query_words)


def retrieve(
    query: str,
    top_k: int | None = None,
    use_hybrid: bool = True,
) -> list[dict]:
    """Retrieve the most relevant document chunks for a query.
    
    Uses vector similarity search as the primary method. Optionally
    applies keyword matching and reciprocal rank fusion for hybrid search.
    
    Args:
        query: The user's question.
        top_k: Number of results to return (defaults to settings).
        use_hybrid: Whether to apply keyword reranking.
        
    Returns:
        List of result dicts sorted by relevance, each containing:
        'text', 'page', 'pdf', 'score'.
    """
    settings = get_settings()
    k = top_k or settings.TOP_K_RESULTS
    
    # Step 1: Vector similarity search
    query_embedding = embed_query(query)
    results = vector_query(query_embedding, top_k=k * 2)  # Fetch more for reranking
    
    if not results:
        logger.info("No results found for query.")
        return []
    
    if not use_hybrid:
        return results[:k]
    
    # Step 2: Hybrid reranking with keyword scores
    for result in results:
        vector_score = result["score"]
        kw_score = _keyword_score(query, result["text"])
        # Weighted combination: 70% vector, 30% keyword
        result["score"] = 0.7 * vector_score + 0.3 * kw_score
    
    # Sort by combined score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # Deduplicate by content (keep highest scoring)
    seen_texts: set[str] = set()
    unique_results: list[dict] = []
    for r in results:
        text_key = r["text"][:100]  # Use first 100 chars as dedup key
        if text_key not in seen_texts:
            seen_texts.add(text_key)
            unique_results.append(r)
    
    final = unique_results[:k]
    logger.info(f"Retrieved {len(final)} chunks for query: '{query[:50]}...'")
    
    return final
