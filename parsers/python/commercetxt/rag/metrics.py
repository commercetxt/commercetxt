"""
Basic Prometheus metrics for RAG system monitoring.

Provides counters, histograms, and gauges for production observability.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any

try:
    from prometheus_client import (  # type: ignore[import-not-found]
        Counter,
        Gauge,
        Histogram,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


# Counters (monotonically increasing)
ingest_total = (
    Counter(
        "rag_ingest_total",
        "Total products ingested",
        ["status"],  # success, skipped, failed
    )
    if PROMETHEUS_AVAILABLE
    else None
)

search_total = (
    Counter(
        "rag_search_total", "Total searches executed", ["status"]  # success, failed
    )
    if PROMETHEUS_AVAILABLE
    else None
)

embedding_api_calls = (
    Counter(
        "rag_embedding_api_calls_total",
        "Total embedding API calls",
        ["provider"],  # openai, local
    )
    if PROMETHEUS_AVAILABLE
    else None
)

vector_store_operations = (
    Counter(
        "rag_vector_store_operations_total",
        "Total vector store operations",
        ["operation", "backend"],  # upsert/search, faiss/pinecone/qdrant
    )
    if PROMETHEUS_AVAILABLE
    else None
)

# Histograms (latency distribution)
search_latency = (
    Histogram(
        "rag_search_latency_seconds",
        "Search operation latency",
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
    )
    if PROMETHEUS_AVAILABLE
    else None
)

ingest_latency = (
    Histogram(
        "rag_ingest_latency_seconds",
        "Ingest operation latency",
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    )
    if PROMETHEUS_AVAILABLE
    else None
)

embedding_latency = (
    Histogram(
        "rag_embedding_latency_seconds",
        "Embedding generation latency",
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
    )
    if PROMETHEUS_AVAILABLE
    else None
)

# Gauges (point-in-time measurements)
cache_hit_ratio = (
    Gauge(
        "rag_cache_hit_ratio",
        "Cache hit ratio",
        ["cache_type"],  # embedding, search, slm
    )
    if PROMETHEUS_AVAILABLE
    else None
)

active_connections = (
    Gauge(
        "rag_active_connections",
        "Active database connections",
        ["backend"],  # faiss, pinecone, qdrant, redis
    )
    if PROMETHEUS_AVAILABLE
    else None
)


def track_latency(histogram: Histogram | None) -> Callable:
    """
    Decorator to track function execution latency.

    Args:
        histogram: Prometheus histogram to record latency

    Example:
        @track_latency(search_latency)
        def search(query):
            return results
    """

    def decorator(func: Callable) -> Callable:
        if not PROMETHEUS_AVAILABLE or histogram is None:
            return func

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                histogram.observe(time.time() - start)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                histogram.observe(time.time() - start)

        # Return appropriate wrapper
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def count_calls(counter: Counter | None, **labels: str) -> Callable:
    """
    Decorator to count function calls.

    Args:
        counter: Prometheus counter to increment
        **labels: Label values for the counter

    Example:
        @count_calls(ingest_total, status="success")
        def ingest(data):
            return count
    """

    def decorator(func: Callable) -> Callable:
        if not PROMETHEUS_AVAILABLE or counter is None:
            return func

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            counter.labels(**labels).inc()
            return result

        return wrapper

    return decorator


def get_metrics_summary() -> dict[str, Any]:
    """
    Get current metrics summary.

    Returns:
        Dictionary with metric values (or empty if Prometheus not available)
    """
    if not PROMETHEUS_AVAILABLE:
        return {"error": "prometheus_client not installed"}

    try:
        from prometheus_client import REGISTRY

        metrics = {}
        for collector in REGISTRY._collector_to_names:
            for metric in collector.collect():
                metrics[metric.name] = {
                    "type": metric.type,
                    "documentation": metric.documentation,
                    "samples": len(metric.samples) if hasattr(metric, "samples") else 0,
                }
        return metrics
    except Exception as e:
        return {"error": str(e)}


def export_metrics_to_prometheus() -> str:
    """
    Export metrics in Prometheus text format.

    Returns:
        Metrics in Prometheus exposition format
    """
    if not PROMETHEUS_AVAILABLE:
        return "# prometheus_client not installed\n"

    try:
        from prometheus_client import REGISTRY, generate_latest

        result = generate_latest(REGISTRY)
        return result.decode("utf-8") if isinstance(result, bytes) else str(result)
    except Exception as e:
        return f"# Error exporting metrics: {e}\n"


# Helper to check if metrics are enabled
def metrics_enabled() -> bool:
    """Check if Prometheus metrics are available."""
    return PROMETHEUS_AVAILABLE
