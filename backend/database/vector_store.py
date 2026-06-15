import logging
from typing import List, Dict, Any
import chromadb
from backend.config import get_settings

logger = logging.getLogger(__name__)

class VectorStore:
    """ChromaDB vector store wrapper for persistent document storage."""
    
    _client = None
    _collection = None
    _COLLECTION_NAME = "rag_documents"

    @classmethod
    def get_client(cls) -> chromadb.PersistentClient:
        if cls._client is None:
            settings = get_settings()
            logger.info(f"Initializing ChromaDB at: {settings.chroma_path}")
            cls._client = chromadb.PersistentClient(path=str(settings.chroma_path))
        return cls._client

    @classmethod
    def get_collection(cls) -> chromadb.Collection:
        if cls._collection is None:
            client = cls.get_client()
            cls._collection = client.get_or_create_collection(
                name=cls._COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return cls._collection

    @classmethod
    def add_documents(cls, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> int:
        """Add chunks to ChromaDB. Uses upsert for deduplication."""
        collection = cls.get_collection()
        
        ids = [chunk["metadata"]["chunk_id"] for chunk in chunks]
        documents = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            collection.upsert(
                ids=ids[i:end],
                documents=documents[i:end],
                embeddings=embeddings[i:end],
                metadatas=metadatas[i:end],
            )
            
        logger.info(f"Upserted {len(ids)} chunks. Total collection size: {collection.count()}")
        return len(ids)

    @classmethod
    def query(cls, embedding: List[float], top_k: int = 10, filter_dict: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        collection = cls.get_collection()
        if collection.count() == 0:
            return []
            
        query_params = {
            "query_embeddings": [embedding],
            "n_results": min(top_k, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if filter_dict:
            query_params["where"] = filter_dict
            
        results = collection.query(**query_params)
        
        formatted = []
        if results and results["documents"] and results["documents"][0]:
            for idx in range(len(results["documents"][0])):
                # Ensure distance isn't negative (cosine)
                score = max(0.0, 1.0 - results["distances"][0][idx])
                formatted.append({
                    "text": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx],
                    "score": score
                })
        return formatted

    @classmethod
    def delete_document(cls, filename: str) -> int:
        collection = cls.get_collection()
        existing = collection.get(where={"source_file": filename}, include=[])
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
            return len(existing["ids"])
        return 0

    @classmethod
    def list_documents(cls) -> List[str]:
        collection = cls.get_collection()
        if collection.count() == 0:
            return []
        results = collection.get(include=["metadatas"])
        filenames = set()
        if results["metadatas"]:
            for meta in results["metadatas"]:
                if "source_file" in meta:
                    filenames.add(meta["source_file"])
        return sorted(list(filenames))

    @classmethod
    def is_healthy(cls) -> bool:
        try:
            cls.get_client().heartbeat()
            return True
        except Exception:
            return False
