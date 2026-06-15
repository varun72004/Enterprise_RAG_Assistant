import logging
from sentence_transformers import CrossEncoder
from backend.config import get_settings

logger = logging.getLogger(__name__)

class HallucinationChecker:
    """
    Validates if the generated answer is supported by the retrieved context
    using a cross-encoder to compute semantic entailment/similarity.
    """
    
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            settings = get_settings()
            # Reuse the reranker model for similarity checking to save memory
            logger.info(f"Loading hallucination checker model: {settings.RERANKER_MODEL}")
            cls._model = CrossEncoder(settings.RERANKER_MODEL)
        return cls._model

    @classmethod
    def check_hallucination(cls, answer: str, context: str) -> dict:
        """
        Compare the generated answer vs the retrieved context.
        If confidence is low, return a warning.
        
        Args:
            answer: The LLM generated answer.
            context: The retrieved context blocks combined.
            
        Returns:
            dict containing is_hallucinated (bool), score (float), and warning (str)
        """
        if not answer or not context:
            return {"is_hallucinated": False, "score": 1.0, "warning": ""}

        # Refusal check to prevent false positives when LLM correctly refuses to answer or states constraints
        refusal_phrases = [
            "does not contain",
            "not mentioned",
            "no mention",
            "not provide",
            "not enough information",
            "does not specify",
            "unable to find",
            "cannot answer",
            "not found in the context",
            "no information about",
            "is not contained in the provided",
            "no document",
            "context does not",
        ]
        answer_lower = answer.lower()
        if any(phrase in answer_lower for phrase in refusal_phrases):
            return {"is_hallucinated": False, "score": 1.0, "warning": ""}
            
        model = cls.get_model()
        
        # Predict entailment / similarity
        score = float(model.predict([context, answer]))
        
        # A simple threshold heuristic. Cross-encoder scores vary by model.
        # ms-marco-MiniLM typically outputs logits. We can apply sigmoid if needed, 
        # but let's assume a generic threshold logic. If score is below 0, it indicates poor overlap.
        is_hallucinated = score < 0.0
        
        warning = ""
        if is_hallucinated:
            warning = "\n\n⚠️ **Warning:** The answer may not be fully supported by the source documents."
            logger.warning(f"Possible hallucination detected. Score: {score}")
            
        return {
            "is_hallucinated": is_hallucinated,
            "score": score,
            "warning": warning
        }
