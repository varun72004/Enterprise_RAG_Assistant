"""ChromaDB vector store wrapper for persistent document storage."""

from __future__ import annotations

import logging
from typing import Any

import chromadb
from langchain_core.documents import Document

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Module-level singleton
_client: chromadb.PersistentClient | None = None
_collection: chromadb.Collection | None = None
_COLLECTION_NAME = "pdf_documents"


def _get_client() -> chromadb.PersistentClient:
    """Get or create the ChromaDB persistent client."""
    global _client
    if _client is None:
        settings = get_settings()
        logger.info(f"Initializing ChromaDB at: {settings.chroma_path}")
        _client = chromadb.PersistentClient(path=str(settings.chroma_path))
    return _client


def get_collection() -> chromadb.Collection:
    """Get or create the document collection."""
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB collection '{_COLLECTION_NAME}' ready. Count: {_collection.count()}")
    return _collection


def add_documents(
    chunks: list[Document],
    embeddings: list[list[float]],
) -> int:
    """Add document chunks with embeddings to the vector store.
    
    Uses chunk_id from metadata for deduplication (upsert behavior).
    
    Args:
        chunks: List of LangChain Document objects.
        embeddings: Corresponding embedding vectors.
        
    Returns:
        Number of chunks added.
    """
    collection = get_collection()
    
    ids = [chunk.metadata["chunk_id"] for chunk in chunks]
    documents = [chunk.page_content for chunk in chunks]
    metadatas = [
        {"page": chunk.metadata["page"], "pdf": chunk.metadata["pdf"]}
        for chunk in chunks
    ]
    
    # Upsert in batches to avoid memory issues with large documents
    batch_size = 500
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.upsert(
            ids=ids[i:end],
            documents=documents[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end],
        )
    
    logger.info(f"Upserted {len(ids)} chunks into ChromaDB. Total: {collection.count()}")
    return len(ids)


def query(
    embedding: list[float],
    top_k: int = 5,
    filter_dict: dict[str, Any] | None = None,
) -> list[dict]:
    """Query the vector store for similar chunks.
    
    Args:
        embedding: Query embedding vector.
        top_k: Number of results to return.
        filter_dict: Optional metadata filter (e.g., {"pdf": "file.pdf"}).
        
    Returns:
        List of result dicts with 'text', 'page', 'pdf', 'score' keys.
    """
    collection = get_collection()
    
    if collection.count() == 0:
        logger.warning("Vector store is empty. No documents to search.")
        return []
    
    query_params: dict[str, Any] = {
        "query_embeddings": [embedding],
        "n_results": min(top_k, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    
    if filter_dict:
        query_params["where"] = filter_dict
    
    results = collection.query(**query_params)
    
    formatted: list[dict] = []
    if results and results["documents"] and results["documents"][0]:
        for idx in range(len(results["documents"][0])):
            formatted.append({
                "text": results["documents"][0][idx],
                "page": results["metadatas"][0][idx]["page"],
                "pdf": results["metadatas"][0][idx]["pdf"],
                "score": 1 - results["distances"][0][idx],  # Convert distance to similarity
            })
    
    return formatted


def delete_document(filename: str) -> int:
    """Delete all chunks belonging to a specific PDF.
    
    Args:
        filename: The PDF filename to remove.
        
    Returns:
        Number of chunks deleted.
    """
    collection = get_collection()
    
    # Get all IDs for this document
    existing = collection.get(
        where={"pdf": filename},
        include=[],
    )
    
    if existing["ids"]:
        collection.delete(ids=existing["ids"])
        logger.info(f"Deleted {len(existing['ids'])} chunks for '{filename}'")
        return len(existing["ids"])
    
    return 0


def get_document_count() -> int:
    """Get total number of chunks in the vector store."""
    return get_collection().count()


def list_documents() -> list[str]:
    """Get list of unique PDF filenames in the store."""
    collection = get_collection()
    
    if collection.count() == 0:
        return []
    
    # Get all metadatas
    results = collection.get(include=["metadatas"])
    
    filenames = set()
    if results["metadatas"]:
        for meta in results["metadatas"]:
            if "pdf" in meta:
                filenames.add(meta["pdf"])
    
    return sorted(filenames)


def get_chunks_for_document(filename: str) -> int:
    """Get the number of chunks for a specific document."""
    collection = get_collection()
    existing = collection.get(
        where={"pdf": filename},
        include=[],
    )
    return len(existing["ids"])


def is_healthy() -> bool:
    """Check if ChromaDB is accessible."""
    try:
        _get_client().heartbeat()
        return True
    except Exception:
        return False
