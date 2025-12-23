"""
Bridge between CommerceTXT and Large Language Models.
Optimized for low token usage and high reliability.
"""

from .model import ParseResult
from .metrics import get_metrics


class CommerceAIBridge:
    """Connects parsed data to AI systems."""

    def __init__(self, result: ParseResult):
        self.result = result
        self.metrics = get_metrics()

    def generate_low_token_prompt(self) -> str:
        """Create a clean, dense text prompt for LLMs."""
        d = self.result.directives

        identity = d.get("IDENTITY", {})
        store_name = identity.get("Name") or "Unknown Store"
        currency = identity.get("Currency") or "USD"

        product = d.get("PRODUCT", {})
        offer = d.get("OFFER", {})

        buy_link = offer.get("URL") or product.get("URL") or "N/A"

        # Build clean data lines. No noise.
        lines = [
            f"STORE: {store_name}",
            f"CURRENCY: {currency}",
            f"ITEM: {product.get('Name', 'Unknown Item')}",
            f"PRICE: {offer.get('Price', 'N/A')}",
            f"AVAILABILITY: {offer.get('Availability', 'Unknown')}",
        ]

        if buy_link != "N/A":
            lines.append(f"BUY_LINK: {buy_link}")

        if "inventory_stale" in self.result.trust_flags:
            lines.append("NOTE: Inventory data may be outdated")

        return "\n".join(lines)

    def calculate_readiness_score(self) -> dict:
        """Measure if data is fit for AI consumption."""
        score = 100
        reasons = []

        if not self.result.version:
            score -= 10
            reasons.append("Missing version directive")

        offer = self.result.directives.get("OFFER", {})
        if not offer.get("Price") or not offer.get("Availability"):
            score -= 30
            reasons.append("Missing core offer data (Price/Availability)")

        # Errors damage reliability. Subtract heavily.
        if self.result.errors:
            score -= len(self.result.errors) * 20

        if "inventory_stale" in self.result.trust_flags:
            score -= 15
            reasons.append("Stale inventory reduces reliability")

        final_score = max(0, score)
        self.metrics.set_gauge("llm_readiness_score", final_score)

        return {
            "score": final_score,
            "grade": "A" if final_score > 90 else "B" if final_score > 70 else "C",
            "issues": reasons,
        }
