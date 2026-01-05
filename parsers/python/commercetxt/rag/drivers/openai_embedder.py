"""
OpenAI Embedder.

Generates embeddings via OpenAI API for high-quality semantic search.
"""

from __future__ import annotations

import os
from typing import Any

from ..core.rate_limiter import RateLimiter
from ..interfaces.base_embedder import BaseEmbedder

try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    OpenAI = None  # type: ignore[assignment, misc]
    HAS_OPENAI = False


class OpenAIEmbedder(BaseEmbedder):
    """
    Uses OpenAI API for high-quality embeddings.

    Includes automatic rate limiting to prevent API throttling.
    Default: 3 requests/second (conservative for tier 1).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        requests_per_second: float = 3.0,
    ):
        """
        Initialize OpenAI embedder.

        Args:
            api_key: OpenAI API key (falls back to OPENAI_API_KEY env var)
            model: Model name (default: text-embedding-3-small)
            requests_per_second: Rate limit for API calls (default: 3.0)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.rate_limiter = RateLimiter(calls_per_second=requests_per_second)

        if not HAS_OPENAI:
            raise ImportError("OpenAI not installed. Install with: pip install openai")

        self.client = OpenAI(api_key=self.api_key)

    def embed_text(self, text: str) -> list[float]:
        """Embed single text with rate limiting."""
        self.rate_limiter.acquire()
        text = text.replace("\n", " ")
        result = self.client.embeddings.create(input=[text], model=self.model)
        return list(result.data[0].embedding)

    def embed_shards(self, shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Embed multiple shards with rate limiting."""
        if not shards:
            return []

        self.rate_limiter.acquire()
        texts = [s["text"].replace("\n", " ") for s in shards]
        response = self.client.embeddings.create(input=texts, model=self.model)

        for i, item in enumerate(response.data):
            shards[i]["values"] = list(item.embedding)
            shards[i]["model"] = self.model

        return shards
