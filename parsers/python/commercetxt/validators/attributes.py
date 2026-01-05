"""
Attribute validation: @SPECS, @IMAGES, @REVIEWS, @COMPATIBILITY, etc.
These are OPTIONAL but recommended for Tier 2+ compliance.
"""

from typing import ClassVar

from ..constants import MAX_ALT_TEXT_LEN, TRUSTED_REVIEW_DOMAINS
from ..logging_config import get_logger
from ..model import ParseResult


class AttributeValidator:
    """
    Validates product attribute directives.

    Scope:
    - @SPECS: Technical specifications
    - @IMAGES: Product images with alt text
    - @REVIEWS: Aggregated review data
    - @COMPATIBILITY: Works with / requires
    - @IN_THE_BOX: Package contents
    - @VARIANTS: Product variants (delegates to EnhancedVariantsValidator)
    """

    TRUSTED_REVIEW_DOMAINS: ClassVar[list[str]] = TRUSTED_REVIEW_DOMAINS

    def __init__(self, strict: bool = False, logger=None):
        self.strict = strict
        self.logger = logger or get_logger(__name__)

    def validate(self, result: ParseResult) -> None:
        """Run all attribute validations."""
        self._validate_specs(result)
        self._validate_images(result)
        self._validate_reviews(result)
        self._validate_compatibility(result)
        self._validate_in_the_box(result)
        self._validate_variants(result)

    def _validate_specs(self, result: ParseResult) -> None:
        """Validates @SPECS (Spec Section 4.15)."""
        specs = result.directives.get("SPECS")
        if specs is not None and len(specs) == 0:
            self._warning("@SPECS section is empty", result)

    def _validate_images(self, result: ParseResult) -> None:
        """Validates @IMAGES (Spec Section 4.22)."""
        imgs = result.directives.get("IMAGES", {}).get("items", [])
        if not imgs:
            return

        # Check for Main image
        has_main = any(
            str(i.get("name", "")).lower() == "main"
            for i in imgs
            if isinstance(i, dict)
        )
        if not has_main:
            self._warning("@IMAGES missing 'Main' image", result)

        # Validate alt text length
        for item in imgs:
            if isinstance(item, dict):
                alt = self._get_case_insensitive(item, "Alt")
                if alt:
                    alt_clean = str(alt).strip("\"'")
                    if alt_clean and len(str(alt)) > MAX_ALT_TEXT_LEN:
                        self._warning(
                            f"Alt text too long (>{MAX_ALT_TEXT_LEN} chars)", result
                        )

    def _validate_reviews(self, result: ParseResult) -> None:
        """Validates @REVIEWS (Spec Section 4.9)."""
        reviews = result.directives.get("REVIEWS")
        if not reviews:
            return

        scale_val = self._validate_rating_scale(reviews, result)
        self._validate_review_source(reviews, result)
        self._validate_review_rating(reviews, result, scale_val)
        self._validate_review_count(reviews, result)

        # TopTags balance check (Spec Section 4.9)
        top_tags = self._get_case_insensitive(reviews, "TopTags")
        if top_tags:
            self._validate_reviews_balance(str(top_tags), result)

    def _validate_rating_scale(self, reviews: dict, result: ParseResult) -> float:
        """Validate RatingScale field and return the scale value."""
        rating_scale_raw = self._get_case_insensitive(reviews, "RatingScale")
        scale_val = 5.0
        if not rating_scale_raw:
            self._error("@REVIEWS missing required 'RatingScale'", result)
        else:
            try:
                scale_val = float(rating_scale_raw)
            except ValueError:
                self._error("@REVIEWS RatingScale must be numeric", result)
        return scale_val

    def _validate_review_source(self, reviews: dict, result: ParseResult) -> None:
        """Validate review source for trust flags."""
        source = self._get_case_insensitive(reviews, "Source")
        if source:
            source_str = str(source).lower()
            if not any(domain in source_str for domain in self.TRUSTED_REVIEW_DOMAINS):
                result.trust_flags.append("reviews_unverified")
                self._warning(f"Review source '{source}' is unverified", result)

    def _validate_review_rating(
        self, reviews: dict, result: ParseResult, scale_val: float
    ) -> None:
        """Validate rating value against scale."""
        rating = self._get_case_insensitive(reviews, "Rating")
        if rating:
            try:
                r_val = float(rating)
                if not (0 <= r_val <= scale_val):
                    self._warning(f"Rating {r_val} outside allowed scale", result)
            except ValueError:
                self._error("@REVIEWS Rating must be numeric", result)

    def _validate_review_count(self, reviews: dict, result: ParseResult) -> None:
        """Validate review count."""
        count = self._get_case_insensitive(reviews, "Count")
        if count:
            try:
                c_val = int(count)
                if c_val < 0:
                    self._error("@REVIEWS Count cannot be negative", result)
            except ValueError:
                self._error("@REVIEWS Count must be numeric", result)

    def _validate_reviews_balance(self, top_tags_str: str, result: ParseResult) -> None:
        """
        Validates @REVIEWS TopTags for sentiment balance.

        Spec Section 4.9: SHOULD include at least 1 negative tag
        if negative themes exceed 20%.
        This heuristic checks if tags cherry-pick only positive sentiment.

        Note: This is a simplified heuristic. Full compliance requires
        analyzing actual review sentiment distribution, which is beyond
        the scope of static validation.
        """
        tags = [t.strip().strip("\"'") for t in top_tags_str.split(",")]

        # Filter out empty tags
        tags = [t for t in tags if t]

        # Need at least this many tags to make meaningful assessment
        min_tags_for_balance_check = 5
        if len(tags) < min_tags_for_balance_check:
            return

        # Heuristic: Check for only positive words
        positive_words = {
            "great",
            "excellent",
            "amazing",
            "best",
            "perfect",
            "love",
            "loved",
            "awesome",
            "fantastic",
            "wonderful",
            "brilliant",
            "outstanding",
            "superb",
            "exceptional",
            "impressive",
            "quality",
            "recommended",
        }
        negative_words = {
            "tight",
            "expensive",
            "pricey",
            "heavy",
            "uncomfortable",
            "bulky",
            "loud",
            "noisy",
            "small",
            "short",
            "difficult",
            "hard",
            "poor",
            "weak",
            "slow",
            "disappointing",
            "issue",
            "problem",
            "not",
        }

        tags_lower = [t.lower() for t in tags]

        has_positive = any(
            any(pw in tag for pw in positive_words) for tag in tags_lower
        )
        has_negative = any(
            any(nw in tag for nw in negative_words) for tag in tags_lower
        )

        if has_positive and not has_negative:
            self._warning(
                "@REVIEWS TopTags appear to cherry-pick only positive sentiment. "
                "Consider adding balanced feedback per spec Section 4.9.",
                result,
            )

    def _validate_compatibility(self, result: ParseResult) -> None:
        """Validates @COMPATIBILITY (Spec Section 4.18)."""
        comp = result.directives.get("COMPATIBILITY", {})
        if not comp:
            return

        allowed = {
            "WorksWith",
            "Requires",
            "NotCompatibleWith",
            "OptimalWith",
            "CarrierCompatibility",
            "items",
        }
        for k in comp:
            if k.lower() not in {a.lower() for a in allowed}:
                self._warning(f"Unknown key in @COMPATIBILITY: {k}", result)

    def _validate_in_the_box(self, result: ParseResult) -> None:
        """Validates @IN_THE_BOX (Spec Section 4.17)."""
        box = result.directives.get("IN_THE_BOX")
        if box is not None and not box.get("items"):
            self._warning("@IN_THE_BOX section is empty", result)

    def _validate_variants(self, result: ParseResult) -> None:
        """
        Validates @VARIANTS (Spec Section 4.10).
        Delegates to EnhancedVariantsValidator for complex validation.
        """
        variants = result.directives.get("VARIANTS")
        if not variants:
            return

        # Import here to avoid circular dependency
        from ..enhanced_variants_validator import EnhancedVariantsValidator

        offer = result.directives.get("OFFER", {})
        product = result.directives.get("PRODUCT", {})
        product_name = product.get("Name", "Product")

        variants_validator = EnhancedVariantsValidator(strict=self.strict)
        variants_validator.validate(variants, offer, product_name)

        result.errors.extend(variants_validator.errors)
        result.warnings.extend(variants_validator.warnings)

    # === Helper Methods ===

    def _get_case_insensitive(self, data: dict, key: str, default=None):
        for k, v in data.items():
            if k.lower() == key.lower():
                return v
        return default

    def _error(self, message: str, result: ParseResult):
        result.errors.append(message)
        self.logger.error(message)
        if self.strict:
            raise ValueError(message)

    def _warning(self, message: str, result: ParseResult):
        result.warnings.append(message)
        self.logger.warning(message)
