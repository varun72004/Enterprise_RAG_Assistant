"""Embedding service using FastEmbed (ONNX optimized, low memory)."""

from __future__ import annotations

import logging
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

# Module-level singleton
_model: TextEmbedding | None = None
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def get_model() -> TextEmbedding:
    """Get or initialize the fastembed model (singleton).
    
    Returns:
        Loaded TextEmbedding model.
    """
    global _model
    if _model is None:
        logger.info(f"Loading embedding model via fastembed: {_MODEL_NAME}")
        # FastEmbed uses ONNX runtime, saving hundreds of MBs of RAM compared to PyTorch
        _model = TextEmbedding(_MODEL_NAME)
        logger.info("Embedding model loaded.")
    return _model


def get_model_name() -> str:
    """Return the name of the embedding model."""
    return _MODEL_NAME


def embed_texts(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Generate embeddings for a batch of texts.
    
    Args:
        texts: List of text strings to embed.
        batch_size: Number of texts to process at once.
        
    Returns:
        List of embedding vectors (each a list of floats).
    """
    model = get_model()
    
    logger.info(f"Generating embeddings for {len(texts)} texts (batch_size={batch_size})")
    
    # fastembed.embed returns an iterable of numpy arrays
    embeddings = list(model.embed(texts, batch_size=batch_size))
    
    return [e.tolist() for e in embeddings]


def embed_query(query: str) -> list[float]:
    """Generate an embedding for a single query string.
    
    Args:
        query: The query text to embed.
        
    Returns:
        Embedding vector as a list of floats.
    """
    model = get_model()
    # fastembed expects a list of strings
    embeddings = list(model.embed([query]))
    return embeddings[0].tolist()
