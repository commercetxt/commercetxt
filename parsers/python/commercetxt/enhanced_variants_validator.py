"""
Enhanced Variants Validator.

Validates @VARIANTS section per Protocol Section 4.10.
"""

import re
from typing import Any

from .constants import MAX_VARIANT_COMBINATIONS, MAX_VARIANT_GROUPS


class EnhancedVariantsValidator:
    """
    Validates @VARIANTS directive with strict Protocol Section 4.10 compliance.

    Key Requirements:
    1. Base price MUST exist in @OFFER before @VARIANTS
    2. All modifiers must be numeric
    3. Final calculated prices must be positive
    4. Multi-dimensional variants should be flattened (if stock varies)
    5. Total combinations < MAX_VARIANT_COMBINATIONS (recommended)
    """

    # Regex for price modifiers (+50.00, -20.00, 348.00)
    MODIFIER_PATTERN = re.compile(r"^([+\-]?)(\d+\.?\d*)$")

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(
        self,
        variants_data: dict[str, Any],
        offer_data: dict[str, Any],
        product_name: str = "Product",
    ) -> bool:
        """
        Main validation entry point.

        Args:
            variants_data: Parsed @VARIANTS section
            offer_data: Parsed @OFFER section
            product_name: Product name for error messages

        Returns:
            bool: True if valid, False otherwise
        """
        # Step 1: Check @OFFER exists
        if not offer_data:
            self._error("@VARIANTS requires @OFFER section to be defined first")
            return False

        # Step 2: Extract base price
        base_price = self._extract_base_price(offer_data)
        if base_price is None:
            self._error(
                "@VARIANTS requires base Price in @OFFER. "
                "Found @OFFER but no Price field."
            )
            return False

        # Step 3: Validate variants structure
        variant_groups = self._parse_variant_groups(variants_data)
        if not variant_groups:
            self._warning("@VARIANTS section is empty")
            return True

        # Step 4: Validate each variant group
        total_combinations = 1
        for group_idx, group in enumerate(variant_groups):
            is_valid = self._validate_variant_group(
                group, base_price, product_name, group_idx
            )
            if not is_valid:
                continue

            # Track combinations
            options_count = len(group.get("options", []))
            total_combinations *= options_count

        # Step 5: Check complexity
        self._check_complexity(total_combinations, len(variant_groups))

        return len(self.errors) == 0

    def _extract_base_price(self, offer_data: dict[str, Any]) -> float | None:
        """
        Extracts base price from @OFFER (case-insensitive).
        """
        for key, value in offer_data.items():
            if key.lower() == "price":
                try:
                    return float(value)
                except (ValueError, TypeError):
                    self._error(f"@OFFER Price '{value}' is not a valid number")
                    return None
        return None

    def _parse_variant_groups(
        self, variants_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Parses variant groups from the variants directive.

        Handles both formats:
        1. Single group: Type: Storage, Options: [...]
        2. Multiple groups: Multiple Type/Options pairs
        """
        groups = []

        # Check if 'items' contains structured data
        items = variants_data.get("items", [])

        # Format 1: Flat structure with Type and Options keys
        if "Type" in variants_data and "Options" in variants_data:
            groups.append(
                {
                    "type": variants_data.get("Type"),
                    "options": variants_data.get("Options", []),
                }
            )

        # Format 2: Items list contains type/options pairs
        # This handles multiple variant dimensions
        current_type = None
        for item in items:
            if isinstance(item, dict):
                # Check if this is a Type declaration
                if "Type" in item or "type" in item:
                    current_type = item.get("Type") or item.get("type")
                    groups.append({"type": current_type, "options": []})
                # Otherwise it's an option
                elif current_type and groups:
                    groups[-1]["options"].append(item)

        return groups

    def _validate_variant_group(
        self,
        group: dict[str, Any],
        base_price: float,
        product_name: str,
        group_idx: int,
    ) -> bool:
        """
        Validates a single variant group.
        """
        variant_type = group.get("type", f"Group {group_idx}")
        options = group.get("options", [])

        if not options:
            self._warning(f"@VARIANTS '{variant_type}': No options defined")
            return False

        # Track option names for duplicates
        seen_names: set[str] = set()

        for opt_idx, option in enumerate(options):
            if not isinstance(option, dict):
                self._warning(
                    f"@VARIANTS '{variant_type}' option {opt_idx}: "
                    f"Expected dict, got {type(option)}"
                )
                continue

            # Extract option name and price
            opt_name = option.get("name") or option.get("value", f"Option {opt_idx}")
            opt_price = option.get("path") or option.get("value")

            # Check for duplicate names
            if opt_name in seen_names:
                self._warning(
                    f"@VARIANTS '{variant_type}': "
                    f"Duplicate option name '{opt_name}'"
                )
            seen_names.add(opt_name)

            # Validate price
            self._validate_option_price(opt_name, opt_price, base_price, variant_type)

        return True

    def _validate_option_price(
        self, option_name: str, price_str: Any, base_price: float, variant_type: str
    ) -> None:
        """
        Validates individual option price with modifier support.

        # Supports both:
        # 1. Absolute: "999.00" (final price)
        # 2. Modifiers: "+50.00" or "-20.00" (relative to base)
        """
        if price_str is None:
            # No price specified - use base price
            return

        price_str = str(price_str).strip()

        # Parse price/modifier
        match = self.MODIFIER_PATTERN.match(price_str)
        if not match:
            self._error(
                f"@VARIANTS '{variant_type}' option '{option_name}': "
                f"Invalid price format '{price_str}'. "
                f"Expected: 999.00, +50.00, or -20.00"
            )
            return

        sign, amount_str = match.groups()

        try:
            amount = float(amount_str)
        except ValueError:
            self._error(
                f"@VARIANTS '{variant_type}' option '{option_name}': "
                f"Cannot parse amount '{amount_str}' as number"
            )
            return

        # Calculate final price
        if sign in ("+", "-"):
            # It's a modifier
            final_price = base_price + (amount if sign == "+" else -amount)

            # Validate final price is positive
            if final_price < 0:
                self._error(
                    f"@VARIANTS '{variant_type}' option '{option_name}': "
                    f"Modifier {sign}{amount} yields negative price "
                    f"({base_price} {sign} {amount} = {final_price}). "
                    f"Variant prices must be positive."
                )
            elif final_price == 0:
                self._warning(
                    f"@VARIANTS '{variant_type}' option '{option_name}': "
                    f"Final price is $0.00 - is this intentional?"
                )
        # It's an absolute price
        elif amount < 0:
            self._error(
                f"@VARIANTS '{variant_type}' option '{option_name}': "
                f"Absolute price cannot be negative ({amount})"
            )
        elif amount == 0:
            self._warning(
                f"@VARIANTS '{variant_type}' option '{option_name}': "
                f"Price is $0.00 - is this intentional?"
            )

    def _check_complexity(self, total_combinations: int, group_count: int) -> None:
        """
        Checks variant complexity and recommends flattening if needed.

        Protocol Section 4.10:
        - Use @VARIANTS when: Total combinations < MAX_VARIANT_COMBINATIONS
        - Use separate files when: Total combinations > MAX_VARIANT_COMBINATIONS
        """
        if total_combinations > MAX_VARIANT_COMBINATIONS:
            self._warning(
                f"@VARIANTS has {total_combinations} total combinations "
                f"({group_count} variant dimensions). "
                f"Protocol recommends separate product files when "
                f"> {MAX_VARIANT_COMBINATIONS} combinations."
            )

        if group_count > MAX_VARIANT_GROUPS:
            self._warning(
                f"@VARIANTS has {group_count} variant dimensions. "
                f"Consider using flattened approach (explicit combinations) "
                f"if stock levels vary per combination. "
                f"See Protocol Section 4.10 'Multi-Dimensional Variants'."
            )

    def _error(self, message: str) -> None:
        """Records an error."""
        self.errors.append(message)
        if self.strict:
            raise ValueError(message)

    def _warning(self, message: str) -> None:
        """Records a warning."""
        self.warnings.append(message)

    def get_report(self) -> dict[str, Any]:
        """Returns validation report."""
        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }
