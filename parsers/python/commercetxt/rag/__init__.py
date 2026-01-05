"""
RAG (Retrieval-Augmented Generation) support for CommerceTXT.

Converts structured commerce data into vector-database-ready shards
with semantic tagging for intelligent filtering.

Features async architecture, caching, and production metrics.
"""

from .async_pipeline import AsyncRAGPipeline
from .container import RAGContainer
from .core.generator import RAGGenerator
from .core.rate_limiter import RateLimiter, rate_limit
from .core.semantic_tags import SemanticTagger
from .core.shards import ShardBuilder
from .exceptions import (
    EmbeddingError,
    HealthCheckError,
    RAGError,
    RateLimitError,
    StorageError,
    ValidationError,
    VectorStoreError,
)
from .monitoring import HealthMonitor, create_health_endpoint
from .pipeline import RAGPipeline
from .tools import AIHealthChecker, SchemaBridge, SemanticNormalizer

__all__ = [
    "AIHealthChecker",
    "AsyncRAGPipeline",
    "EmbeddingError",
    "HealthCheckError",
    "HealthMonitor",
    "create_health_endpoint",
    "RAGContainer",
    "RAGError",
    "RAGGenerator",
    "RAGPipeline",
    "RateLimitError",
    "RateLimiter",
    "rate_limit",
    "SchemaBridge",
    "SemanticNormalizer",
    "SemanticTagger",
    "ShardBuilder",
    "StorageError",
    "ValidationError",
    "VectorStoreError",
]

__version__ = "1.0.0"
