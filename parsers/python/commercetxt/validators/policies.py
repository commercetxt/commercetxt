"""
Policy validation: @SHIPPING, @PAYMENT, @POLICIES, @SUPPORT, etc.
These define store-level policies and are typically in Root files.
"""

import re
from datetime import datetime, timezone

from ..logging_config import get_logger
from ..model import ParseResult


class PolicyValidator:
    """
    Validates policy and operational directives.

    Scope:
    - @SHIPPING: Shipping methods and carriers
    - @PAYMENT: Payment methods
    - @POLICIES: Returns, warranty, privacy
    - @SUPPORT: Customer service contact
    - @LOCALES: Multi-region support
    - @CATALOG: Category mapping (delegates to CatalogFiltersValidator)
    - @FILTERS: Filter definitions (delegates to CatalogFiltersValidator)
    - @SUBSCRIPTION: Subscription plans
    - @AGE_RESTRICTION: Age requirements
    - @SEMANTIC_LOGIC: AI reasoning rules
    - @PROMOS: Promotions
    - @BRAND_VOICE: Communication style
    """

    def __init__(self, strict: bool = False, logger=None):
        self.strict = strict
        self.logger = logger or get_logger(__name__)

    def validate(self, result: ParseResult) -> None:
        """Run all policy validations."""
        self._validate_shipping(result)
        self._validate_payment(result)
        self._validate_policies(result)
        self._validate_support(result)
        self._validate_locales(result)
        self._validate_catalog(result)
        self._validate_filters(result)
        self._validate_subscription(result)
        self._validate_age_restriction(result)
        self._validate_semantic_logic(result)
        self._validate_promos(result)
        self._validate_brand_voice(result)
        self._validate_items(result)

    def _validate_shipping(self, result: ParseResult) -> None:
        """Validates @SHIPPING (Spec Section 4.12)."""
        shipping = result.directives.get("SHIPPING")
        if shipping is not None and not shipping.get("items") and len(shipping) <= 0:
            self._warning("@SHIPPING section is empty", result)

    def _validate_payment(self, result: ParseResult) -> None:
        """Validates @PAYMENT (Spec Section 4.13)."""
        payment = result.directives.get("PAYMENT")
        if payment is not None and not payment.get("items") and len(payment) <= 0:
            self._warning("@PAYMENT section is empty", result)

    def _validate_policies(self, result: ParseResult) -> None:
        """Validates @POLICIES (Spec Section 4.14)."""
        policies = result.directives.get("POLICIES")
        if policies is not None and not policies:
            self._warning("@POLICIES section is empty", result)

    def _validate_support(self, result: ParseResult) -> None:
        """Validates @SUPPORT (Spec Section 4.16)."""
        support = result.directives.get("SUPPORT", {})
        if not support:
            return

        has_contact = any(
            k.lower() in ["email", "phone", "chat", "hours", "contact"]
            for k in support.keys()
        )
        if not has_contact:
            self._warning(
                "@SUPPORT section exists but contains no contact info", result
            )

    def _validate_locales(self, result: ParseResult) -> None:
        """Validates @LOCALES (Spec Section 4.11)."""
        locales = result.directives.get("LOCALES", {})
        if not locales:
            return

        current_count = 0
        locale_pattern = re.compile(r"^[a-z]{2}(-[a-z]{2})?$", re.IGNORECASE)

        for code, path in locales.items():
            if code == "items":
                continue
            if not locale_pattern.match(code):
                self._warning(f"Invalid locale code: {code}", result)
            if "(Current)" in str(path):
                current_count += 1

        if current_count > 1:
            self._error("Multiple locales marked as current", result)

    def _validate_catalog(self, result: ParseResult) -> None:
        """Validates @CATALOG (Spec Section 4.2)."""
        catalog = result.directives.get("CATALOG", {})
        if not catalog:
            return

        from ..catalog_filters_validator import CatalogFiltersValidator

        catalog_validator = CatalogFiltersValidator(strict=self.strict)
        file_level = getattr(result, "level", "root")
        catalog_validator.validate_catalog(catalog, file_level)

        result.errors.extend(catalog_validator.errors)
        result.warnings.extend(catalog_validator.warnings)

    def _validate_filters(self, result: ParseResult) -> None:
        """Validates @FILTERS (Spec Section 4.3)."""
        filters = result.directives.get("FILTERS", {})
        if not filters:
            return

        from ..catalog_filters_validator import CatalogFiltersValidator

        filters_validator = CatalogFiltersValidator(strict=self.strict)
        file_level = getattr(result, "level", "category")
        filters_validator.validate_filters(filters, file_level)

        result.errors.extend(filters_validator.errors)
        result.warnings.extend(filters_validator.warnings)

    def _validate_subscription(self, result: ParseResult) -> None:
        """Validates @SUBSCRIPTION (Spec Section 4.8)."""
        sub = result.directives.get("SUBSCRIPTION")
        if not sub:
            return

        plans = self._get_case_insensitive(sub, "Plans")
        if not plans or not isinstance(plans, list) or len(plans) == 0:
            self._error("@SUBSCRIPTION missing required Plans", result)

        promo = self._get_case_insensitive(sub, "PromotionalPricing")
        if promo:
            if not isinstance(promo, list):
                self._warning("PromotionalPricing should be a list", result)
            else:
                for item in promo:
                    if isinstance(item, dict):
                        # Check for required keys
                        if "Offer" not in item:
                            self._warning(
                                "PromotionalPricing item missing 'Offer'", result
                            )
                        if "Duration" not in item:
                            self._warning(
                                "PromotionalPricing item missing 'Duration'", result
                            )

    def _validate_age_restriction(self, result: ParseResult) -> None:
        """Validates @AGE_RESTRICTION (Spec Section 4.23)."""
        age_dir = result.directives.get("AGE_RESTRICTION", {})
        min_age = self._get_case_insensitive(age_dir, "MinimumAge")
        if min_age is not None:
            try:
                age_val = int(min_age)
                if age_val < 0:
                    self._error("Age cannot be negative", result)
            except ValueError:
                self._error("MinimumAge must be numeric", result)

        verification = self._get_case_insensitive(age_dir, "VerificationRequired")
        if verification and str(verification).lower() not in ("true", "false"):
            self._warning("VerificationRequired should be boolean", result)

    def _validate_semantic_logic(self, result: ParseResult) -> None:
        """Validates @SEMANTIC_LOGIC (Spec Section 4.19)."""
        logic = result.directives.get("SEMANTIC_LOGIC")
        if not logic:
            return

        items = logic.get("items", [])
        for rule in items:
            rule_str = str(
                rule.get("value") if isinstance(rule, dict) else rule
            ).lower()
            forbidden = ["price", "stock", "availability", "inventory", "currency"]
            if any(word in rule_str for word in forbidden):
                self._warning(f"Logic overrides facts: {rule_str[:30]}...", result)

    def _validate_promos(self, result: ParseResult) -> None:
        """Validates @PROMOS (Spec Section 4.21)."""
        promos = result.directives.get("PROMOS", {})
        if not promos:
            return

        items = promos.get("items", [])
        if not items and not promos:
            self._warning("@PROMOS section is empty", result)

        for item in items:
            expires = item.get("Expires")
            if expires:
                try:
                    exp_date = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                    if exp_date < datetime.now(timezone.utc):
                        self._warning(f"Promo '{item.get('name')}' has expired", result)
                except ValueError:
                    self._warning(f"Invalid Expires date: {expires}", result)

    def _validate_brand_voice(self, result: ParseResult) -> None:
        """Validates @BRAND_VOICE (Spec Section 4.20)."""
        voice = result.directives.get("BRAND_VOICE", {})
        if not voice:
            return

        allowed_keys = {"Tone", "Restrictions", "Emphasis", "items"}
        for k in voice:
            if k not in allowed_keys:
                self._warning(f"Unknown key in @BRAND_VOICE: {k}", result)

        tone = self._get_case_insensitive(voice, "Tone")
        if tone:
            standard_tones = [
                "Professional",
                "Friendly",
                "Technical",
                "Direct",
                "Enthusiastic",
            ]
            if tone not in standard_tones:
                self._warning(f"Non-standard Tone: {tone}", result)

    def _validate_items(self, result: ParseResult) -> None:
        """Validates @ITEMS (Spec Section 4.4)."""
        items = result.directives.get("ITEMS", {})
        if not items:
            return

        from ..catalog_filters_validator import CatalogFiltersValidator

        validator = CatalogFiltersValidator(strict=self.strict)
        validator._validate_items(result)

        result.errors.extend(validator.errors)
        result.warnings.extend(validator.warnings)

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
