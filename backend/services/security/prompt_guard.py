import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class PromptGuard:
    """Security layer to detect and block malicious prompt injections."""
    
    # List of heuristic rules/substrings indicating a potential injection
    MALICIOUS_PATTERNS = [
        "ignore previous",
        "ignore all previous",
        "system prompt",
        "what are your instructions",
        "reveal your instructions",
        "forget what i told you",
        "api key",
        "you are now a",
        "bypass",
        "developer mode"
    ]

    @classmethod
    def check_query(cls, query: str) -> Tuple[bool, str]:
        """
        Validate the user query.
        
        Returns:
            Tuple (is_safe, error_message).
            If is_safe is False, error_message contains the reason.
        """
        query_lower = query.lower()
        
        for pattern in cls.MALICIOUS_PATTERNS:
            if pattern in query_lower:
                logger.warning(f"Blocked malicious query matching pattern '{pattern}': {query}")
                return False, "Your query was blocked due to potential prompt injection or policy violation."
                
        return True, ""
