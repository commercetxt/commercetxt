"""
Async vector store interface for semantic search.

Defines the contract for async vector database backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AsyncBaseVectorStore(ABC):
    """
    Abstract base for async vector database backends.

    Provides non-blocking vector operations for high-concurrency scenarios.
    """

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to vector database asynchronously.

        Returns:
            True if connection successful

        Example:
            success = await vector_store.connect()
        """
        pass

    @abstractmethod
    async def upsert(self, shards: list[dict[str, Any]], namespace: str) -> int:
        """
        Insert or update vectors asynchronously.

        Args:
            shards: List of shard dictionaries with 'values' (vector) and 'metadata'
            namespace: Target namespace for isolation

        Returns:
            Number of vectors upserted

        Example:
            count = await vector_store.upsert(shards, namespace='products')
            # Returns: 15
        """
        pass

    @abstractmethod
    async def search(
        self, vector: list[float], top_k: int = 5, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors asynchronously.

        Args:
            vector: Query vector
            top_k: Number of results to return
            namespace: Filter by namespace (optional)

        Returns:
            List of matches with 'id', 'score', and 'metadata'

        Example:
            results = await vector_store.search(query_vector, top_k=10)
            # [
            #     {'id': 'vec_123', 'score': 0.95, 'metadata': {...}},
            #     {'id': 'vec_456', 'score': 0.87, 'metadata': {...}}
            # ]
        """
        pass

    @abstractmethod
    async def delete(
        self,
        ids: list[str] | None = None,
        namespace: str | None = None,
        delete_all: bool = False,
    ) -> bool:
        """
        Delete vectors asynchronously.

        Args:
            ids: List of vector IDs to delete
            namespace: Delete all vectors in namespace
            delete_all: Delete all vectors (use with caution)

        Returns:
            True if deletion successful
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Check vector store health asynchronously.

        Returns:
            Health status dictionary
        """
        pass
