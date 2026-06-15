import logging
from typing import AsyncGenerator
from backend.services.llm.openai_provider import OpenAIProvider
from backend.services.llm.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

class FallbackManager:
    """Manages LLM requests with primary and fallback providers."""

    @classmethod
    async def generate_stream(cls, system_prompt: str, context_str: str, history_str: str, query: str) -> AsyncGenerator[str, None]:
        """
        Try OpenAI first. If it fails, fallback to Gemini.
        """
        try:
            logger.info("Attempting primary LLM provider (OpenAI)")
            async for chunk in OpenAIProvider.generate_stream(system_prompt, context_str, history_str, query):
                yield chunk
        except Exception as e:
            logger.warning(f"Primary provider failed: {str(e)}. Attempting fallback (Gemini)")
            try:
                # Iterate and yield from the sync fallback generator wrapped in async
                async for chunk in GeminiProvider.generate_stream(system_prompt, context_str, history_str, query):
                    yield chunk
            except Exception as e2:
                logger.error(f"Fallback provider also failed: {str(e2)}")
                yield "\n\n[System Error: Both primary and fallback AI providers are currently unavailable. Please try again later.]"
