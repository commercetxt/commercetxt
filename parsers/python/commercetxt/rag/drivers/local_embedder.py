"""
Local Embedder using sentence-transformers.

Generates embeddings locally on CPU/GPU without API calls.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..interfaces.base_embedder import BaseEmbedder

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

try:
    from sentence_transformers import SentenceTransformer

    HAS_SENTENCE_TRANSFORMERS = True
    SentenceTransformerClass: Any = SentenceTransformer
except ImportError:
    SentenceTransformerClass = None
    HAS_SENTENCE_TRANSFORMERS = False

logger = logging.getLogger(__name__)


class LocalEmbedder(BaseEmbedder):
    """Embeds text using sentence-transformers locally. No API. Fast. Reliable."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Load the transformer model. Log status. Raise if missing."""
        if not HAS_SENTENCE_TRANSFORMERS:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        logger.info(f"Loading local embedder model: {model_name}")
        self.model = SentenceTransformerClass(model_name)
        self.model_name = model_name
        logger.info(f"Successfully loaded model: {model_name}")

    def embed_text(self, text: str) -> list[float]:
        """Return embedding for a single text as a list of floats."""
        result = self.model.encode(text)
        return list(result.tolist())

    def embed_shards(self, shards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Embed many texts. Add embeddings and model name to each shard."""
        if not shards:
            return []
        texts = [s["text"] for s in shards]
        embeddings = self.model.encode(texts)
        for i, vec in enumerate(embeddings):
            shards[i]["values"] = vec.tolist()
            shards[i]["model"] = self.model_name
        return shards
