"""
Realtime Enricher.

Merges vector search results with live price and stock data.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..interfaces.base_storage import BaseRealtimeStorage


class RealtimeEnricher:
    """
    Merges semantic search results with real-time data (Price, Stock).
    Implements a "Vector-Metadata Join" pattern.

    Expected input shape for each result (minimum):
      {
        "id": "<vector_point_id>",
        "metadata": {
            "product_id": "<canonical_product_id>",   # strongly recommended
            ...
        },
        ...
      }

    Behavior:
    - Uses metadata[product_id_key] as the lookup key by default.
    - Falls back to result["id"] if product_id is missing (backwards compatible),
      but this will be unreliable unless vector IDs are deterministic per product.
    """

    def __init__(
        self,
        storage: BaseRealtimeStorage,
        product_id_key: str = "product_id",
        output_prefix: str = "live_",
    ):
        self.storage = storage
        self.product_id_key = product_id_key
        self.output_prefix = output_prefix

    def enrich(
        self,
        search_results: list[dict[str, Any]],
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Injects live price/stock/currency into vector search results.

        Args:
            search_results: List of vector search results.
            fields: Which realtime fields to fetch.
                    Defaults to ["price", "availability", "currency"].

        Returns:
            The same list, with metadata enriched in-place.
        """
        if not search_results:
            return []

        default_fields = ["price", "availability", "currency"]
        fields = list(fields) if fields is not None else default_fields

        # Extract lookup keys in the same order as results
        lookup_keys, key_map = self._extract_lookup_keys(search_results)

        if not lookup_keys:
            return search_results

        # Batch fetch realtime data
        live_data = self.storage.get_live_attributes(lookup_keys, fields=fields) or {}

        # Merge
        for res, key in key_map:
            info = live_data.get(key)
            if not info:
                continue

            meta = res.get("metadata")
            if meta is None or not isinstance(meta, dict):
                meta = {}
                res["metadata"] = meta

            # Conventional fields (kept compatible with your current names)
            if "price" in fields:
                meta[f"{self.output_prefix}price"] = info.get("price")
            if "availability" in fields:
                meta[f"{self.output_prefix}stock"] = info.get("availability")
            if "currency" in fields:
                meta[f"{self.output_prefix}currency"] = info.get("currency")

            # If user requests extra fields beyond the defaults, include them too:
            extra_fields = set(fields) - {"price", "availability", "currency"}
            for f in extra_fields:
                meta[f"{self.output_prefix}{f}"] = info.get(f)

        return search_results

    def _extract_lookup_keys(
        self, search_results: list[dict[str, Any]]
    ) -> tuple[list[str], list[tuple[dict[str, Any], str]]]:
        """
        Returns:
          - unique lookup keys (preserving first-seen order)
          - mapping list of (result, lookup_key) preserving result order
        """
        seen = set()
        unique_keys: list[str] = []
        mapping: list[tuple[dict[str, Any], str]] = []

        for res in search_results:
            meta = res.get("metadata") if isinstance(res, dict) else None
            key = None

            if isinstance(meta, dict):
                key = meta.get(self.product_id_key)

            # Backwards-compat fallback (works only if result["id"] is product-stable)
            if not key:
                key = res.get("id") if isinstance(res, dict) else None

            if not key or not isinstance(key, str):
                # Skip results we cannot enrich
                continue

            mapping.append((res, key))

            if key not in seen:
                seen.add(key)
                unique_keys.append(key)

        return unique_keys, mapping
