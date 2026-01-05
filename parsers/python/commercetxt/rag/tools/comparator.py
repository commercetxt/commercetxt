"""
Intelligent product comparison with semantic understanding.
Provides structured insights and recommendations.
"""

import re
from typing import Any, ClassVar

from commercetxt.rag.tools.normalizer import SemanticNormalizer


class ProductComparator:
    """
    Intelligent product comparison with semantic understanding.
    """

    # Constants for advantage detection - Annotated for RUF012
    BETTER_HIGHER: ClassVar[list[str]] = [
        "battery",
        "ram",
        "storage",
        "screen",
        "camera",
        "megapixel",
        "resolution",
    ]
    BETTER_LOWER: ClassVar[list[str]] = ["weight", "price", "latency", "thickness"]

    # Pre-compiled regex for performance
    RE_NUMERIC: ClassVar[re.Pattern] = re.compile(r"(\d+\.?\d*)")

    def __init__(self) -> None:
        self.normalizer = SemanticNormalizer()

    def compare(
        self, product_a: dict[str, Any], product_b: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Generates structured comparison highlighting key differences.
        """
        spec_diffs: list[dict[str, Any]] = []

        comparison: dict[str, Any] = {
            "winner": None,
            "price_advantage": None,
            "savings": None,
            "spec_differences": spec_diffs,
            "unique_features": {"a": [], "b": []},
            "recommendation": "",
        }

        # Price comparison
        price_a = float(product_a.get("PRICE", 0))
        price_b = float(product_b.get("PRICE", 0))

        if price_a < price_b:
            comparison["price_advantage"] = "a"
            comparison["savings"] = f"${price_b - price_a:.2f} cheaper"
        elif price_b < price_a:
            comparison["price_advantage"] = "b"
            comparison["savings"] = f"${price_a - price_b:.2f} cheaper"

        # Spec comparison
        specs_a = product_a.get("SPECS", {})
        specs_b = product_b.get("SPECS", {})

        all_keys = set(specs_a.keys()) | set(specs_b.keys())

        for key in all_keys:
            raw_a = str(specs_a.get(key, "N/A"))
            raw_b = str(specs_b.get(key, "N/A"))

            val_a = self.normalizer.normalize_value(raw_a)
            val_b = self.normalizer.normalize_value(raw_b)

            if val_a != val_b:
                advantage = self._determine_advantage(key, val_a, val_b)
                spec_diffs.append(
                    {
                        "attribute": key,
                        "product_a": val_a,
                        "product_b": val_b,
                        "advantage": advantage,
                    }
                )

        # Generate recommendation
        comparison["recommendation"] = self._generate_recommendation(comparison)

        return comparison

    def _determine_advantage(self, attribute: str, val_a: str, val_b: str) -> str:
        """Smart advantage detection (higher battery = better, etc.)"""
        if "N/A" in (val_a, val_b):
            return "b" if val_a == "N/A" else "a"

        try:
            num_a = self.RE_NUMERIC.search(val_a)
            num_b = self.RE_NUMERIC.search(val_b)
            if not (num_a and num_b):
                return "neutral"

            a = float(num_a.group(1))
            b = float(num_b.group(1))
            if a == b:
                return "neutral"

            attr_lower = attribute.lower()
            if any(kw in attr_lower for kw in self.BETTER_HIGHER):
                return "a" if a > b else "b"
            if any(kw in attr_lower for kw in self.BETTER_LOWER):
                return "a" if a < b else "b"

        except (ValueError, IndexError):
            pass

        return "neutral"

    def _generate_recommendation(self, comparison: dict[str, Any]) -> str:
        """Simple heuristic-based recommendation."""
        price_adv = comparison.get("price_advantage")
        if price_adv == "a":
            return "Product A offers better value for money."
        if price_adv == "b":
            return "Product B is the premium choice."
        return "Both products are competitive."
