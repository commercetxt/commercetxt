"""
Async OpenAI embedder using httpx for native async HTTP.

Generates embeddings via OpenAI API without blocking.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ..core.rate_limiter import RateLimiter
from ..interfaces.async_embedder import AsyncBaseEmbedder

logger = logging.getLogger(__name__)


class AsyncOpenAIEmbedder(AsyncBaseEmbedder):
    """
    Async OpenAI embedder with native HTTP async support.

    Uses httpx.AsyncClient for non-blocking API calls.
    Includes automatic rate limiting.

    Example:
        embedder = AsyncOpenAIEmbedder(api_key="sk-...")

        # Single text
        vector = await embedder.embed_text("wireless headphones")

        # Batch
        vectors = await embedder.embed_texts([
            "product 1",
            "product 2"
        ])
    """

    API_BASE = "https://api.openai.com/v1"
    DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        requests_per_second: float = 3.0,
        timeout: float = 30.0,
    ):
        """
        Initialize AsyncOpenAIEmbedder.

        Args:
            api_key: OpenAI API key (falls back to OPENAI_API_KEY env var)
            model: Model name (default: text-embedding-3-small)
            requests_per_second: Rate limit for API calls
            timeout: HTTP timeout in seconds
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required")

        self.model = model
        self.timeout = timeout
        self.rate_limiter = RateLimiter(calls_per_second=requests_per_second)
        self._client = None

    async def _get_client(self):
        """Get or create async HTTP client."""
        if self._client is None:
            try:
                import httpx

                self._client = httpx.AsyncClient(
                    base_url=self.API_BASE,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=httpx.Timeout(self.timeout),
                )
            except ImportError:
                raise ImportError(
                    "Missing dependency. Run: pip install httpx"
                ) from None

        return self._client

    async def _call_api(self, texts: list[str]) -> list[list[float]]:
        """
        Call OpenAI embeddings API asynchronously.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        # Rate limiting
        self.rate_limiter.acquire()

        client = await self._get_client()

        try:
            # Prepare texts (remove newlines)
            clean_texts = [text.replace("\n", " ") for text in texts]

            # API call
            response = await client.post(
                "/embeddings",
                json={
                    "input": clean_texts,
                    "model": self.model,
                },
            )

            response.raise_for_status()
            data = response.json()

            # Extract embeddings
            embeddings = [item["embedding"] for item in data["data"]]
            return embeddings

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    async def embed_text(self, text: str) -> list[float]:
        """
        Embed a single text asynchronously.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        embeddings = await self._call_api([text])
        return embeddings[0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Batch embed multiple texts asynchronously.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # OpenAI allows up to 2048 texts per request, but we batch smaller
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await self._call_api(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def embed_shards(self, shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Embed shards asynchronously.

        Args:
            shards: List of shard dictionaries with 'text' key

        Returns:
            Shards with 'values' key added
        """
        if not shards:
            return []

        # Extract texts
        texts = [shard["text"] for shard in shards]

        # Batch embed
        embeddings = await self.embed_texts(texts)

        # Add embeddings to shards
        for shard, embedding in zip(shards, embeddings, strict=False):
            shard["values"] = embedding
            shard["model"] = self.model

        return shards

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Context manager entry."""
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup."""
        await self.close()
