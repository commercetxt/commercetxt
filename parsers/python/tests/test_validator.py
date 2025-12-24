"""
Comprehensive Tests for CommerceTXT Validator.
Spec-grade coverage for Tier 1, Tier 2 and Tier 3 rules.
Validator is treated as protocol authority.
"""

import pytest
import builtins
from datetime import datetime, timedelta
from unittest.mock import patch

from commercetxt.validator import CommerceTXTValidator
from commercetxt.model import ParseResult
from commercetxt.constants import (
    VALID_AVAILABILITY,
    VALID_CONDITION,
    VALID_STOCK_STATUS,
    INVENTORY_STALE_HOURS,
)


# =========================================================
# FIXTURES
# =========================================================


@pytest.fixture
def validator():
    return CommerceTXTValidator(strict=False)


@pytest.fixture
def strict_validator():
    return CommerceTXTValidator(strict=True)


@pytest.fixture
def result():
    return ParseResult(directives={}, errors=[], warnings=[], trust_flags=[])


# =========================================================
# CORE CONSTANTS
# =========================================================


def test_protocol_constants_integrity():
    assert "InStock" in VALID_AVAILABILITY
    assert "Used" in VALID_CONDITION
    assert "LowStock" in VALID_STOCK_STATUS
    assert INVENTORY_STALE_HOURS == 72


# =========================================================
# TIER 1 – IDENTITY / PRODUCT / OFFER
# =========================================================


def test_identity_required_for_root(strict_validator):
    res = ParseResult(directives={"OFFER": {"Price": "10", "Availability": "InStock"}})
    with pytest.raises(ValueError):
        strict_validator.validate(res)


def test_identity_optional_for_child_context(validator, result):
    result.directives = {"PRODUCT": {"Name": "X"}}
    validator.validate(result)
    assert not result.errors


def test_identity_currency_validation(validator, result):
    result.directives = {"IDENTITY": {"Name": "Shop", "Currency": "12$"}}
    validator.validate(result)
    assert any("Invalid Currency" in e for e in result.errors)


def test_product_url_warning(validator, result):
    result.directives = {"PRODUCT": {"Name": "X"}}
    validator.validate(result)
    assert any("URL" in w for w in result.warnings)


def test_offer_required_fields_and_price_logic(validator, result):
    result.directives = {"OFFER": {"Price": "1e3"}}
    validator.validate(result)

    assert any("Availability" in e for e in result.errors)
    assert not any("Price must be numeric" in e for e in result.errors)

    result.directives["OFFER"]["Availability"] = "InStock"
    result.directives["OFFER"]["Price"] = "-5"
    validator.validate(result)

    assert any("cannot be negative" in e for e in result.errors)


def test_offer_condition_warning(validator, result):
    result.directives = {
        "OFFER": {"Availability": "InStock", "Price": "10", "Condition": "Alien"}
    }
    validator.validate(result)
    assert any("Non-standard Condition" in w for w in result.warnings)


# =========================================================
# TIER 2 – INVENTORY / REVIEWS / AGE / SUBSCRIPTION
# =========================================================


def test_inventory_stale_and_very_stale(validator, result):
    old = (datetime.now() - timedelta(days=4)).isoformat()
    very_old = (datetime.now() - timedelta(days=10)).isoformat()

    result.directives = {
        "IDENTITY": {"Name": "X", "Currency": "USD"},
        "INVENTORY": {"LastUpdated": old},
    }
    validator.validate(result)
    assert "inventory_stale" in result.trust_flags

    result.directives["INVENTORY"]["LastUpdated"] = very_old
    validator.validate(result)
    assert "inventory_very_stale" in result.trust_flags


def test_inventory_invalid_date_format(validator, result):
    result.directives["INVENTORY"] = {"LastUpdated": "not-a-date"}
    validator.validate(result)
    assert any("format error" in w for w in result.warnings)


def test_reviews_all_numeric_failures(validator, result):
    result.directives["REVIEWS"] = {
        "RatingScale": "Five",
        "Rating": "Great",
        "Count": "Many",
        "Source": "random-site.com",
    }
    validator.validate(result)

    assert any("RatingScale must be numeric" in e for e in result.errors)
    assert any("Rating must be numeric" in e for e in result.errors)
    assert any("Count must be numeric" in e for e in result.errors)
    assert "reviews_unverified" in result.trust_flags


def test_age_restriction_numeric_guard(validator, result):
    result.directives["AGE_RESTRICTION"] = {"MinimumAge": "NaN"}
    validator.validate(result)
    assert any("MinimumAge must be numeric" in e for e in result.errors)


def test_subscription_plans_structure(validator, result):
    result.directives["SUBSCRIPTION"] = {"Plans": "Invalid"}
    validator.validate(result)
    assert any("required Plans" in e for e in result.errors)


# =========================================================
# TIER 2 – LOCALES / EMPTY SECTIONS
# =========================================================


def test_locales_invalid_and_multiple_current(validator, result):
    result.directives["LOCALES"] = {
        "invalid-locale-123": "x",
        "en": "path (Current)",
        "bg": "path (Current)",
    }
    validator.validate(result)

    assert any("Invalid locale code" in w for w in result.warnings)
    assert any("Multiple locales" in e for e in result.errors)


def test_empty_sections_warnings(validator, result):
    for sec in ["SHIPPING", "PAYMENT", "POLICIES", "SPECS"]:
        result.directives[sec] = {}

    result.directives["IN_THE_BOX"] = {"items": []}

    validator.validate(result)

    assert any("section is empty" in w for w in result.warnings)


# =========================================================
# TIER 3 – IMAGES / COMPATIBILITY / VARIANTS
# =========================================================


def test_images_missing_main_and_alt_length(validator, result):
    result.directives["IMAGES"] = {"items": [{"name": "secondary", "Alt": "A" * 200}]}
    validator.validate(result)

    assert any("missing 'Main'" in w for w in result.warnings)
    assert any("Alt text too long" in w for w in result.warnings)


def test_compatibility_unknown_keys(validator, result):
    result.directives["COMPATIBILITY"] = {"WeirdKey": "X"}
    validator.validate(result)
    assert any("Unknown key" in w for w in result.warnings)


def test_variants_require_offer_and_price(validator, result):
    result.directives["VARIANTS"] = {"Options": []}
    validator.validate(result)
    assert any("used without @OFFER" in e for e in result.errors)


def test_variant_negative_price_math(validator, result):
    result.directives = {
        "OFFER": {"Price": "10", "Availability": "InStock"},
        "VARIANTS": {"Options": [{"name": "X", "path": "-20"}]},
    }
    validator.validate(result)
    assert any("negative price" in e for e in result.errors)


# =========================================================
# SEMANTIC LOGIC
# =========================================================


def test_semantic_logic_override_warning(validator, result):
    result.directives["SEMANTIC_LOGIC"] = {"items": ["override PRICE aggressively"]}
    validator.validate(result)
    assert any("Logic overrides facts" in w for w in result.warnings)


# =========================================================
# SYSTEM-LEVEL MOCKING (UNREACHABLE DEFENSIVE CODE)
# =========================================================


def test_datetime_internal_crash_mock(validator, result):
    result.directives["INVENTORY"] = {"LastUpdated": "2025-01-01"}
    with patch("commercetxt.validator.datetime") as mock_dt:
        mock_dt.fromisoformat.side_effect = Exception("boom")
        validator.validate(result)

    assert any("format error" in w for w in result.warnings)


def test_global_float_failure_mock(validator, result):
    result.directives["REVIEWS"] = {"RatingScale": "5", "Rating": "4"}
    with patch.object(builtins, "float", side_effect=ValueError("boom")):
        validator.validate(result)

    assert any("must be numeric" in e for e in result.errors)


def test_len_and_isinstance_conflict_mock(validator, result):
    class FakeShipping(dict):
        def get(self, key, default=None):
            return None

        def __len__(self):
            return 0

    result.directives = {
        "IDENTITY": {"Name": "Shop", "Currency": "USD"},
        "SHIPPING": FakeShipping(items=["x"]),
    }

    validator.validate(result)

    assert any("SHIPPING section is empty" in w for w in result.warnings)


def test_reviews_complex_numeric_failures(validator, result):
    # Trigger invalid float parsing
    result.directives["REVIEWS"] = {
        "RatingScale": "5.0",
        "Rating": "4.5.6",  # Invalid float
        "Count": "10.5",  # Float where Integer is expected
    }
    validator.validate(result)
    assert any("Rating must be numeric" in e for e in result.errors)
    assert any("Count must be numeric" in e for e in result.errors)

    # Trigger out-of-bounds rating
    result.directives["REVIEWS"] = {"RatingScale": "5", "Rating": "10"}
    validator.validate(result)
    assert any("outside allowed scale" in w for w in result.warnings)


def test_malformed_nested_types_coverage(validator, result):
    # SEMANTIC_LOGIC expecting list but gets string

    result.directives = {
        "OFFER": {"Price": "10", "Availability": "InStock"},
        "VARIANTS": {"Options": "JustAString"},
        "SEMANTIC_LOGIC": {"items": ["PRICE rule"]},
        "IMAGES": {"items": ["http://img.jpg"]},
    }

    validator.validate(result)
    assert any("Logic overrides facts" in w for w in result.warnings)
    assert any("missing 'Main'" in w for w in result.warnings)


def test_validator_deep_coverage(tmp_path, run_cli):  # Променено на run_cli
    """Hits specific validation guardrails in validator.py."""

    file_sub = tmp_path / "sub.txt"
    file_sub.write_text(
        "# @IDENTITY\nName: S\nCurrency: USD\n# @SUBSCRIPTION\nPlans: NotAList",
        encoding="utf-8",
    )
    run_cli([str(file_sub), "--validate"])

    file_img = tmp_path / "img.txt"
    file_img.write_text(
        "# @IDENTITY\nName: I\nCurrency: USD\n# @IMAGES\nitems:\n  - just_a_string_path.jpg",
        encoding="utf-8",
    )
    run_cli([str(file_img), "--validate"])

    file_box = tmp_path / "box.txt"
    file_box.write_text(
        "# @IDENTITY\nName: B\nCurrency: USD\n# @IN_THE_BOX\nitems: []",
        encoding="utf-8",
    )
    run_cli([str(file_box), "--validate"])
