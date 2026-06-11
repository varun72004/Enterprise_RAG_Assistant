"""Document chunking service using LangChain text splitters."""

import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from backend.config import get_settings

logger = logging.getLogger(__name__)


def chunk_document(pages: list[dict], filename: str) -> list[Document]:
    """Split extracted PDF pages into overlapping chunks with metadata.
    
    Uses RecursiveCharacterTextSplitter for intelligent splitting at
    paragraph, sentence, and word boundaries.
    
    Args:
        pages: List of dicts with 'page' and 'text' keys from pdf_processor.
        filename: Original PDF filename for metadata.
        
    Returns:
        List of LangChain Document objects with metadata including
        page number, PDF name, and unique chunk ID.
    """
    settings = get_settings()
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    
    all_chunks: list[Document] = []
    
    for page_data in pages:
        page_num = page_data["page"]
        text = page_data["text"]
        
        # Split the page text into chunks
        chunks = splitter.split_text(text)
        
        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_id = f"{filename}_page{page_num}_chunk{chunk_idx}"
            
            doc = Document(
                page_content=chunk_text,
                metadata={
                    "page": page_num,
                    "pdf": filename,
                    "chunk_id": chunk_id,
                },
            )
            all_chunks.append(doc)
    
    logger.info(
        f"Created {len(all_chunks)} chunks from '{filename}' "
        f"({len(pages)} pages)"
    )
    
    return all_chunks
