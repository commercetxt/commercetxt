"""
Filter helpers for semantic tag generation.
Optimized for performance and dynamic categorization.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from commercetxt.constants import (
    BULKY_THRESHOLD_KG,
    DIMENSION_COUNT_REQUIRED,
    HEAVY_THRESHOLD_KG,
    INCH_TO_CM_CONVERSION,
    LARGE_ITEM_THRESHOLD_CM,
    LB_TO_KG_CONVERSION,
    LIGHTWEIGHT_THRESHOLD_KG,
    MATERIAL_TYPES,
    OVERSIZED_THRESHOLD_CM,
    PRICE_TIERS,
    SEASONAL_KEYWORDS,
    SUSTAINABILITY_CERTS,
)


class PriceFilter:
    """Price-based semantic tagging."""

    @staticmethod
    def get_price_tier(price: Any) -> str | None:
        """Returns price tier tag (budget_friendly, premium, etc.)."""
        try:
            val = float(price)
            if val <= 0:
                return None

            for tier, (min_val, max_val) in PRICE_TIERS.items():
                if min_val <= val < max_val:
                    return tier
        except (ValueError, TypeError):
            pass
        return None


class MaterialFilter:
    """Material classification logic."""

    @staticmethod
    def detect_materials(specs: dict[str, Any]) -> list[str]:
        """
        Detects material types dynamically from specs.
        Maps keywords to general categories and specific material tags.
        """
        tags: list[str] = []
        material_keys = ["material", "materials", "fabric"]

        val = ""
        for k, v in specs.items():
            if k.lower() in material_keys:
                val = str(v).lower()
                break

        if not val:
            return tags

        for category, keywords in MATERIAL_TYPES.items():
            category_matched = False
            for kw in keywords:
                if kw in val:
                    tag_name = "wooden" if kw == "wood" else kw
                    tags.append(tag_name)
                    tags.append(category)
                    category_matched = True

            if category_matched:
                tags.append(f"{category}_material")

        return sorted(list(set(tags)))


class SeasonalityFilter:
    """Seasonal product detection."""

    @staticmethod
    def detect_seasonality(item_name: str) -> list[str]:
        """Detects seasonal tags based on current month and keywords."""
        tags: list[str] = []
        if not item_name:
            return tags

        current_month = datetime.now(timezone.utc).month
        name_lower = item_name.lower()

        for season, config in SEASONAL_KEYWORDS.items():
            if current_month in config["months"]:
                if any(kw in name_lower for kw in config["keywords"]):
                    tags.append(f"{season}_seasonal")

        return tags


class LogisticsFilter:
    """Shipping and logistics classification."""

    @staticmethod
    def classify_weight(specs: dict[str, Any]) -> list[str]:
        """Classifies product by weight for shipping with strict unit handling."""
        tags: list[str] = []
        weight_keys = ["weight", "mass"]

        weight_val = ""
        for k, v in specs.items():
            if k.lower() in weight_keys:
                weight_val = str(v).lower()
                break

        if not weight_val:
            return tags

        try:
            match = re.search(r"(\d+\.?\d*)", weight_val)
            if match:
                num = float(match.group(1))
                weight_kg = LogisticsFilter._to_kg(num, weight_val)

                if weight_kg > HEAVY_THRESHOLD_KG:
                    tags.extend(["heavy_shipping", "freight_required"])
                elif weight_kg > BULKY_THRESHOLD_KG:
                    tags.append("bulky_item")
                elif 0 < weight_kg < LIGHTWEIGHT_THRESHOLD_KG:
                    tags.append("lightweight")
                else:
                    tags.append("standard_shipping")
        except (ValueError, AttributeError):
            pass

        return tags

    @staticmethod
    def _to_kg(num: float, unit_str: str) -> float:
        """Helper to convert various units to kg."""
        if any(u in unit_str for u in ["lb", "pound"]):
            return num * LB_TO_KG_CONVERSION
        if any(u in unit_str for u in ["g", "gram"]) and "kg" not in unit_str:
            return num / 1000
        return num

    @staticmethod
    def classify_dimensions(specs: dict[str, Any]) -> list[str]:
        """Classifies product by dimensions."""
        tags: list[str] = []
        dim_keys = ["dimensions", "size"]

        val = ""
        for k, v in specs.items():
            if k.lower() in dim_keys:
                val = str(v).lower()
                break

        if not val:
            return tags

        matches = re.findall(r"(\d+\.?\d*)", val)
        if len(matches) >= DIMENSION_COUNT_REQUIRED:
            try:
                dims = [float(m) for m in matches[:DIMENSION_COUNT_REQUIRED]]
                max_dim = max(dims)

                if any(u in val for u in ["in", "inch"]):
                    max_dim *= INCH_TO_CM_CONVERSION

                if max_dim > OVERSIZED_THRESHOLD_CM:
                    tags.extend(["oversized_item", "special_handling"])
                elif max_dim > LARGE_ITEM_THRESHOLD_CM:
                    tags.append("large_item")
            except ValueError:
                pass

        return tags


class SustainabilityFilter:
    """Environmental and ethical product attributes."""

    @staticmethod
    def detect_certifications(specs: dict[str, Any]) -> list[str]:
        """Detects sustainability certifications dynamically."""
        tags: list[str] = []
        cert_keys = ["certification", "certified", "compliance"]

        val = ""
        for k, v in specs.items():
            if any(ck in k.lower() for ck in cert_keys):
                val += " " + str(v).lower()

        if not val:
            return tags

        for cert_tag, keywords in SUSTAINABILITY_CERTS.items():
            if any(kw in val for kw in keywords):
                tags.append(f"{cert_tag}_certified")

        return tags
