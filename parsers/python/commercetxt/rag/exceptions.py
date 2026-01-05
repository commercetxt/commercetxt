"""
Custom exception hierarchy for RAG system.

Provides structured error handling with context for production debugging.
"""

from __future__ import annotations

from typing import Any


class RAGError(Exception):
    """
    Base exception for all RAG-related errors.

    Includes context dictionary for structured logging and debugging.
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        """
        Initialize RAG exception.

        Args:
            message: Human-readable error message
            context: Additional context (product_id, operation, etc.)
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (context: {context_str})"
        return self.message


class StorageError(RAGError):
    """
    Storage backend errors (local, Redis, etc.).

    Examples:
        - File not found
        - Redis connection failure
        - Cache corruption
    """

    pass


class EmbeddingError(RAGError):
    """
    Embedding generation errors.

    Examples:
        - API rate limit exceeded
        - Model not found
        - Invalid input text
    """

    pass


class VectorStoreError(RAGError):
    """
    Vector database errors (Faiss, Pinecone, Qdrant).

    Examples:
        - Connection failure
        - Index not found
        - Dimension mismatch
    """

    pass


class ValidationError(RAGError):
    """
    Data validation errors.

    Examples:
        - Missing required fields
        - Invalid data format
        - Schema violation
    """

    pass


class HealthCheckError(RAGError):
    """
    Health check failures.

    Examples:
        - Low quality score
        - Missing critical fields
        - Unusable data
    """

    pass


class RateLimitError(RAGError):
    """
    Rate limiting errors.

    Examples:
        - API quota exceeded
        - Too many requests
    """

    pass
