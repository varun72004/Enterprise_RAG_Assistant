import logging
from typing import AsyncGenerator
from openai import AsyncOpenAI
from backend.config import get_settings

logger = logging.getLogger(__name__)

class OpenAIProvider:
    """Primary LLM provider using OpenAI-compatible API (supports OpenRouter)."""

    @classmethod
    async def generate_stream(cls, system_prompt: str, context_str: str, history_str: str, query: str) -> AsyncGenerator[str, None]:
        """Generate streaming response from OpenAI or OpenRouter."""
        settings = get_settings()
        
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not configured.")
        
        # Detect OpenRouter key and set base_url accordingly
        api_key = settings.OPENAI_API_KEY
        base_url = None
        model = settings.OPENAI_MODEL
        
        if api_key.startswith("sk-or-"):
            # This is an OpenRouter key
            base_url = "https://openrouter.ai/api/v1"
            # Fix model name if it's a placeholder or retired free model
            if model in ("openrouter/free", "", "google/gemini-2.0-flash-exp:free"):
                model = "google/gemma-4-31b-it:free"
            logger.info(f"Using OpenRouter with model: {model}")
        
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        
        prompt = f"""Context from uploaded documents:
---
{context_str}
---
Conversation History:
{history_str}

User Question: {query}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            logger.info(f"Calling LLM with model: {model}")
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                temperature=0.2,
                max_tokens=1000
            )
            
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI/OpenRouter Generation Error: {str(e)}")
            raise
