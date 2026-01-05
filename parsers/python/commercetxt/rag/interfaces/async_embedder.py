"""
Async embedder interface for text vectorization.

Defines the contract for async embedding providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AsyncBaseEmbedder(ABC):
    """
    Abstract base for async text embedding providers.

    Allows switching between OpenAI, Azure, local models with async support.
    """

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """
        Convert a single string into a vector asynchronously.

        Args:
            text: Input text to embed

        Returns:
            Vector as list of floats (typically 384 or 1536 dimensions)

        Example:
            vector = await embedder.embed_text("wireless headphones")
            # [0.123, -0.456, 0.789, ...]
        """
        pass

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Batch embed multiple texts asynchronously.

        Args:
            texts: List of input texts

        Returns:
            List of vectors

        Example:
            vectors = await embedder.embed_texts([
                "wireless headphones",
                "bluetooth speaker"
            ])
            # [[0.1, 0.2, ...], [0.3, 0.4, ...]]
        """
        pass

    @abstractmethod
    async def embed_shards(self, shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Batch process a list of shards asynchronously.

        Must populate the 'values' key in each shard with the embedding vector.

        Args:
            shards: List of shard dictionaries with 'text' key

        Returns:
            Same shards with 'values' key added

        Example:
            shards = [
                {'text': 'Product description', 'metadata': {...}},
                {'text': 'Price: $99', 'metadata': {...}}
            ]
            result = await embedder.embed_shards(shards)
            # Each shard now has 'values': [0.1, 0.2, ...]
        """
        pass
