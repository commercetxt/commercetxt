"""
AI Health Checker for CommerceTXT.
Evaluates how 'AI-ready' and token-efficient a product file is.
"""

from __future__ import annotations

from typing import Any

from ...constants import (
    HEALTH_EXCELLENT_LIMIT,
    HEALTH_FAIR_LIMIT,
    HEALTH_GOOD_LIMIT,
    MAX_DESCRIPTION_LENGTH,
    MIN_TECHNICAL_SPECS,
)


class AIHealthChecker:
    """Analyzes product data for semantic completeness and token efficiency."""

    def assess(self, data: dict[str, Any]) -> dict[str, Any]:
        """Assess the AI readiness of the given product data."""
        flat_data = self._flatten_and_normalize(data)
        score = 100
        suggestions: list[str] = []
        metrics: dict[str, int] = {}

        # Run checks
        score = self._check_critical_fields(flat_data, score, suggestions)
        score = self._check_specs(flat_data, score, suggestions, metrics)
        score = self._check_content_quality(flat_data, score, suggestions, metrics)

        # Final Status Calculation
        if score >= HEALTH_EXCELLENT_LIMIT:
            status = "EXCELLENT"
        elif score >= HEALTH_GOOD_LIMIT:
            status = "GOOD"
        elif score >= HEALTH_FAIR_LIMIT:
            status = "NEEDS WORK"
        else:
            status = "UNUSABLE"

        return {
            "score": max(0, score),
            "status": status,
            "metrics": metrics,
            "suggestions": suggestions,
        }

    def _flatten_and_normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Flattens nested dicts and uppercases keys."""
        flat_data = {}
        for key, value in data.items():
            if isinstance(value, dict):
                flat_data.update(value)
                flat_data[key] = value
            else:
                flat_data[key] = value
        return {k.upper(): v for k, v in flat_data.items()}

    def _check_critical_fields(self, data: dict, score: int, suggestions: list) -> int:
        """Checks for presence of mandatory commercial fields."""
        critical_map = {
            "ITEM": ["NAME", "ITEM", "PRODUCT_NAME"],
            "BRAND": ["BRAND"],
            "PRICE": ["PRICE"],
            "CURRENCY": ["CURRENCY"],
            "AVAILABILITY": ["AVAILABILITY", "STOCK_STATUS"],
        }

        missing = [
            canonical
            for canonical, aliases in critical_map.items()
            if not any(alias in data for alias in aliases)
        ]

        if missing:
            score -= len(missing) * 15
            suggestions.append(f"CRITICAL: Missing core commercial fields {missing}.")

        return score

    def _check_specs(
        self, data: dict, score: int, suggestions: list, metrics: dict
    ) -> int:
        """Evaluates technical specifications."""
        specs = data.get("SPECS", {})
        count = len(specs) if isinstance(specs, dict) else 0
        metrics["specs_count"] = count

        if count == 0:
            score -= 30
            suggestions.append(
                "POOR: No @SPECS block found. AI cannot answer technical questions."
            )
        elif count < MIN_TECHNICAL_SPECS:
            score -= 10
            suggestions.append(
                "WEAK: Few technical specs. Consider adding Display, Battery, "
                "and Processor info."
            )

        return score

    def _check_content_quality(
        self, data: dict, score: int, suggestions: list, metrics: dict
    ) -> int:
        """Checks description length and semantic logic."""
        # Check Logic
        if not data.get("SEMANTIC_LOGIC"):
            score -= 10
            suggestions.append(
                "ADVICE: Missing @SEMANTIC_LOGIC. "
                "Adding AI reasoning rules helps handle FAQ better."
            )

        # Check Description
        desc = str(data.get("DESCRIPTION", ""))
        metrics["description_length"] = len(desc)

        if len(desc) > MAX_DESCRIPTION_LENGTH:
            score -= 5
            suggestions.append(
                "TOKEN-WARNING: Long description. "
                "Ensure it doesn't repeat @SPECS to save tokens."
            )

        # Check Buzzwords
        buzzwords = ["best in the world", "unbelievable", "amazing", "click here"]
        found = [w for w in buzzwords if w in desc.lower()]
        if found:
            score -= 5
            suggestions.append(
                f"NOISE: Found marketing buzzwords {found}. Keep it factual for AI."
            )

        return score
