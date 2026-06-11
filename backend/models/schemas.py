"""Pydantic request/response schemas for API endpoints."""

from datetime import datetime
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response after successful PDF upload and processing."""
    status: str = "success"
    filename: str
    pages_extracted: int = 0
    chunks_created: int = 0


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    question: str = Field(..., min_length=1, max_length=2000, description="User question")


class SourceReference(BaseModel):
    """Source attribution for a retrieved chunk."""
    pdf: str
    page: int
    excerpt: str


class ChatResponse(BaseModel):
    """Complete chat response with sources."""
    answer: str
    sources: list[SourceReference] = []


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    sources: list[SourceReference] = []
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class DocumentInfo(BaseModel):
    """Information about an uploaded document."""
    filename: str
    pages: int
    chunks: int
    uploaded_at: str
    file_size_mb: float


class DocumentListResponse(BaseModel):
    """Response for listing all documents."""
    documents: list[DocumentInfo] = []
    total_count: int = 0


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    documents_count: int = 0
    chroma_status: str = "connected"
    embedding_model: str = ""


class ErrorResponse(BaseModel):
    """Standard error response."""
    status: str = "error"
    detail: str
