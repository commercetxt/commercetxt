"""
Validates parsed CommerceTXT data.
Enforces protocol rules.
Protects data integrity across three tiers.
"""

import re
from datetime import datetime
from .logging_config import get_logger
from .model import ParseResult
from .metrics import get_metrics


class CommerceTXTValidator:
    """
    Enforces protocol rules.
    Runs checks across three compliance tiers.
    """

    # --- CONSTANTS ---
    VALID_AVAILABILITY = {"InStock", "OutOfStock", "PreOrder", "Discontinued"}
    VALID_CONDITION = {"New", "Refurbished", "Used"}
    VALID_STOCK_STATUS = {"InStock", "LowStock", "OutOfStock", "Backorder"}

    INVENTORY_STALE_HOURS = 72
    INVENTORY_VERY_STALE_HOURS = 168

    TRUSTED_REVIEW_DOMAINS = [
        "trustpilot.com",
        "google.com",
        "reviews.io",
        "yotpo.com",
        "feefo.com",
    ]

    def __init__(self, strict: bool = False, logger=None):
        self.strict = strict
        self.logger = logger or get_logger(__name__)

    def validate(self, result: ParseResult) -> ParseResult:
        """
        Run all validation checks.
        Truth over chaos. Returns the populated result object.
        """
        metrics = get_metrics()
        metrics.start_timer("validation")

        self.logger.debug("Starting validation")

        # Tier 1: Critical. Data is useless without these.
        self._validate_identity(result)
        self._validate_product(result)
        self._validate_offer(result)

        # Tier 2: Standard. Commercial requirements.
        self._validate_inventory(result)
        self._validate_reviews(result)
        self._validate_age_restriction(result)
        self._validate_subscription(result)
        self._validate_locales(result)
        self._validate_shipping(result)
        self._validate_payment(result)
        self._validate_policies(result)
        self._validate_specs(result)
        self._validate_in_the_box(result)

        # Tier 3: Rich metadata. Good for AI and UX.
        self._validate_images(result)
        self._validate_compatibility(result)
        self._validate_variants(result)
        self._validate_variants_semantics(result)
        self._validate_semantic_logic(result)

        if result.errors:
            self.logger.error(f"Validation failed with {len(result.errors)} errors")
        else:
            self.logger.info(f"Validation passed with {len(result.warnings)} warnings")

        # Metrics Stop. Record findings.
        metrics.stop_timer("validation")
        metrics.gauge("validation_errors", len(result.errors))
        metrics.gauge("validation_warnings", len(result.warnings))

        return result

    # --- HELPERS ---

    def _error(self, message: str, result: ParseResult):
        """Log failure. Stop if strict."""
        result.errors.append(message)
        self.logger.error(message)
        if self.strict:
            raise ValueError(message)

    def _warning(self, message: str, result: ParseResult):
        """Log minor issue."""
        result.warnings.append(message)
        self.logger.warning(message)

    def _get_case_insensitive(self, data: dict, key: str, default=None):
        """Find key. Ignore case."""
        for k, v in data.items():
            if k.lower() == key.lower():
                return v
        return default

    # --- TIER 1 ---

    def _validate_identity(self, result: ParseResult):
        """Check store identity. Name and Currency are required."""
        identity = result.directives.get("IDENTITY", {})
        is_child_context = ("PRODUCT" in result.directives) or (
            "ITEMS" in result.directives
        )

        if not identity:
            if not is_child_context:
                self._error(
                    "Missing @IDENTITY directive. Required for Root files.", result
                )
            return

        name = self._get_case_insensitive(identity, "Name")
        if not name:
            self._error("@IDENTITY missing required 'Name'", result)

        currency = self._get_case_insensitive(identity, "Currency")
        if not currency:
            self._error("@IDENTITY missing required 'Currency'", result)
        else:
            curr_str = str(currency).strip()
            if len(curr_str) == 3:
                if not curr_str.isalpha():
                    self._error(
                        f"Invalid Currency code '{curr_str}'. Use letters only.", result
                    )
            elif len(curr_str) < 2 or len(curr_str) > 4:
                self._error(
                    f"Invalid Currency code '{curr_str}'. Use ISO 4217 code.", result
                )
            else:
                self._warning(f"Currency '{curr_str}' is non-standard.", result)

    def _validate_product(self, result: ParseResult):
        """Check product fields."""
        product = result.directives.get("PRODUCT")
        if product:
            url = self._get_case_insensitive(product, "URL")
            if not url:
                self._warning("@PRODUCT missing recommended 'URL' field", result)

    def _validate_offer(self, result: ParseResult):
        """Check the offer. Availability and Price are mandatory."""
        offer = result.directives.get("OFFER")
        if not offer:
            return

        availability = self._get_case_insensitive(offer, "Availability")
        if not availability:
            self._error("@OFFER missing required 'Availability'", result)
        elif availability not in self.VALID_AVAILABILITY:
            self._error(f"Invalid Availability: {availability}", result)

        condition = self._get_case_insensitive(offer, "Condition")
        if condition and condition not in self.VALID_CONDITION:
            self._warning(f"Non-standard Condition: {condition}", result)

        price = self._get_case_insensitive(offer, "Price")
        if price:
            p_val = None
            try:
                p_val = float(price)
            except (ValueError, TypeError):
                self._error("@OFFER Price must be numeric", result)

            if p_val is not None and p_val < 0:
                self._error("@OFFER Price cannot be negative", result)
        else:
            self._error("@OFFER missing required 'Price'", result)

        # Tax transparency check.
        tax_incl = self._get_case_insensitive(offer, "TaxIncluded")
        if tax_incl and str(tax_incl).strip().lower() == "true":
            if not self._get_case_insensitive(offer, "TaxRate"):
                self._warning("TaxRate recommended for transparency", result)

    # --- TIER 2 ---

    def _validate_inventory(self, result: ParseResult):
        """Check stock levels. Flag old data."""
        inv = result.directives.get("INVENTORY", {})
        if not inv:
            return

        status = self._get_case_insensitive(inv, "StockStatus")
        if status and status not in self.VALID_STOCK_STATUS:
            self._error(f"Invalid StockStatus: {status}", result)

        last_updated = self._get_case_insensitive(inv, "LastUpdated")
        if not last_updated:
            self._error("@INVENTORY missing required 'LastUpdated'", result)
            return

        try:
            last_updated = last_updated.replace("Z", "+00:00")
            dt = datetime.fromisoformat(last_updated)
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            age_hours = (now - dt).total_seconds() / 3600

            if age_hours > self.INVENTORY_VERY_STALE_HOURS:
                self._warning("@INVENTORY data is very stale (>7 days)", result)
                result.trust_flags.append("inventory_very_stale")
            elif age_hours > self.INVENTORY_STALE_HOURS:
                self._warning("@INVENTORY data is stale (>72h)", result)
                result.trust_flags.append("inventory_stale")
        except Exception as e:
            self._warning(f"@INVENTORY LastUpdated format error: {e}", result)

    def _validate_reviews(self, result: ParseResult):
        """Validate user reviews. Check sources and ranges."""
        reviews = result.directives.get("REVIEWS")
        if not reviews:
            return

        rating_scale_raw = self._get_case_insensitive(reviews, "RatingScale")
        scale_val = 5.0
        if not rating_scale_raw:
            self._error("@REVIEWS missing required 'RatingScale'", result)
        else:
            try:
                scale_val = float(rating_scale_raw)
            except ValueError:
                self._error("@REVIEWS RatingScale must be numeric", result)

        source = self._get_case_insensitive(reviews, "Source")
        if source:
            source_str = str(source).lower()
            if not any(domain in source_str for domain in self.TRUSTED_REVIEW_DOMAINS):
                result.trust_flags.append("reviews_unverified")
                self._warning(f"Review source '{source}' is unverified", result)

        rating = self._get_case_insensitive(reviews, "Rating")
        if rating:
            try:
                r_val = float(rating)
                if not (0 <= r_val <= scale_val):
                    self._warning(f"Rating {r_val} outside allowed scale", result)
            except ValueError:
                self._error("@REVIEWS Rating must be numeric", result)

        count = self._get_case_insensitive(reviews, "Count")
        if count:
            try:
                c_val = int(count)
                if c_val < 0:
                    self._error("@REVIEWS Count cannot be negative", result)
            except ValueError:
                self._error("@REVIEWS Count must be numeric", result)

    def _validate_subscription(self, result: ParseResult):
        """Subscriptions must have active plans."""
        sub = result.directives.get("SUBSCRIPTION")
        if not sub:
            return
        plans = self._get_case_insensitive(sub, "Plans")
        if not plans or not isinstance(plans, list) or len(plans) == 0:
            self._error("@SUBSCRIPTION missing required Plans", result)

    def _validate_age_restriction(self, result: ParseResult):
        """Check age limits."""
        age_dir = result.directives.get("AGE_RESTRICTION", {})
        min_age = self._get_case_insensitive(age_dir, "MinimumAge")
        if min_age is not None:
            try:
                age_val = int(min_age)
                if age_val < 0:
                    self._error("Age cannot be negative", result)
            except ValueError:
                self._error("MinimumAge must be numeric", result)

    def _validate_locales(self, result: ParseResult):
        """Check locale codes. Allow only one current locale."""
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

    def _validate_shipping(self, result: ParseResult):
        shipping = result.directives.get("SHIPPING")
        if shipping is not None and not shipping.get("items") and len(shipping) <= 0:
            self._warning("@SHIPPING section is empty", result)

    def _validate_payment(self, result: ParseResult):
        payment = result.directives.get("PAYMENT")
        if payment is not None and not payment.get("items") and len(payment) <= 0:
            self._warning("@PAYMENT section is empty", result)

    def _validate_policies(self, result: ParseResult):
        policies = result.directives.get("POLICIES")
        if policies is not None and not policies:
            self._warning("@POLICIES section is empty", result)

    def _validate_specs(self, result: ParseResult):
        specs = result.directives.get("SPECS")
        if specs is not None and len(specs) == 0:
            self._warning("@SPECS section is empty", result)

    def _validate_in_the_box(self, result: ParseResult):
        box = result.directives.get("IN_THE_BOX")
        if box is not None and not box.get("items"):
            self._warning("@IN_THE_BOX section is empty", result)

    # --- TIER 3 ---

    def _validate_images(self, result: ParseResult):
        """Check image metadata. One 'Main' image is required."""
        imgs = result.directives.get("IMAGES", {}).get("items", [])
        if not imgs:
            return
        has_main = any(
            str(i.get("name", "")).lower() == "main"
            for i in imgs
            if isinstance(i, dict)
        )
        if not has_main:
            self._warning("@IMAGES missing 'Main' image", result)

        for item in imgs:
            if isinstance(item, dict):
                alt = self._get_case_insensitive(item, "Alt")
                if alt and len(str(alt)) > 120:
                    self._warning("Alt text too long (>120 chars)", result)

    def _validate_compatibility(self, result: ParseResult):
        """Verify compatibility keys."""
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
        for k in comp.keys():
            if k.lower() not in {a.lower() for a in allowed}:
                self._warning(f"Unknown key in @COMPATIBILITY: {k}", result)

    def _validate_variants(self, result: ParseResult):
        """Verify variants have a base offer."""
        variants = result.directives.get("VARIANTS")
        offer = result.directives.get("OFFER")
        if variants:
            if not offer:
                self._error("@VARIANTS used without @OFFER section", result)
                return
            if not self._get_case_insensitive(offer, "Price"):
                self._error("@VARIANTS requires base Price in @OFFER", result)

    def _validate_variants_semantics(self, result: ParseResult):
        """Calculate variant price logic. Block negative outcomes."""
        variants = result.directives.get("VARIANTS")
        offer = result.directives.get("OFFER")
        if not variants or not offer:
            return
        base_price_raw = self._get_case_insensitive(offer, "Price")
        try:
            base_price = float(base_price_raw)
        except (ValueError, TypeError):
            return

        options = self._get_case_insensitive(variants, "Options", [])
        if not isinstance(options, list):
            return
        for opt in options:
            if not isinstance(opt, dict):
                continue
            val = str(opt.get("path") or opt.get("value", "0")).strip()
            if val.startswith(("+", "-")):
                try:
                    modifier = float(val)
                    if base_price + modifier < 0:
                        self._error(
                            f"Variant '{opt.get('name')}' yields negative price", result
                        )
                except (ValueError, TypeError):
                    pass

    def _validate_semantic_logic(self, result: ParseResult):
        """Protect facts. Do not allow logic to override data."""
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
