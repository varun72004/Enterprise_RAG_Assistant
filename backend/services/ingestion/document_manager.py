import logging
from pathlib import Path
from typing import List, Dict, Any
from backend.services.ingestion.pdf_loader import PDFLoader
from backend.services.ingestion.html_loader import HTMLLoader
from backend.services.ingestion.csv_loader import CSVLoader

logger = logging.getLogger(__name__)

class DocumentManager:
    """
    Manages document ingestion by delegating to specific loaders based on file type.
    This acts as the entry point for the indexing pipeline.
    """

    @staticmethod
    def load_document(file_path: str) -> List[Dict[str, Any]]:
        """
        Determine the file type and load the document.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        
        if ext == ".pdf":
            return PDFLoader.load(file_path)
        elif ext in [".html", ".htm"]:
            return HTMLLoader.load(file_path)
        elif ext == ".csv":
            return CSVLoader.load(file_path)
        else:
            raise ValueError(f"Unsupported document format: {ext}")

    @staticmethod
    def process_file_task(file_path: str):
        """
        Main function to be called by Celery task for processing a single file.
        This handles loading, chunking, and indexing.
        """
        logger.info(f"Starting processing for {file_path}")
        filename = Path(file_path).name
        from backend.services.ingestion.document_registry import DocumentRegistry
        file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
        ext = Path(file_path).suffix.lower().replace(".", "").upper()
        
        # Mark as Processing
        DocumentRegistry.add_or_update(filename, "Processing", ext, file_size)
        
        try:
            # 1. Load document
            docs = DocumentManager.load_document(file_path)
            page_count = len(docs)
            
            # 2. Chunking (lazy import to avoid circular dependencies if needed)
            from backend.services.chunking_service import ChunkingService
            chunks = ChunkingService.chunk_documents(docs)
            chunk_count = len(chunks)
            
            # 3. Embedding and Indexing
            from backend.services.embedding_service import EmbeddingService
            EmbeddingService.embed_and_store(chunks)
            
            # Mark as Indexed
            DocumentRegistry.add_or_update(filename, "Indexed", ext, file_size, page_count, chunk_count)
            
            logger.info(f"Successfully processed and indexed {file_path}")
            return {"status": "success", "file": file_path, "chunks": len(chunks)}
            
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {str(e)}")
            DocumentRegistry.add_or_update(filename, "Failed", error=str(e))
            return {"status": "error", "file": file_path, "error": str(e)}
