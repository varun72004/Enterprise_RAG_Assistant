import json
import logging
import time
import asyncio
import math
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse

from backend.config import get_settings
from backend.models.schemas import ChatRequest, HealthResponse
from backend.services.retrieval.retriever import RetrieverService, ContextCompressor
from backend.services.retrieval.reranker import RerankerService
from backend.services.embedding_service import EmbeddingService
from backend.services.llm.fallback_manager import FallbackManager
from backend.services.memory_service import MemoryService
from backend.services.security.prompt_guard import PromptGuard
from backend.services.hallucination_checker import HallucinationChecker
from backend.database.vector_store import VectorStore
from backend.monitoring.metrics import MetricsStore

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/chat")
async def chat(request: ChatRequest, x_session_id: str | None = Header(None)):
    start_time = time.time()
    session_id = x_session_id or "default_session"
    question = request.question.strip()
    settings = get_settings()
    
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
        
    # 1. Prompt Injection Defense
    is_safe, error_msg = PromptGuard.check_query(question)
    if not is_safe:
        MetricsStore.record_security_event("Prompt Injection Blocked", question)
        MetricsStore.record_query(time.time() - start_time, error=True)
        raise HTTPException(status_code=400, detail=error_msg)
        
    async def event_generator():
        generation_start = time.time()
        full_answer = []
        error_occurred = False
        chunks = []
        context_str = "No documents found."
        
        try:
            # Step 1: Retrieving
            yield f"data: {json.dumps({'type': 'status', 'content': 'Retrieving Documents...'})}\n\n"
            await asyncio.sleep(0.1)
            
            retrieval_start = time.time()
            query_embedding = EmbeddingService.embed_query(question)
            initial_results = VectorStore.query(
                embedding=query_embedding,
                top_k=settings.TOP_K_RESULTS
            )
            retrieval_latency = time.time() - retrieval_start
            MetricsStore.record_retrieval(retrieval_latency)
            
            # Step 2: Reranking
            yield f"data: {json.dumps({'type': 'status', 'content': 'Reranking Results...'})}\n\n"
            await asyncio.sleep(0.1)
            
            if initial_results:
                reranked_results = RerankerService.rerank(
                    query=question,
                    chunks=initial_results,
                    top_k=settings.TOP_K_RERANK
                )
            else:
                reranked_results = []
                
            # Step 3: Compressing
            yield f"data: {json.dumps({'type': 'status', 'content': 'Compressing Context...'})}\n\n"
            await asyncio.sleep(0.1)
            
            total_original_len = 0
            total_compressed_len = 0
            for result in reranked_results:
                result["original_text"] = result["text"]
                compressed = ContextCompressor.compress(question, result["text"])
                result["text"] = compressed
                total_original_len += len(result["original_text"])
                total_compressed_len += len(compressed)
                
            compression_ratio = 1.0
            if total_original_len > 0:
                compression_ratio = total_compressed_len / total_original_len
            
            context_tokens = int(total_compressed_len / 4)
            chunks = reranked_results
            
            if chunks:
                context_str = "\n\n".join([f"[Source: {c['metadata'].get('source_file', 'Unknown')} | Page: {c['metadata'].get('page_number', '?')}]\n{c['text']}" for c in chunks])
                
            # Yield pipeline stats
            pipeline_data = {
                'type': 'pipeline',
                'retrieved_chunks': len(initial_results),
                'reranked_chunks': len(reranked_results),
                'compression_ratio': round(compression_ratio, 2),
                'context_tokens': context_tokens
            }
            yield f"data: {json.dumps(pipeline_data)}\n\n"
            
            # Step 4: Generating
            yield f"data: {json.dumps({'type': 'status', 'content': 'Generating Answer...'})}\n\n"
            await asyncio.sleep(0.1)
            
            # Fetch Session History
            history_str = MemoryService.format_history_for_prompt(session_id)
            system_prompt = "You are a helpful AI assistant. Answer the user's question based ONLY on the provided context. If the context does not contain the answer, say so. Do not hallucinate."
            
            # Stream Generation
            async for token in FallbackManager.generate_stream(system_prompt, context_str, history_str, question):
                full_answer.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                
        except Exception as e:
            error_occurred = True
            logger.error(f"Error in chat stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': 'An error occurred during generation.'})}\n\n"
            raise e
        finally:
            generation_latency = time.time() - generation_start
            MetricsStore.record_generation(generation_latency)
            
            total_latency = time.time() - start_time
            MetricsStore.record_query(total_latency, error=error_occurred)
            
        final_answer = "".join(full_answer)
        
        # 5. Save to Memory
        MemoryService.add_interaction(session_id, question, final_answer)
        
        # 6. Hallucination Detection & Grounding Score
        hallucination_result = HallucinationChecker.check_hallucination(final_answer, context_str)
        MetricsStore.record_hallucination(hallucination_result["is_hallucinated"])
        if hallucination_result["is_hallucinated"]:
            yield f"data: {json.dumps({'type': 'token', 'content': hallucination_result['warning']})}\n\n"
            
        if hallucination_result["is_hallucinated"]:
            grounding_score = max(0.0, min(0.4, 1.0 / (1.0 + math.exp(-hallucination_result.get("score", -1.0)))))
        else:
            grounding_score = max(0.8, min(1.0, 1.0 / (1.0 + math.exp(-hallucination_result.get("score", 1.0)))))
        MetricsStore.record_grounding_score(grounding_score)
        
        # 7. Record Retrieval Precision
        if chunks:
            avg_precision = sum(1.0 / (1.0 + math.exp(-c.get("rerank_score", 0.0))) for c in chunks) / len(chunks)
        else:
            avg_precision = 0.0
        MetricsStore.record_retrieval_precision(avg_precision)
        
        # 8. Record Cost
        input_tokens = (len(context_str) + len(question)) / 4.0
        output_tokens = len(final_answer) / 4.0
        cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1000000.0
        MetricsStore.record_cost(cost)
        
        # 9. Append Citations
        citations = []
        for c in chunks:
            # Map distance score to percentage confidence
            score_val = c.get('score', 0.85)
            # Standardize similarity score
            citations.append({
                "file": c['metadata'].get('source_file'),
                "page": c['metadata'].get('page_number'),
                "score": float(score_val),
                "rerank_score": float(c.get('rerank_score', 0.0)),
                "excerpt": c.get('original_text', c.get('text', ''))[:400]
            })
            
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@router.post("/clear-session")
async def clear_session(x_session_id: str | None = Header(None)):
    session_id = x_session_id or "default_session"
    MemoryService.clear_session(session_id)
    return {"status": "success", "message": "Session memory cleared."}

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        documents_count=0, # Simplified for now
        chroma_status="connected" if VectorStore.is_healthy() else "disconnected",
        embedding_model=get_settings().EMBEDDING_MODEL,
    )

@router.get("/history")
async def get_history(x_session_id: str | None = Header(None)):
    session_id = x_session_id or "default_session"
    history = MemoryService.get_history(session_id)
    return {"history": history}
