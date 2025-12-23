"""
Tests for CommerceTXT Validator.
Check the rules. Trust the data.
"""

import pytest
from datetime import datetime, timedelta
from commercetxt.parser import CommerceTXTParser
from commercetxt.validator import CommerceTXTValidator

from commercetxt import ParseResult

from commercetxt.constants import (
    VALID_AVAILABILITY,
    VALID_CONDITION,
    VALID_STOCK_STATUS,
    INVENTORY_STALE_HOURS,
)


def test_protocol_constants_integrity():
    """Ensure core protocol constants are not altered accidentally."""
    assert "InStock" in VALID_AVAILABILITY
    assert "OutOfStock" in VALID_AVAILABILITY

    assert "New" in VALID_CONDITION
    assert "Used" in VALID_CONDITION

    assert "Backorder" in VALID_STOCK_STATUS

    assert INVENTORY_STALE_HOURS == 72


def test_strict_validation_raises_on_missing_identity():
    """Strict mode must raise ValueError on critical missing data."""
    parser = CommerceTXTParser()
    result = parser.parse("# @OFFER\nPrice: 10.00\nAvailability: InStock")
    validator = CommerceTXTValidator(strict=True)

    with pytest.raises(ValueError, match="Missing @IDENTITY directive"):
        validator.validate(result)


def test_non_strict_collects_errors():
    """Non-strict mode collects errors. It does not stop."""
    parser = CommerceTXTParser()
    content = "# @OFFER\nPrice: 10.00"
    result = parser.parse(content)
    validator = CommerceTXTValidator(strict=False)
    validator.validate(result)

    assert len(result.errors) > 0
    assert any("Missing @IDENTITY directive" in e for e in result.errors)


def test_inventory_stale_warning():
    """Old inventory data triggers a stale warning."""
    parser = CommerceTXTParser()
    result = parser.parse(
        """
# @IDENTITY
Name: Store
Currency: USD
# @INVENTORY
StockStatus: InStock
LastUpdated: 2020-01-01T00:00:00Z
"""
    )
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("stale" in w for w in result.warnings)


def test_variants_without_offer_error():
    """Variants need an Offer section. Error if missing."""
    parser = CommerceTXTParser()
    result = parser.parse(
        """
# @IDENTITY
Name: Store
Currency: USD
# @VARIANTS
Options:
  - Red: +0
"""
    )
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("@VARIANTS used without @OFFER" in e for e in result.errors)


def test_valid_minimal_tier_passes():
    """Minimal valid file should have zero errors."""
    parser = CommerceTXTParser()
    result = parser.parse(
        """
# @IDENTITY
Name: Store
Currency: USD
# @OFFER
Price: 99.00
Availability: InStock
"""
    )
    validator = CommerceTXTValidator(strict=True)
    validated = validator.validate(result)
    assert not validated.errors


def test_negative_price_error():
    """Prices cannot be negative. This is an error."""
    parser = CommerceTXTParser()
    result = parser.parse("# @OFFER\nPrice: -10.00")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("Price cannot be negative" in e for e in result.errors)


def test_tax_transparency_warning():
    """TaxIncluded needs a TaxRate. Warning only."""
    parser = CommerceTXTParser()
    result = parser.parse(
        """
# @IDENTITY
Name: X
Currency: USD
# @OFFER
Price: 100
Availability: InStock
TaxIncluded: True
"""
    )
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("TaxRate recommended" in w for w in result.warnings)


def test_invalid_currency_code():
    """Currency codes must follow ISO standards."""
    parser = CommerceTXTParser()
    result = parser.parse("# @IDENTITY\nName: X\nCurrency: Dollars")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("Invalid Currency code" in e for e in result.errors)


def test_subscription_validation_rules():
    """Subscriptions require a list of plans."""
    parser = CommerceTXTParser()
    result = parser.parse("# @SUBSCRIPTION\nCancelAnytime: True")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("missing required Plans" in e for e in result.errors)


def test_images_validation():
    """At least one image should be 'Main'."""
    parser = CommerceTXTParser()
    result = parser.parse("# @IMAGES\n- Photo 1: /1.jpg\n- Photo 2: /2.jpg")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("Main" in w for w in result.warnings)


def test_price_scientific_notation():
    """Prices in scientific notation are valid numbers."""
    parser = CommerceTXTParser()
    result = parser.parse(
        """
# @IDENTITY
Name: X
Currency: USD
# @OFFER
Price: 1e3
Availability: InStock
"""
    )
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert not [e for e in result.errors if "Price" in e]


def test_inventory_very_stale():
    """Inventory older than 7 days is very stale."""
    parser = CommerceTXTParser()
    old_date = (datetime.now() - timedelta(days=8)).isoformat()
    content = (
        f"# @IDENTITY\nName: X\nCurrency: USD\n# @INVENTORY\nLastUpdated: {old_date}"
    )
    result = parser.parse(content)
    validator = CommerceTXTValidator()
    validator.validate(result)

    assert any("very stale" in w for w in result.warnings)
    assert "inventory_very_stale" in result.trust_flags


def test_locales_multiple_current_and_format():
    """Only one locale can be current. Code format matters."""
    parser = CommerceTXTParser()
    content = """
# @IDENTITY
Name: X
Currency: USD
# @LOCALES
INVALID_CODE: /path
en-US: /us (Current)
fr-FR: /fr (Current)
"""
    result = parser.parse(content)
    validator = CommerceTXTValidator()
    validator.validate(result)

    assert any("Invalid locale code" in w for w in result.warnings)
    assert any("Multiple locales marked as current" in e for e in result.errors)


def test_variants_semantics_malformed():
    """Validator must handle malformed variant data without crashing."""
    parser = CommerceTXTParser()
    content = """
# @IDENTITY
Name: X
Currency: USD
# @OFFER
Price: ???
Availability: InStock
# @VARIANTS
Options:
  - Addon: +10
"""
    result = parser.parse(content)
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert len(result.errors) > 0


def test_inventory_date_parsing_exception():
    """Broken date formats trigger a warning."""
    parser = CommerceTXTParser()
    content = """
# @IDENTITY
Name: X
Currency: USD
# @INVENTORY
LastUpdated: THIS-IS-NOT-A-DATE
StockStatus: InStock
"""
    result = parser.parse(content)
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("format error" in w for w in result.warnings)


def test_identity_currency_non_standard_warning():
    """Currencies with non-standard lengths trigger warnings."""
    parser = CommerceTXTParser()
    result = parser.parse("# @IDENTITY\nName: X\nCurrency: USDT")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("is non-standard" in w for w in result.warnings)


def test_variants_missing_base_price():
    """Variants require a Price in the Offer section."""
    parser = CommerceTXTParser()
    content = """
# @IDENTITY
Name: X
Currency: USD
# @OFFER
Availability: InStock
# @VARIANTS
Options:
  - Color: Red
"""
    result = parser.parse(content)
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("requires base Price" in e for e in result.errors)


def test_price_with_currency_symbol():
    """Price containing symbols must fail numeric check."""
    parser = CommerceTXTParser()
    result = parser.parse("# @OFFER\nPrice: $10.00")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("must be numeric" in e for e in result.errors)


def test_availability_invalid_enum():
    """Check against strict allowed availability values."""
    parser = CommerceTXTParser()
    result = parser.parse("# @OFFER\nPrice: 10\nAvailability: SoldOut")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("Invalid Availability" in e for e in result.errors)


def test_stock_status_enum_validation():
    """Inventory StockStatus must match allowed values."""
    parser = CommerceTXTParser()
    result = parser.parse("# @INVENTORY\nStockStatus: Full")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("Invalid StockStatus" in e for e in result.errors)


def test_rating_exceeds_scale_warning():
    """Rating higher than RatingScale triggers a warning."""
    parser = CommerceTXTParser()
    result = parser.parse("# @REVIEWS\nRating: 10\nRatingScale: 5")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("outside allowed scale" in w for w in result.warnings)


def test_negative_rating_error():
    """Ratings cannot be below zero."""
    parser = CommerceTXTParser()
    result = parser.parse("# @REVIEWS\nRating: -1\nRatingScale: 5")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any(
        "numeric" in e or "outside" in str(e) for e in result.errors + result.warnings
    )


def test_invalid_date_format_iso():
    """Non-ISO dates must trigger a warning."""
    parser = CommerceTXTParser()
    result = parser.parse("# @INVENTORY\nLastUpdated: 2024/01/01")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("format error" in w for w in result.warnings)


def test_empty_specs_warning():
    """Sections with no content should warn the user."""
    parser = CommerceTXTParser()
    result = parser.parse("# @SPECS")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("section is empty" in w for w in result.warnings)


def test_untrusted_review_source():
    """Verify that unknown domains flag unverified trust."""
    parser = CommerceTXTParser()
    result = parser.parse("# @REVIEWS\nRating: 5\nSource: shady-reviews.net")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert "reviews_unverified" in result.trust_flags


def test_missing_shipping_items():
    """Empty shipping section should be flagged."""
    parser = CommerceTXTParser()
    result = parser.parse("# @SHIPPING")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("SHIPPING section is empty" in w for w in result.warnings)


def test_missing_payment_items():
    """Empty payment section should be flagged."""
    parser = CommerceTXTParser()
    result = parser.parse("# @PAYMENT")
    validator = CommerceTXTValidator()
    validator.validate(result)
    assert any("PAYMENT section is empty" in w for w in result.warnings)


def test_validator_semantic_logic_overrides():
    """Trigger warnings when logic attempts to override factual data."""
    v = CommerceTXTValidator()
    res = ParseResult(directives={"SEMANTIC_LOGIC": {"items": ["Override Price to 0"]}})
    v.validate(res)
    assert any("Logic overrides facts" in w for w in res.warnings)


def test_validator_age_restriction_variants():
    """Test missing and valid age restriction branches with identity present."""
    v = CommerceTXTValidator()
    identity = {"Name": "Test", "Currency": "USD"}
    res1 = ParseResult(
        directives={"IDENTITY": identity, "AGE_RESTRICTION": {"MinimumAge": "18"}}
    )
    v.validate(res1)
    assert not res1.errors
    res2 = ParseResult(directives={"IDENTITY": identity, "AGE_RESTRICTION": {}})
    v.validate(res2)
    assert not res2.errors


def test_validator_reviews_missing_scale():
    """Trigger error when reviews exist but scale is missing."""
    v = CommerceTXTValidator()
    res = ParseResult(directives={"REVIEWS": {"Rating": "5"}})
    v.validate(res)
    assert any("missing required 'RatingScale'" in e for e in res.errors)


def test_validator_unverified_review_source():
    """Flag reviews from untrusted domains."""
    v = CommerceTXTValidator()
    res = ParseResult(
        directives={"REVIEWS": {"RatingScale": "5", "Source": "unknown.biz"}}
    )
    v.validate(res)
    assert "reviews_unverified" in res.trust_flags


def test_validator_empty_optional_sections():
    """Ensure empty policies and box sections trigger warnings."""
    v = CommerceTXTValidator()
    res = ParseResult(directives={"POLICIES": {}, "IN_THE_BOX": {}})
    v.validate(res)
    assert any("POLICIES section is empty" in w for w in res.warnings)
    assert any("IN_THE_BOX section is empty" in w for w in res.warnings)
