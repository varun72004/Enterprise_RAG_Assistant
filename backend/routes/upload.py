"""Upload and document management routes."""

import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from backend.config import get_settings
from backend.services.ingestion.document_manager import DocumentManager

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".html", ".htm", ".csv"}


def _try_celery_dispatch(file_path: str) -> str | None:
    """Attempt to dispatch to Celery. Returns task_id or None if unavailable."""
    # Fast check if Redis port is open
    import socket
    try:
        with socket.create_connection(("localhost", 6379), timeout=0.3):
            pass
    except Exception:
        logger.info("Redis is offline. Bypassing Celery and falling back to sync processing.")
        return None

    try:
        from backend.celery_app import celery
        task = celery.send_task("process_document_task", args=[file_path], retry=False)
        return task.id
    except Exception as e:
        logger.warning(f"Celery unavailable, falling back to sync processing: {e}")
        return None


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """Upload a file (PDF, HTML, CSV) and process it.
    
    Tries Celery first for background ingestion. Falls back to
    synchronous processing if Redis/Celery is unavailable.
    """
    settings = get_settings()

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    safe_filename = Path(file.filename).name.replace(" ", "_")
    filepath = settings.upload_path / safe_filename

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    with open(filepath, "wb") as f:
        f.write(content)

    from backend.services.ingestion.document_registry import DocumentRegistry
    DocumentRegistry.add_or_update(safe_filename, "Processing", ext.replace(".", "").upper(), len(content))

    # Try Celery first, fall back to sync
    task_id = _try_celery_dispatch(str(filepath))

    if task_id:
        logger.info(f"Queued {safe_filename} for background processing (task={task_id})")
        return {
            "status": "success",
            "message": f"File '{safe_filename}' uploaded and queued for processing.",
            "task_id": task_id,
        }
    else:
        # Synchronous fallback
        try:
            result = DocumentManager.process_file_task(str(filepath))
            return {
                "status": "success",
                "message": f"File '{safe_filename}' processed successfully.",
                "chunks": result.get("chunks", 0),
            }
        except Exception as e:
            logger.error(f"Sync processing failed for {safe_filename}: {e}")
            if filepath.exists():
                filepath.unlink()
            raise HTTPException(status_code=500, detail=f"Processing failed: {e}")


@router.get("/documents")
async def list_documents():
    """List all uploaded and indexed documents."""
    from backend.services.ingestion.document_registry import DocumentRegistry
    docs = DocumentRegistry.list_all()
    return {"documents": docs}


@router.delete("/document/{filename}")
async def delete_document(filename: str):
    """Delete a document and its associated vectors."""
    from backend.database.vector_store import VectorStore
    from backend.services.ingestion.document_registry import DocumentRegistry
    settings = get_settings()
    
    deleted = VectorStore.delete_document(filename)
    DocumentRegistry.delete(filename)
    
    # Also delete the physical file
    filepath = settings.upload_path / filename
    file_deleted = False
    if filepath.exists():
        filepath.unlink()
        file_deleted = True
    
    if deleted == 0 and not file_deleted:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
    
    return {"status": "success", "filename": filename, "chunks_deleted": deleted}
