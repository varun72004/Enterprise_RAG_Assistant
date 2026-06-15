"""FastAPI application entry point for Production-Grade RAG Assistant."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import get_settings
from backend.routes import upload, chat, metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    logger.info("=" * 60)
    logger.info("Production RAG System — Starting up...")
    logger.info("=" * 60)
    
    settings = get_settings()
    settings.upload_path
    settings.chroma_path
    
    # Pre-load models
    logger.info("Pre-loading models...")
    from backend.services.embedding_service import EmbeddingService
    from backend.services.retrieval.reranker import RerankerService
    EmbeddingService.get_model()
    RerankerService.get_model()
    
    # Initialize ChromaDB
    from backend.database.vector_store import VectorStore
    collection = VectorStore.get_collection()
    logger.info(f"ChromaDB ready. Existing chunks: {collection.count()}")
    
    logger.info("Ready!")
    yield
    
    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Production-Grade RAG Assistant",
    description="Scalable, enterprise-ready RAG application with PDF/HTML/CSV support, advanced retrieval, hallucination detection, and observability.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(upload.router, tags=["Documents"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(metrics.router, tags=["Observability"])

# Mount frontend static files
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")



@app.get("/")
async def serve_frontend():
    """Serve the frontend single-page application."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Production RAG Assistant API is running. Frontend not found."}


@app.get("/dashboard")
async def serve_dashboard():
    """Serve the observability metrics dashboard."""
    dashboard_path = frontend_dir / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(str(dashboard_path))
    return {"message": "Dashboard not found."}
