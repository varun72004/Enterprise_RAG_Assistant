"""Upload and document management routes."""

import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Header

from backend.config import get_settings
from backend.models.schemas import (
    UploadResponse,
    DocumentInfo,
    DocumentListResponse,
    ErrorResponse,
)
from backend.services.pdf_processor import extract_text, get_pdf_page_count
from backend.services.chunking import chunk_document
from backend.services.embedding_service import embed_texts
from backend.database.vector_store import (
    add_documents,
    delete_document as delete_from_store,
    get_chunks_for_document,
    list_documents,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Allowed file extensions
_ALLOWED_EXTENSIONS = {".pdf"}


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename.
        
    Returns:
        Sanitized filename with only safe characters.
    """
    # Remove path components
    name = Path(filename).name
    # Replace potentially dangerous characters
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ")
    sanitized = "".join(c if c in safe_chars else "_" for c in name)
    # Collapse multiple underscores
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    return sanitized.strip("_")


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...), x_session_id: str | None = Header(None)):
    """Upload a PDF file, extract text, chunk, embed, and store.
    
    Validates file type and size, then processes through the full
    RAG pipeline: extract → chunk → embed → store.
    """
    settings = get_settings()
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    
    extension = Path(file.filename).suffix.lower()
    if extension not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{extension}'. Only PDF files are accepted.",
        )
    
    # Sanitize filename
    safe_filename = _sanitize_filename(file.filename)
    if not safe_filename.lower().endswith(".pdf"):
        safe_filename += ".pdf"
        
    if x_session_id:
        safe_filename = f"{x_session_id}_{safe_filename}"
    
    # Read file content
    content = await file.read()
    
    # Validate file size
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )
    
    # Validate it's actually a PDF (check magic bytes)
    if not content[:5] == b"%PDF-":
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid PDF.",
        )
    
    # Save file
    filepath = settings.upload_path / safe_filename
    try:
        with open(filepath, "wb") as f:
            f.write(content)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    
    try:
        # Extract text
        pages = extract_text(filepath)
        if not pages:
            raise HTTPException(
                status_code=422,
                detail="Could not extract any text from the PDF. The file may be image-only or corrupted.",
            )
        
        # Chunk
        chunks = chunk_document(pages, safe_filename)
        
        # Inject session_id into chunk metadata for vector store isolation
        if x_session_id:
            for chunk in chunks:
                chunk.metadata["session_id"] = x_session_id
                # Remove prefix for display
                chunk.metadata["pdf"] = safe_filename.replace(f"{x_session_id}_", "", 1)
        
        # Embed
        texts = [chunk.page_content for chunk in chunks]
        embeddings = embed_texts(texts)
        
        # Store
        add_documents(chunks, embeddings)
        
        logger.info(
            f"Successfully processed '{safe_filename}': "
            f"{len(pages)} pages, {len(chunks)} chunks"
        )
        
        display_name = safe_filename.replace(f"{x_session_id}_", "", 1) if x_session_id else safe_filename
        
        return UploadResponse(
            status="success",
            filename=display_name,
            pages_extracted=len(pages),
            chunks_created=len(chunks),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing '{safe_filename}': {e}")
        # Clean up the saved file on failure
        if filepath.exists():
            filepath.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {e}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_uploaded_documents(x_session_id: str | None = Header(None)):
    """List all uploaded and processed PDF documents."""
    settings = get_settings()
    documents: list[DocumentInfo] = []
    
    stored_pdfs = list_documents()
    
    for filename in stored_pdfs:
        if x_session_id and not filename.startswith(f"{x_session_id}_"):
            continue
            
        filepath = settings.upload_path / filename
        
        file_size_mb = 0.0
        uploaded_at = ""
        pages = 0
        
        if filepath.exists():
            stat = filepath.stat()
            file_size_mb = round(stat.st_size / (1024 * 1024), 2)
            uploaded_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
            pages = get_pdf_page_count(filepath)
        
        chunks = get_chunks_for_document(filename)
        
        display_name = filename.replace(f"{x_session_id}_", "", 1) if x_session_id else filename
        
        documents.append(DocumentInfo(
            filename=display_name,
            pages=pages,
            chunks=chunks,
            uploaded_at=uploaded_at,
            file_size_mb=file_size_mb,
        ))
    
    return DocumentListResponse(
        documents=documents,
        total_count=len(documents),
    )


@router.delete("/document/{filename}")
async def delete_document(filename: str, x_session_id: str | None = Header(None)):
    """Delete a PDF document and its associated vectors."""
    settings = get_settings()
    
    # Sanitize
    safe_filename = _sanitize_filename(filename)
    if x_session_id:
        safe_filename = f"{x_session_id}_{safe_filename}"
    
    # Delete from vector store
    deleted_chunks = delete_from_store(safe_filename)
    
    # Delete physical file
    filepath = settings.upload_path / safe_filename
    file_deleted = False
    if filepath.exists():
        filepath.unlink()
        file_deleted = True
    
    if deleted_chunks == 0 and not file_deleted:
        raise HTTPException(status_code=404, detail=f"Document '{safe_filename}' not found.")
    
    display_name = safe_filename.replace(f"{x_session_id}_", "", 1) if x_session_id else safe_filename
    
    return {
        "status": "success",
        "filename": display_name,
        "chunks_deleted": deleted_chunks,
    }
