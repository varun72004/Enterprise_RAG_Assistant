import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class MemoryService:
    """In-memory session storage for conversation context."""
    
    # Store histories mapped by session_id
    _sessions: Dict[str, List[Dict[str, str]]] = {}

    @classmethod
    def get_history(cls, session_id: str) -> List[Dict[str, str]]:
        """Retrieve conversation history for a session."""
        if session_id not in cls._sessions:
            cls._sessions[session_id] = []
        return cls._sessions[session_id]

    @classmethod
    def add_interaction(cls, session_id: str, user_query: str, ai_response: str):
        """Append an interaction to the session history."""
        history = cls.get_history(session_id)
        history.append({"role": "user", "content": user_query})
        history.append({"role": "assistant", "content": ai_response})
        # Keep only last 10 interactions (20 messages) to prevent context bloat
        if len(history) > 20:
            cls._sessions[session_id] = history[-20:]
            
    @classmethod
    def format_history_for_prompt(cls, session_id: str) -> str:
        """Format history as a string block for the LLM prompt."""
        history = cls.get_history(session_id)
        if not history:
            return "No previous conversation."
            
        lines = []
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    @classmethod
    def clear_session(cls, session_id: str):
        """Clear memory for a session."""
        if session_id in cls._sessions:
            del cls._sessions[session_id]
            logger.info(f"Cleared session memory: {session_id}")
