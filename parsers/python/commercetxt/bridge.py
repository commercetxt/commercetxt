"""
Bridge between CommerceTXT and Large Language Models.
Optimized for low token usage and high reliability.
"""

from typing import Any

from .constants import (
    DEFAULT_AVAILABILITY,
    DEFAULT_CURRENCY,
    DEFAULT_ITEM_NAME,
    DEFAULT_PRICE,
    DEFAULT_STORE_NAME,
    GRADE_A_THRESHOLD,
    GRADE_B_THRESHOLD,
    MAX_SHIPPING_METHODS_DISPLAY,
    MAX_SPECS_DISPLAY,
    MAX_VARIANT_OPTIONS_DISPLAY,
    PENALTY_MISSING_OFFER,
    PENALTY_MISSING_VERSION,
    PENALTY_PER_ERROR,
    PENALTY_STALE_INVENTORY,
)
from .metrics import get_metrics
from .model import ParseResult


class CommerceAIBridge:
    """
    Connects parsed data to AI systems.

    Important: For accurate AI readiness scoring, run CommerceTXTValidator
    BEFORE creating the bridge. The validator populates trust_flags
    (e.g., 'inventory_stale') which are used by calculate_readiness_score().

    Example:
        # Correct usage:
        parser = CommerceTXTParser()
        result = parser.parse(content)

        validator = CommerceTXTValidator()
        validator.validate(result)  # Populates trust_flags

        bridge = CommerceAIBridge(result)
        score = bridge.calculate_readiness_score()  # Uses trust_flags
    """

    def __init__(self, result: ParseResult):
        self.result = result
        self.metrics = get_metrics()

    def generate_low_token_prompt(self) -> str:
        """Create a clean, dense text prompt for LLMs."""
        d = self.result.directives
        lines: list[str] = []

        self._add_identity(lines, d.get("IDENTITY", {}))
        self._add_product(lines, d.get("PRODUCT", {}))
        self._add_offer(lines, d.get("OFFER", {}))
        self._add_inventory(lines, d.get("INVENTORY", {}))
        self._add_reviews(lines, d.get("REVIEWS", {}))
        self._add_specs(lines, d.get("SPECS", {}))
        self._add_variants(lines, d.get("VARIANTS", {}))
        self._add_shipping(lines, d.get("SHIPPING", {}))
        self._add_extras(lines, d)  # Promos, Compatibility, Images, etc.
        self._add_ai_guidance(lines, d)

        return "\n".join(lines)

    def _add_identity(self, lines: list[str], data: dict[str, Any]) -> None:
        """Add store/identity information to prompt."""
        if not data:
            return

        name = data.get("Name", DEFAULT_STORE_NAME)
        currency = data.get("Currency", DEFAULT_CURRENCY)

        lines.append(f"STORE: {name}")
        lines.append(f"CURRENCY: {currency}")

    def _add_product(self, lines: list[str], data: dict[str, Any]) -> None:
        """Add product information to prompt."""
        if not data:
            return

        # Always add name with explicit default
        name = data.get("Name", DEFAULT_ITEM_NAME)
        lines.append(f"ITEM: {name}")

        # Optional fields - explicit None checks
        sku = data.get("SKU")
        if sku is not None and sku != "":
            lines.append(f"SKU: {sku}")

        brand = data.get("Brand")
        if brand is not None and brand != "":
            lines.append(f"BRAND: {brand}")

        url = data.get("URL")
        if url is not None and url != "":
            lines.append(f"URL: {url}")

    def _add_offer(self, lines: list[str], data: dict[str, Any]) -> None:
        """Add offer/pricing information to prompt."""
        if not data:
            return

        # Always add price and availability with explicit defaults
        price = data.get("Price", DEFAULT_PRICE)
        availability = data.get("Availability", DEFAULT_AVAILABILITY)

        lines.append(f"PRICE: {price}")
        lines.append(f"AVAILABILITY: {availability}")

        # Optional fields - explicit None checks
        condition = data.get("Condition")
        if condition is not None and condition != "":
            lines.append(f"CONDITION: {condition}")

        url = data.get("URL")
        if url is not None and url != "":
            lines.append(f"URL: {url}")

    def _add_inventory(self, lines: list[str], data: dict[str, Any]) -> None:
        """Add inventory information to prompt."""
        if not data:
            return

        stock = data.get("Stock")
        # Explicit type and value checks - allows stock=0 but rejects negative
        if stock is not None and isinstance(stock, (int, float, str)):
            # Convert to numeric for validation
            try:
                stock_value = float(stock) if isinstance(stock, str) else stock
                # Only show non-negative stock (>= 0 allows zero)
                if stock_value >= 0:
                    lines.append(f"STOCK: {stock} units")
            except (ValueError, TypeError):
                # Invalid stock value (e.g., "abc"), skip it
                pass

        last_updated = data.get("LastUpdated")
        if last_updated is not None and last_updated != "":
            lines.append(f"STOCK_UPDATED: {last_updated}")

        # Trust flags check (moved outside the data check for clarity)
        if "inventory_stale" in self.result.trust_flags:
            lines.append("NOTE: Inventory data may be outdated")

    def _add_reviews(self, lines: list[str], data: dict[str, Any]) -> None:
        """Add review information to prompt."""
        if not data:
            return

        rating = data.get("Rating")
        count = data.get("Count")

        # Both must be present and non-empty
        if rating is not None and rating != "" and count is not None and count != "":
            lines.append(f"RATING: {rating}/5 ({count} reviews)")

        top_tags = data.get("TopTags")
        if top_tags is not None and top_tags != "":
            lines.append(f"TAGS: {top_tags}")

    def _add_specs(self, lines: list[str], data: dict[str, Any]) -> None:
        """Add specification information to prompt."""
        if not data:
            return

        lines.append("SPECS:")

        # Explicitly limit to MAX_SPECS_DISPLAY
        count = 0
        for key, value in data.items():
            if key != "items":  # Skip metadata
                lines.append(f"  {key}: {value}")
                count += 1
                if count >= MAX_SPECS_DISPLAY:
                    break

    def _add_variants(self, lines: list[str], data: dict[str, Any]) -> None:
        """Add variant information to prompt."""
        if not data:
            return

        options = data.get("Options")

        # Explicit checks for list type and non-empty
        if not isinstance(options, list):
            return

        if len(options) == 0:
            return

        variant_type = data.get("Type", "Options")

        # Extract names safely, filtering out non-dict items
        names = [
            opt.get("name") or opt.get("value")
            for opt in options[:MAX_VARIANT_OPTIONS_DISPLAY]
            if isinstance(opt, dict)
        ]

        if names:
            # Filter out None values for type safety
            valid_names = [str(n) for n in names if n is not None]
            if valid_names:
                lines.append(f"{variant_type.upper()}: {', '.join(valid_names)}")

            remaining = len(options) - MAX_VARIANT_OPTIONS_DISPLAY
            if remaining > 0:
                lines.append(f"  (+{remaining} more)")

    def _add_shipping(self, lines: list[str], data: dict[str, Any]) -> None:
        """Add shipping information to prompt."""
        if not data:
            return

        items = data.get("items")
        if not isinstance(items, list) or len(items) == 0:
            return

        lines.append("SHIPPING:")
        for item in items[:MAX_SHIPPING_METHODS_DISPLAY]:
            if isinstance(item, dict):
                name = item.get("name", "")
                path = item.get("path", "")
                lines.append(f"  {name}: {path}")

    def _add_extras(self, lines: list[str], d: dict[str, Any]) -> None:
        """Handles Promos, Compatibility, Images, Age."""
        # Promos
        promos = d.get("PROMOS", {}).get("items", [])
        if promos:
            lines.append("PROMOS:")
            for p in promos:
                lines.append(f"  - {p.get('name', 'Promo')}: {p.get('value', '')}")

        # Compatibility
        comp = d.get("COMPATIBILITY", {})
        if comp:
            lines.append("COMPATIBILITY:")
            for k, v in comp.items():
                if k != "items":
                    lines.append(f"  {k}: {v}")

        # Images
        images = d.get("IMAGES", {}).get("items", [])
        if images:
            lines.append("VISUALS:")
            for img in images:
                name = img.get("name", "Image")
                alt = img.get("Alt", "").strip('"')
                desc = f"Describes {alt}" if alt else f"Available at {img.get('path')}"
                lines.append(f"  - {name}: {desc}")

        # Age
        age = d.get("AGE_RESTRICTION", {})
        if age.get("MinimumAge"):
            lines.append(f"SAFETY: Restricted to ages {age['MinimumAge']}+")

    def _add_ai_guidance(self, lines: list[str], d: dict[str, Any]) -> None:
        logic = d.get("SEMANTIC_LOGIC", {}).get("items", [])
        if logic:
            lines.append("AI_LOGIC_RULES:")
            for rule in logic:
                if isinstance(rule, dict) and rule.get("name") and rule.get("path"):
                    lines.append(f"  - {rule['name']} -> {rule['path']}")
                else:
                    val = rule.get("value") if isinstance(rule, dict) else rule
                    lines.append(f"  - {val}")

        voice = d.get("BRAND_VOICE", {})
        if voice:
            lines.append(f"TONE_OF_VOICE: {voice.get('Tone', 'Neutral')}")
            if voice.get("Guidelines"):
                lines.append(f"VOICE_GUIDELINES: {voice['Guidelines']}")

    def calculate_readiness_score(self) -> dict:
        """
        Calculate AI readiness score based on completeness and freshness.
        Note: This validates internal consistency only. For full Trust Score
        compliance (Section 9.1.1), external verification against HTML and
        Schema.org markup is required (not implemented in this validator).
        """

        score = 100
        reasons = []

        if not self.result.version:
            score -= PENALTY_MISSING_VERSION
            reasons.append("Missing version directive")

        offer = self.result.directives.get("OFFER", {})
        if not offer.get("Price") or not offer.get("Availability"):
            score -= PENALTY_MISSING_OFFER
            reasons.append("Missing core offer data (Price/Availability)")

        if self.result.errors:
            score -= len(self.result.errors) * PENALTY_PER_ERROR

        if "inventory_stale" in self.result.trust_flags:
            score -= PENALTY_STALE_INVENTORY
            reasons.append("Stale inventory reduces reliability")

        final_score = max(0, score)
        self.metrics.set_gauge("llm_readiness_score", final_score)

        grade = "C"
        if final_score > GRADE_A_THRESHOLD:
            grade = "A"
        elif final_score > GRADE_B_THRESHOLD:
            grade = "B"

        return {"score": final_score, "grade": grade, "issues": reasons}
