import logging
from fastapi import APIRouter
from backend.monitoring.metrics import MetricsStore

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/metrics")
async def get_metrics():
    """Retrieve observability metrics."""
    from backend.database.vector_store import VectorStore
    metrics = MetricsStore.get_metrics()
    
    try:
        collection = VectorStore.get_collection()
        metrics["vector_chunks"] = collection.count()
        metrics["documents_indexed"] = len(VectorStore.list_documents())
    except Exception as e:
        logger.error(f"Error fetching database counts for metrics: {e}")
        metrics["vector_chunks"] = 0
        metrics["documents_indexed"] = 0
        
    return metrics
