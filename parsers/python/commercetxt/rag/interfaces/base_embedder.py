"""
Base Embedder Interface.

Abstract base class for text embedding providers.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseEmbedder(ABC):
    """
    Contract for Embedding Models.
    Allows switching between OpenAI, Azure, or Local models.
    """

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Convert a single string into a vector."""
        pass

    @abstractmethod
    def embed_shards(self, shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Batch process a list of shards.
        Must populate the 'values' key in each shard.
        """
        pass
