"""
Core directive validation: @IDENTITY, @PRODUCT, @OFFER, @INVENTORY.
These are MANDATORY for Tier 1 compliance (Spec Section 6).
"""

from datetime import datetime, timezone
from typing import ClassVar

from ..constants import (
    CURRENCY_CODE_LEN,
    INVENTORY_STALE_HOURS,
    INVENTORY_VERY_STALE_HOURS,
    MAX_CURRENCY_LEN,
    MIN_CURRENCY_LEN,
    VALID_AVAILABILITY,
    VALID_CONDITION,
    VALID_STOCK_STATUS,
)
from ..logging_config import get_logger
from ..model import ParseResult


class CoreValidator:
    """
    Validates core transactional directives.

    Scope:
    - @IDENTITY: Store identification and currency
    - @PRODUCT: Product identification (Name, SKU, GTIN)
    - @OFFER: Pricing and availability
    - @INVENTORY: Stock levels and freshness
    """

    VALID_AVAILABILITY: ClassVar[set[str]] = VALID_AVAILABILITY
    VALID_CONDITION: ClassVar[set[str]] = VALID_CONDITION
    VALID_STOCK_STATUS: ClassVar[set[str]] = VALID_STOCK_STATUS

    def __init__(self, strict: bool = False, logger=None):
        self.strict = strict
        self.logger = logger or get_logger(__name__)

    def validate(self, result: ParseResult) -> None:
        """Run all core validations."""
        self._validate_identity(result)
        self._validate_product(result)
        self._validate_offer(result)
        self._validate_inventory(result)

    def _validate_identity(self, result: ParseResult) -> None:
        """Validates @IDENTITY (Spec Section 4.1)."""
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
            self._check_currency_code(currency, result)

    def _validate_product(self, result: ParseResult) -> None:
        """Validates @PRODUCT (Spec Section 4.5)."""
        product = result.directives.get("PRODUCT")
        if not product:
            return

        name = self._get_case_insensitive(product, "Name")
        if not name:
            self._error("@PRODUCT missing required 'Name'", result)

        sku = self._get_case_insensitive(product, "SKU")
        if not sku:
            self._error("@PRODUCT missing required 'SKU'", result)

        url = self._get_case_insensitive(product, "URL")
        if not url:
            self._warning("@PRODUCT missing recommended 'URL' field", result)

    def _validate_offer(self, result: ParseResult) -> None:
        """Validates @OFFER (Spec Section 4.6)."""
        offer = result.directives.get("OFFER")
        if not offer:
            return

        # Validate Availability (mandatory field)
        availability = self._get_case_insensitive(offer, "Availability")
        if not availability:
            self._error("@OFFER missing required 'Availability'", result, "OFFER")
        elif availability not in self.VALID_AVAILABILITY:
            self._error(
                f"Invalid Availability: {availability}", result, "OFFER.Availability"
            )

        # Validate Condition (optional field)
        condition = self._get_case_insensitive(offer, "Condition")
        if condition and condition not in self.VALID_CONDITION:
            self._warning(
                f"Non-standard Condition: {condition}", result, "OFFER.Condition"
            )

        # Validate Price (mandatory field)
        price = self._get_case_insensitive(offer, "Price")
        if price:
            try:
                p_val = float(price)
            except (ValueError, TypeError):
                self._error("@OFFER Price must be numeric", result, "OFFER.Price")
            else:
                if p_val < 0:
                    self._error(
                        "@OFFER Price cannot be negative", result, "OFFER.Price"
                    )
        else:
            self._error("@OFFER missing required 'Price'", result, "OFFER")

        # Tax transparency
        tax_incl = self._get_case_insensitive(offer, "TaxIncluded")
        if tax_incl and str(tax_incl).strip().lower() == "true":
            if not self._get_case_insensitive(offer, "TaxRate"):
                self._warning("TaxRate recommended for transparency", result)

    def _validate_inventory(self, result: ParseResult) -> None:
        """Validates @INVENTORY (Spec Section 4.7)."""
        inv = result.directives.get("INVENTORY", {})
        if not inv:
            return

        # StockStatus validation
        status = self._get_case_insensitive(inv, "StockStatus")
        if status and status not in self.VALID_STOCK_STATUS:
            self._error(f"Invalid StockStatus: {status}", result)

        # LastUpdated validation (mandatory)
        last_updated = self._get_case_insensitive(inv, "LastUpdated")
        if not last_updated:
            self._error("@INVENTORY missing required 'LastUpdated'", result)
            return

        # Freshness check (trust flags)
        try:
            last_updated = last_updated.replace("Z", "+00:00")
            dt = datetime.fromisoformat(last_updated)
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now(timezone.utc)
            age_hours = (now - dt).total_seconds() / 3600

            if age_hours > INVENTORY_VERY_STALE_HOURS:
                self._warning("@INVENTORY data is very stale (>7 days)", result)
                result.trust_flags.append("inventory_very_stale")
            elif age_hours > INVENTORY_STALE_HOURS:
                self._warning("@INVENTORY data is stale (>72h)", result)
                result.trust_flags.append("inventory_stale")
        except Exception as e:
            self._warning(f"@INVENTORY LastUpdated format error: {e}", result)

        # Stock must be integer
        stock = self._get_case_insensitive(inv, "Stock")
        if stock is not None:
            try:
                int(stock)
            except (ValueError, TypeError):
                self._error("@INVENTORY Stock must be an integer", result)

    # === Helper Methods ===

    def _check_currency_code(self, currency, result):
        """Validates ISO 4217 currency codes."""
        curr_str = str(currency).strip()
        if len(curr_str) == CURRENCY_CODE_LEN:
            if not curr_str.isalpha():
                self._error(
                    f"Invalid Currency code '{curr_str}'. Use letters only.", result
                )
        elif len(curr_str) < MIN_CURRENCY_LEN or len(curr_str) > MAX_CURRENCY_LEN:
            self._error(
                f"Invalid Currency code '{curr_str}'. Use ISO 4217 code.", result
            )
        else:
            self._warning(f"Currency '{curr_str}' is non-standard.", result)

    def _get_case_insensitive(self, data: dict, key: str, default=None):
        """Case-insensitive key lookup."""
        for k, v in data.items():
            if k.lower() == key.lower():
                return v
        return default

    def _error(self, message: str, result: ParseResult, context_key: str | None = None):
        """
        Report an error with optional line number from source mapping.

        Args:
            message: Error message
            result: ParseResult to append error to
            context_key: Optional key to lookup in source_map
                (e.g., "OFFER", "PRODUCT.Name")
        """
        # Try to enhance message with line number if source mapping available
        if context_key and result.source_map:
            line_no = result.source_map.get(context_key)
            if line_no:
                message = f"Line {line_no}: {message}"

        result.errors.append(message)
        self.logger.error(message)
        if self.strict:
            raise ValueError(message)

    def _warning(
        self, message: str, result: ParseResult, context_key: str | None = None
    ):
        """
        Report a warning with optional line number from source mapping.

        Args:
            message: Warning message
            result: ParseResult to append warning to
            context_key: Optional key to lookup in source_map
        """
        # Try to enhance message with line number if source mapping available
        if context_key and result.source_map:
            line_no = result.source_map.get(context_key)
            if line_no:
                message = f"Line {line_no}: {message}"

        result.warnings.append(message)
        self.logger.warning(message)
