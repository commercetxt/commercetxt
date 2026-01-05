"""
Semantic tagging orchestration.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .constants import CATEGORY_KEYWORDS
from .filters import (
    LogisticsFilter,
    MaterialFilter,
    PriceFilter,
    SeasonalityFilter,
    SustainabilityFilter,
)


class SemanticTagger:
    """Orchestrates different filters to generate semantic tags for product data."""

    def generate_tags(self, data: dict[str, Any]) -> list[str]:
        """Runs all filters and aggregates tags."""
        tags = []
        specs = data.get("SPECS", {})
        item_name = data.get("ITEM", "")

        # 1. Price
        price_tag = PriceFilter.get_price_tier(data.get("PRICE"))
        if price_tag:
            tags.append(price_tag)

        # 2. Materials
        tags.extend(MaterialFilter.detect_materials(specs))

        # 3. Seasonality
        tags.extend(SeasonalityFilter.detect_seasonality(item_name))

        # 4. Logistics
        tags.extend(LogisticsFilter.classify_weight(specs))
        tags.extend(LogisticsFilter.classify_dimensions(specs))

        # 5. Sustainability
        tags.extend(SustainabilityFilter.detect_certifications(specs))

        # 6. Availability & Condition
        tags.extend(self._get_availability_tags(data))

        # 7. Category detection
        tags.extend(self._get_category_tags(data))

        # 8. Brand recognition
        brand = data.get("BRAND", "")
        if brand:
            brand_str = str(brand).strip().lower()
            if brand_str:
                # Generate safe brand slug with hash suffix for uniqueness
                safe_brand = re.sub(r"[^\w]", "_", brand_str)

                # Compute short hash from original brand for uniqueness
                brand_hash = hashlib.sha256(brand_str.encode("utf-8")).hexdigest()[:6]

                # Truncate slug to leave room for hash suffix (e.g., brand_apple_a1b2c3)
                max_slug_length = 93  # 100 - 1 (underscore) - 6 (hash) = 93
                safe_brand = safe_brand[:max_slug_length]

                # Combine slug with hash suffix
                brand_tag = f"brand_{safe_brand}_{brand_hash}"
                tags.append(brand_tag)

        return list(set(tags))  # Deduplicate

    def _get_availability_tags(self, data: dict[str, Any]) -> list[str]:
        """Availability-based tags."""
        tags = []
        availability = str(data.get("AVAILABILITY", "")).strip()

        if availability == "InStock":
            tags.append("ready_to_ship")
        elif availability in ["OutOfStock", "Discontinued"]:
            tags.append("unavailable")
        elif availability == "PreOrder":
            tags.append("preorder_available")

        # Condition
        condition = str(data.get("CONDITION", "")).strip()
        if condition == "New":
            tags.append("brand_new_condition")
        elif condition == "Refurbished":
            tags.append("refurbished")
        elif condition == "Used":
            tags.append("pre_owned")

        return tags

    def _get_category_tags(self, data: dict[str, Any]) -> list[str]:
        """Category detection from item name."""
        tags = []
        item_name = str(data.get("ITEM", "")).lower()

        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(kw in item_name for kw in keywords):
                tags.append(category)

        return tags
