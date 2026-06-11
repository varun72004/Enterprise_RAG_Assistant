"""Chat and conversation routes."""

import logging
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse

from backend.config import get_settings
from backend.models.schemas import ChatRequest, ChatResponse, HealthResponse
from backend.services.retriever import retrieve
from backend.services.llm_service import stream_answer
from backend.services.embedding_service import get_model_name
from backend.database.vector_store import get_document_count, is_healthy as chroma_healthy

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory chat history (partitioned by session_id)
_chat_history: dict[str, list[dict]] = {}


@router.post("/chat")
async def chat(request: ChatRequest, x_session_id: str | None = Header(None)):
    """Process a chat question and stream the answer.
    
    Retrieves relevant context from uploaded documents,
    then streams the LLM response token by token via SSE.
    """
    settings = get_settings()
    question = request.question.strip()
    
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OpenAI API key not configured. Set OPENAI_API_KEY in .env file.",
        )
    
    # Check if any documents are uploaded
    doc_count = get_document_count()
    if doc_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No documents uploaded yet. Please upload a PDF first.",
        )
    
    # Retrieve relevant chunks, filtering by session
    chunks = retrieve(question, session_id=x_session_id)
    
    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="Could not find relevant information in the uploaded documents.",
        )
    
    # Add user message to history
    session_key = x_session_id or "default"
    _chat_history.setdefault(session_key, []).append({"role": "user", "content": question})
    
    # Stream the response
    async def event_generator():
        full_answer = []
        async for event in stream_answer(question, chunks, _chat_history[session_key]):
            yield event
            # Collect tokens for history
            import json as _json
            try:
                line = event.strip()
                if line.startswith("data: "):
                    data = _json.loads(line[6:])
                    if data.get("type") == "token":
                        full_answer.append(data["content"])
            except Exception:
                pass
        
        # Save assistant response to history
        _chat_history[session_key].append({
            "role": "assistant",
            "content": "".join(full_answer),
        })
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/clear-chat")
async def clear_chat(x_session_id: str | None = Header(None)):
    """Clear the conversation history."""
    session_key = x_session_id or "default"
    if session_key in _chat_history:
        _chat_history[session_key] = []
    return {"status": "success", "message": "Chat history cleared."}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check system health status."""
    return HealthResponse(
        status="healthy",
        documents_count=get_document_count(),
        chroma_status="connected" if chroma_healthy() else "disconnected",
        embedding_model=get_model_name(),
    )
