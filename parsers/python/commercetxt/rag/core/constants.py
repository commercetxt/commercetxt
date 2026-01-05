"""
RAG-specific constants.

NOTE: Most constants moved to commercetxt/constants.py (single source of truth).
This file now only contains RAG-unique constants.
"""

from commercetxt.constants import (
    CATEGORY_KEYWORDS,
    DEFAULT_PLURAL_ATTRIBUTES,
    MATERIAL_TYPES,
    MAX_LIST_ITEMS,
    MAX_SHARDS,
    MAX_TEXT_LENGTH,
    PRICE_TIERS,
    SEASONAL_KEYWORDS,
    SUSTAINABILITY_CERTS,
)

# Known CommerceTXT top-level sections (for schema bridge filtering)
KNOWN_SECTIONS = frozenset(
    {
        "PRODUCT",
        "OFFER",
        "INVENTORY",
        "REVIEWS",
        "IMAGES",
        "SPECS",
        "IDENTITY",
        "METADATA",
    }
)

# Generator constants
MIN_VARIANT_GROUP_PARTS = 2  # Minimum parts needed to extract variant attributes

__all__ = [
    "CATEGORY_KEYWORDS",
    "DEFAULT_PLURAL_ATTRIBUTES",
    "KNOWN_SECTIONS",
    "MATERIAL_TYPES",
    "MAX_LIST_ITEMS",
    "MAX_SHARDS",
    "MAX_TEXT_LENGTH",
    "PRICE_TIERS",
    "SEASONAL_KEYWORDS",
    "SUSTAINABILITY_CERTS",
]
