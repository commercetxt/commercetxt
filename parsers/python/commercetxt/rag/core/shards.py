"""
RAG shard creation and formatting.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .constants import MAX_TEXT_LENGTH


class ShardBuilder:
    """Builds RAG shards from product data."""

    def __init__(
        self,
        include_metadata: bool = True,
        include_confidence: bool = True,
        include_negative_tags: bool = True,
    ):
        self.include_metadata = include_metadata
        self.include_confidence = include_confidence
        self.include_negative_tags = include_negative_tags

    def create_shard(
        self,
        text: str,
        original_data: dict[str, Any],
        attr_type: str,
        index: int,
        semantic_tags: list[str],
    ) -> dict[str, Any]:
        """Creates a single RAG shard."""
        shard: dict[str, Any] = {"text": text}

        if self.include_metadata:
            final_tags: list[str] | list[dict[str, Any]] = semantic_tags

            # Add confidence and negative tags if enabled
            if self.include_confidence or self.include_negative_tags:
                final_tags = self._add_confidence_scores(semantic_tags)

            shard["metadata"] = {
                "index": index,
                "attr_type": attr_type,
                "original_data": original_data,
                "semantic_tags": final_tags,
            }

        return shard

    def _add_confidence_scores(self, tags: list[str]) -> list[dict[str, Any]]:
        """
        Adds confidence scores and negative tags with deduplication.

        Deduplicates during generation for better performance.
        """
        seen = set()
        result: list[dict[str, Any]] = []

        for tag in tags:
            tag_lower = str(tag).lower()

            # Positive tag (deduplicate inline)
            if tag_lower not in seen:
                result.append({"tag": tag_lower, "score": 1.0, "type": "positive"})
                seen.add(tag_lower)

            # Negative tag (deduplicate inline)
            if self.include_negative_tags:
                neg_tag = f"not_{tag_lower}"
                if neg_tag not in seen:
                    result.append({"tag": neg_tag, "score": 0.5, "type": "negative"})
                    seen.add(neg_tag)

        return result

    @staticmethod
    def truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
        """Truncates text to max length."""
        if len(text) > max_length:
            return text[: max_length - 3] + "..."
        return text

    @staticmethod
    def compute_content_hash(shard: dict[str, Any]) -> str:
        """
        Compute a stable hash of shard content for deduplication.

        Uses text and attr_type to identify duplicate content.
        Excludes index and original_data from hash to catch semantic duplicates.
        """
        # Extract core content that defines uniqueness
        text = shard.get("text", "")
        metadata = shard.get("metadata", {})
        attr_type = metadata.get("attr_type", "")

        # Create stable hash input
        hash_input = {
            "text": text,
            "attr_type": attr_type,
        }

        # Convert to stable JSON string and hash
        json_str = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(json_str.encode("utf-8")).hexdigest()
