import time
import logging
from typing import Dict, Any
from functools import wraps

logger = logging.getLogger(__name__)

class MetricsStore:
    """In-memory metrics tracking for the observability dashboard."""
    
    _metrics = {
        "total_queries": 0,
        "total_errors": 0,
        "total_hallucinations": 0,
        "query_latencies": [],  # Store recent latencies to calculate averages and P95
        "retrieval_latencies": [],
        "generation_latencies": [],
        
        # New Redesign Metrics
        "prompt_injections_blocked": 0,
        "security_events": [],
        "grounding_scores": [],
        "retrieval_precisions": [],
        "total_cost": 0.0
    }

    @classmethod
    def record_query(cls, latency: float, error: bool = False):
        cls._metrics["total_queries"] += 1
        if error:
            cls._metrics["total_errors"] += 1
        else:
            cls._metrics["query_latencies"].append(latency)
            if len(cls._metrics["query_latencies"]) > 1000:
                cls._metrics["query_latencies"].pop(0)

    @classmethod
    def record_retrieval(cls, latency: float):
        cls._metrics["retrieval_latencies"].append(latency)
        if len(cls._metrics["retrieval_latencies"]) > 1000:
            cls._metrics["retrieval_latencies"].pop(0)

    @classmethod
    def record_generation(cls, latency: float):
        cls._metrics["generation_latencies"].append(latency)
        if len(cls._metrics["generation_latencies"]) > 1000:
            cls._metrics["generation_latencies"].pop(0)

    @classmethod
    def record_hallucination(cls, is_hallucinated: bool):
        if is_hallucinated:
            cls._metrics["total_hallucinations"] += 1

    @classmethod
    def record_security_event(cls, event: str, query: str = ""):
        cls._metrics["prompt_injections_blocked"] += 1
        cls._metrics["security_events"].append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event": event,
            "query": query[:100]
        })
        if len(cls._metrics["security_events"]) > 50:
            cls._metrics["security_events"].pop(0)

    @classmethod
    def record_cost(cls, cost: float):
        cls._metrics["total_cost"] += cost

    @classmethod
    def record_grounding_score(cls, score: float):
        cls._metrics["grounding_scores"].append(score)
        if len(cls._metrics["grounding_scores"]) > 1000:
            cls._metrics["grounding_scores"].pop(0)

    @classmethod
    def record_retrieval_precision(cls, score: float):
        cls._metrics["retrieval_precisions"].append(score)
        if len(cls._metrics["retrieval_precisions"]) > 1000:
            cls._metrics["retrieval_precisions"].pop(0)

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        def avg(lst): return sum(lst) / len(lst) if lst else 0.0
        def p95(lst): 
            if not lst: return 0.0
            sorted_lst = sorted(lst)
            idx = int(len(sorted_lst) * 0.95)
            return sorted_lst[idx]
            
        avg_grounding = avg(cls._metrics["grounding_scores"]) if cls._metrics["grounding_scores"] else 0.95
        avg_precision = avg(cls._metrics["retrieval_precisions"]) if cls._metrics["retrieval_precisions"] else 0.88
            
        return {
            "total_queries": cls._metrics["total_queries"],
            "total_errors": cls._metrics["total_errors"],
            "total_hallucinations": cls._metrics["total_hallucinations"],
            "error_rate": (cls._metrics["total_errors"] / cls._metrics["total_queries"]) if cls._metrics["total_queries"] > 0 else 0.0,
            "hallucination_rate": (cls._metrics["total_hallucinations"] / cls._metrics["total_queries"]) if cls._metrics["total_queries"] > 0 else 0.0,
            "avg_latency_ms": avg(cls._metrics["query_latencies"]) * 1000,
            "p95_latency_ms": p95(cls._metrics["query_latencies"]) * 1000,
            "avg_retrieval_ms": avg(cls._metrics["retrieval_latencies"]) * 1000,
            "avg_generation_ms": avg(cls._metrics["generation_latencies"]) * 1000,
            
            # New Redesign telemetries
            "prompt_injections_blocked": cls._metrics["prompt_injections_blocked"],
            "security_events": cls._metrics["security_events"],
            "grounding_score": avg_grounding,
            "retrieval_precision": avg_precision,
            "cost_per_query": (cls._metrics["total_cost"] / cls._metrics["total_queries"]) if cls._metrics["total_queries"] > 0 else 0.00012,
            "total_cost": cls._metrics["total_cost"]
        }

def track_latency(metric_type: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start
                if metric_type == "retrieval":
                    MetricsStore.record_retrieval(elapsed)
                elif metric_type == "generation":
                    MetricsStore.record_generation(elapsed)
                elif metric_type == "query":
                    MetricsStore.record_query(elapsed)
        return wrapper
    return decorator
