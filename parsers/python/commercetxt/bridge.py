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
        lines = []

        # === IDENTITY ===
        identity = d.get("IDENTITY", {})
        if identity:
            lines.append(f"STORE: {identity.get('Name', 'Unknown')}")
            lines.append(f"CURRENCY: {identity.get('Currency', 'USD')}")

        # === PRODUCT ===
        product = d.get("PRODUCT", {})
        if product:
            lines.append(f"ITEM: {product.get('Name', 'Unknown Item')}")
            if product.get("SKU"):
                lines.append(f"SKU: {product['SKU']}")
            if product.get("Brand"):
                lines.append(f"BRAND: {product['Brand']}")

        # === OFFER ===
        offer = d.get("OFFER", {})
        if offer:
            lines.append(f"PRICE: {offer.get('Price', 'N/A')}")
            lines.append(f"AVAILABILITY: {offer.get('Availability', 'Unknown')}")
            if offer.get("Condition"):
                lines.append(f"CONDITION: {offer['Condition']}")

        # === INVENTORY ===
        inventory = d.get("INVENTORY", {})
        if inventory:
            stock = inventory.get("Stock")
            if stock is not None:
                lines.append(f"STOCK: {stock} units")
            if inventory.get("LastUpdated"):
                lines.append(f"STOCK_UPDATED: {inventory['LastUpdated']}")

        # === REVIEWS ===
        reviews = d.get("REVIEWS", {})
        if reviews:
            rating = reviews.get("Rating")
            count = reviews.get("Count")
            if rating and count:
                lines.append(f"RATING: {rating}/5 ({count} reviews)")
            if reviews.get("TopTags"):
                lines.append(f"TAGS: {reviews['TopTags']}")

        # === SPECS (top 5 most important) ===
        specs = d.get("SPECS", {})
        if specs:
            lines.append("SPECS:")
            # Get first 5 specs to avoid token bloat
            spec_items = list(specs.items())[:5]
            for key, value in spec_items:
                if key != "items":  # Skip internal structure
                    lines.append(f"  {key}: {value}")

        # === VARIANTS (summarized) ===
        variants = d.get("VARIANTS", {})
        if variants and "Options" in variants:
            options = variants["Options"]
            if isinstance(options, list) and len(options) > 0:
                variant_type = variants.get("Type", "Options")
                option_names = [
                    opt.get("name") or opt.get("value") for opt in options[:3]
                ]
                lines.append(f"{variant_type.upper()}: {', '.join(option_names)}")
                if len(options) > 3:
                    lines.append(f"  (+{len(options) - 3} more)")

        # === SHIPPING ===
        shipping = d.get("SHIPPING", {})
        if shipping and "items" in shipping:
            lines.append("SHIPPING:")
            for item in shipping["items"][:2]:  # First 2 methods
                if isinstance(item, dict):
                    name = item.get("name", "")
                    path = item.get("path", "")
                    lines.append(f"  {name}: {path}")

        # === URL ===
        buy_link = offer.get("URL") or product.get("URL")
        if buy_link:
            lines.append(f"URL: {buy_link}")

        # === TRUST FLAGS ===
        if "inventory_stale" in self.result.trust_flags:
            lines.append("NOTE: Inventory data may be outdated")

        # === PROMOS ===
        promos = d.get("PROMOS", {}).get("items", [])
        if promos:
            lines.append("PROMOS:")
            for p in promos:
                name = p.get("name", "Promo")
                val = p.get("value", "")
                lines.append(f"  - {name}: {val}")

        # === COMPATIBILITY ===
        comp = d.get("COMPATIBILITY", {})
        if comp:
            lines.append("COMPATIBILITY:")
            for k, v in comp.items():
                if k != "items":
                    lines.append(f"  {k}: {v}")

        # === AI GUIDANCE (Logic & Voice) ===
        logic = d.get("SEMANTIC_LOGIC", {}).get("items", [])
        if logic:
            lines.append("AI_LOGIC_RULES:")
            for rule in logic:
                question = rule.get("name", "")
                answer = rule.get("path", "")
                if question and answer:
                    lines.append(f"  - {question} -> {answer}")
                else:
                    val = rule.get("value") if isinstance(rule, dict) else rule
                    lines.append(f"  - {val}")

        voice = d.get("BRAND_VOICE", {})
        if voice:
            lines.append(f"TONE_OF_VOICE: {voice.get('Tone', 'Neutral')}")
            if voice.get("Guidelines"):
                lines.append(f"VOICE_GUIDELINES: {voice['Guidelines']}")

        # === IMAGES ===
        images = d.get("IMAGES", {}).get("items", [])
        if images:
            lines.append("VISUALS:")
            for img in images:
                name = img.get("name", "Image")
                alt = img.get("Alt", "").strip('"')
                if alt:
                    lines.append(f"  - {name}: Describes {alt}")
                else:
                    lines.append(f"  - {name}: Available at {img.get('path', 'N/A')}")

        # === SAFETY & RESTRICTIONS ===
        age = d.get("AGE_RESTRICTION", {})
        if age.get("MinimumAge"):
            lines.append(f"SAFETY: Restricted to ages {age['MinimumAge']}+")
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
