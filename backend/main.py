"""FastAPI application entry point for PDF AI Chatbot."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import get_settings
from backend.routes import upload, chat

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
    logger.info("PDF AI Chatbot — Starting up...")
    logger.info("=" * 60)
    
    settings = get_settings()
    
    # Ensure directories exist
    settings.upload_path
    settings.chroma_path
    
    # Pre-load the embedding model
    logger.info("Pre-loading embedding model...")
    from backend.services.embedding_service import get_model
    get_model()
    
    # Initialize ChromaDB
    logger.info("Initializing ChromaDB...")
    from backend.database.vector_store import get_collection
    collection = get_collection()
    logger.info(f"ChromaDB ready. Existing chunks: {collection.count()}")
    
    logger.info("=" * 60)
    logger.info("PDF AI Chatbot — Ready!")
    logger.info(f"Open http://localhost:8000 in your browser")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("PDF AI Chatbot — Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="PDF AI Chatbot",
    description="A RAG-powered chatbot for querying PDF documents.",
    version="1.0.0",
    lifespan=lifespan,
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
    return {"message": "PDF AI Chatbot API is running. Frontend not found."}
