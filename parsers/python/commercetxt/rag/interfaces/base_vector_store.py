"""
Base Vector Store Interface.

Abstract base class for vector database providers.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseVectorStore(ABC):
    """
    Contract for Vector Databases.
    Allows switching between Pinecone, Weaviate, Qdrant, etc.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection."""
        pass

    @abstractmethod
    def upsert(self, shards: list[dict[str, Any]], namespace: str) -> int:
        """Upload vectors. Returns count of uploaded items."""
        pass

    @abstractmethod
    def search(
        self, vector: list[float], top_k: int = 5, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve similar items."""
        pass
