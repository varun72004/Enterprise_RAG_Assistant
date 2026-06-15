import uuid
import logging
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.config import get_settings

logger = logging.getLogger(__name__)

class ChunkingService:
    """
    Service for chunking text using RecursiveCharacterTextSplitter.
    This improves retrieval quality by ensuring that chunks are semantically coherent 
    and overlap enough to prevent loss of context across chunk boundaries.
    """

    @staticmethod
    def chunk_documents(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Split a list of document pages/rows into smaller chunks with metadata.
        
        Args:
            docs: List of dictionaries with 'text' and 'metadata'.
            
        Returns:
            List of chunk dictionaries with updated metadata including a unique chunk_id.
        """
        settings = get_settings()
        
        # We use RecursiveCharacterTextSplitter because it tries to split on paragraphs, 
        # then sentences, then words, preserving semantic structure much better than naive chunking.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        chunks = []
        for doc in docs:
            text = doc["text"]
            base_metadata = doc["metadata"]
            
            if not text:
                continue
                
            splits = text_splitter.split_text(text)
            
            for split in splits:
                # Deep copy to avoid modifying the original metadata across iterations
                chunk_meta = base_metadata.copy()
                chunk_meta["chunk_id"] = str(uuid.uuid4())
                
                chunks.append({
                    "text": split,
                    "metadata": chunk_meta
                })
                
        logger.info(f"Chunked {len(docs)} documents into {len(chunks)} chunks.")
        return chunks
