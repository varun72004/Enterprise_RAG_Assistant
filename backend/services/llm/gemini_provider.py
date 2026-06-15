import logging
import asyncio
from typing import AsyncGenerator
from backend.config import get_settings

logger = logging.getLogger(__name__)

class GeminiProvider:
    """Fallback LLM provider using Google Gemini via the new google-genai SDK."""

    @classmethod
    async def generate_stream(cls, system_prompt: str, context_str: str, history_str: str, query: str) -> AsyncGenerator[str, None]:
        """Generate streaming response from Gemini API."""
        settings = get_settings()
        
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured.")
        
        full_prompt = f"""System: {system_prompt}

Context from uploaded documents:
---
{context_str}
---

Conversation History:
{history_str}

User Question: {query}"""

        gemini_model = settings.GEMINI_MODEL
        if gemini_model in ("gemini-1.5-flash", "models/gemini-1.5-flash", ""):
            gemini_model = "gemini-2.5-flash"

        try:
            logger.info(f"Calling Gemini Fallback with model: {gemini_model}")
            
            # Try the new google.genai SDK first
            try:
                from google import genai
                
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                response = client.models.generate_content_stream(
                    model=gemini_model,
                    contents=full_prompt,
                )
                
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                        await asyncio.sleep(0.01)
                        
            except ImportError:
                # Fall back to the deprecated SDK
                import google.generativeai as genai
                
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel(gemini_model)
                response = model.generate_content(full_prompt, stream=True)
                
                for chunk in response:
                    if chunk.text:
                        yield chunk.text
                        await asyncio.sleep(0.01)
                        
        except Exception as e:
            logger.error(f"Gemini Generation Error: {str(e)}")
            raise
