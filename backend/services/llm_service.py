"""LLM service for generating answers using OpenAI with RAG context."""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

from backend.config import get_settings
from backend.models.schemas import SourceReference, ChatResponse

logger = logging.getLogger(__name__)

# RAG prompt template
_SYSTEM_PROMPT = """You are an intelligent, strict AI assistant. Your ONLY goal is to analyze the provided document context and answer the user's question.

Guidelines:
1. STRICT SCOPE: You MUST ONLY answer questions using the provided context from the uploaded PDF. 
2. OFF-TOPIC QUESTIONS: If the user asks a question that is NOT covered by the provided context (e.g., general knowledge, coding, greetings, off-topic subjects), you MUST refuse to answer and politely state: "I can only answer questions based on the contents of the uploaded PDF documents."
3. Synthesize the Information: Explain the answer naturally in your own words based on the context.
4. Accuracy is Key: Your answer must be derived ONLY from the provided context.
5. Avoid Clunky Citations: Do not explicitly write "[Source X, Page Y]" inside your response. Just provide the synthesized answer seamlessly, as the user interface already handles source citations separately."""

_CONTEXT_TEMPLATE = """Context from uploaded documents:

{context}

---
Question: {question}"""


def _build_context(chunks: list[dict]) -> str:
    """Build a formatted context string from retrieved chunks.
    
    Args:
        chunks: List of retrieved chunk dicts with 'text', 'page', 'pdf'.
        
    Returns:
        Formatted context string with source labels.
    """
    context_parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        source_label = f"[Source {i}: {chunk['pdf']}, Page {chunk['page']}]"
        context_parts.append(f"{source_label}\n{chunk['text']}")
    
    return "\n\n".join(context_parts)


def _extract_sources(chunks: list[dict]) -> list[SourceReference]:
    """Extract source references from retrieved chunks.
    
    Args:
        chunks: List of retrieved chunk dicts.
        
    Returns:
        List of SourceReference objects.
    """
    sources: list[SourceReference] = []
    seen: set[tuple[str, int]] = set()
    
    for chunk in chunks:
        key = (chunk["pdf"], chunk["page"])
        if key not in seen:
            seen.add(key)
            # Use first 200 chars as excerpt
            excerpt = chunk["text"][:200].strip()
            if len(chunk["text"]) > 200:
                excerpt += "..."
            
            sources.append(SourceReference(
                pdf=chunk["pdf"],
                page=chunk["page"],
                excerpt=excerpt,
            ))
    
    return sources


async def generate_answer(
    question: str,
    chunks: list[dict],
    chat_history: list[dict] | None = None,
) -> ChatResponse:
    """Generate a complete answer using OpenAI.
    
    Args:
        question: The user's question.
        chunks: Retrieved context chunks.
        chat_history: Optional previous messages for context.
        
    Returns:
        ChatResponse with answer and sources.
    """
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
    
    context = _build_context(chunks)
    user_message = _CONTEXT_TEMPLATE.format(context=context, question=question)
    
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    
    # Add chat history for conversational context (last 6 messages max)
    if chat_history:
        for msg in chat_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_message})
    
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=1500,
    )
    
    answer = response.choices[0].message.content or "No response generated."
    sources = _extract_sources(chunks)
    
    return ChatResponse(answer=answer, sources=sources)


async def stream_answer(
    question: str,
    chunks: list[dict],
    chat_history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """Stream answer tokens using Server-Sent Events format.
    
    Yields SSE-formatted strings: 'data: {json}\n\n'
    
    Event types:
    - token: A single answer token
    - sources: The source references (sent at the end)
    - done: Signals completion
    - error: An error occurred
    
    Args:
        question: The user's question.
        chunks: Retrieved context chunks.
        chat_history: Optional previous messages.
        
    Yields:
        SSE-formatted event strings.
    """
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
    
    context = _build_context(chunks)
    user_message = _CONTEXT_TEMPLATE.format(context=context, question=question)
    
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    
    if chat_history:
        for msg in chat_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        stream = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=1500,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                event_data = json.dumps({"type": "token", "content": token})
                yield f"data: {event_data}\n\n"
        
        # Send sources after answer is complete
        sources = _extract_sources(chunks)
        sources_data = json.dumps({
            "type": "sources",
            "sources": [s.model_dump() for s in sources],
        })
        yield f"data: {sources_data}\n\n"
        
        # Send done signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        error_data = json.dumps({"type": "error", "content": str(e)})
        yield f"data: {error_data}\n\n"
