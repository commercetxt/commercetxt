"""
Semantic Normalizer.

Converts physical units to standard SI for consistent AI comparison.
"""

from __future__ import annotations

import re
from typing import Any

from .units_registry import DISTANCE_UNITS, VOLUME_UNITS, WEIGHT_UNITS


class SemanticNormalizer:
    """
    Normalizes physical units in product specifications to standard SI units.
    Helps AI agents compare products with different measurement systems.
    """

    def __init__(self, target_weight="kg", target_distance="m", target_volume="l"):
        self.target_units = {
            "weight": target_weight,
            "distance": target_distance,
            "volume": target_volume,
        }
        # Combine all registries for fast lookup
        self.registry = {**DISTANCE_UNITS, **WEIGHT_UNITS, **VOLUME_UNITS}

        # Pre-sort units by length (descending) to match multi-word units first
        # This avoids O(n log n) sorting on every normalize_value() call
        self._sorted_units = sorted(self.registry.keys(), key=len, reverse=True)

    def normalize_value(self, text: str) -> str:
        """
        Detects units in a string and converts them to base units.
        Example: '1500 g' -> '1.5 kg'
        Supports: special chars (", '), multi-word units (uk pint), and mixed (m3)
        """
        if not text:
            return text

        text = str(text).strip()

        # Use pre-sorted units (sorted by length descending in __init__)
        # This ensures multi-word units like "uk pint" match before "pint"
        for unit_key in self._sorted_units:
            # Build pattern that matches: number + optional space + unit
            # Use re.escape to handle special chars like " and '
            escaped_unit = re.escape(unit_key)
            pattern = rf"(\d+\.?\d*)\s*({escaped_unit})(?:\s|$)"

            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value_str = match.group(1)
                matched_unit = match.group(2).lower()

                # Find the actual unit key (case-insensitive)
                actual_unit = None
                for key in self.registry:
                    if key.lower() == matched_unit:
                        actual_unit = key
                        break

                if actual_unit:
                    # Conversion logic
                    factor = self.registry[actual_unit]
                    normalized_val = float(value_str) * factor

                    # Identify unit type for the label
                    val_str = f"{normalized_val:.3f}".rstrip("0").rstrip(".")
                    if actual_unit in WEIGHT_UNITS:
                        return f"{val_str} kg"
                    if actual_unit in DISTANCE_UNITS:
                        return f"{val_str} m"
                    if actual_unit in VOLUME_UNITS:
                        return f"{val_str} l"

        return text

    def normalize_specs(self, specs: dict[str, Any]) -> dict[str, Any]:
        """Iterates through specs and normalizes all measurable values."""
        normalized_specs = {}
        for key, value in specs.items():
            if isinstance(value, str):
                normalized_specs[key] = self.normalize_value(value)
            else:
                normalized_specs[key] = value
        return normalized_specs
