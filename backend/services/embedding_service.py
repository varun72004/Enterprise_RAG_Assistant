"""Embedding service using Sentence Transformers."""

from __future__ import annotations

import os
# Limit PyTorch memory usage for 512MB Free Tier constraints
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import logging
try:
    import torch
    torch.set_num_threads(1)
except ImportError:
    pass

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Module-level singleton
_model: SentenceTransformer | None = None
_MODEL_NAME = "all-MiniLM-L6-v2"


def get_model() -> SentenceTransformer:
    """Get or initialize the sentence transformer model (singleton).
    
    Returns:
        Loaded SentenceTransformer model.
    """
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {_MODEL_NAME}")
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info(f"Embedding model loaded. Dimension: {_model.get_embedding_dimension()}")
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
    
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Generate an embedding for a single query string.
    
    Args:
        query: The query text to embed.
        
    Returns:
        Embedding vector as a list of floats.
    """
    model = get_model()
    embedding = model.encode(query, normalize_embeddings=True)
    return embedding.tolist()
