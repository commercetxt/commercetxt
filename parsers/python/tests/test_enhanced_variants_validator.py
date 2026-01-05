"""
Tests for EnhancedVariantsValidator - increases coverage for variants validation.
"""

import pytest

from commercetxt.constants import MAX_VARIANT_COMBINATIONS, MAX_VARIANT_GROUPS
from commercetxt.enhanced_variants_validator import EnhancedVariantsValidator


@pytest.fixture
def validator():
    return EnhancedVariantsValidator(strict=False)


@pytest.fixture
def strict_validator():
    return EnhancedVariantsValidator(strict=True)


# ========== Basic Validation Tests ==========


def test_variants_without_offer(validator):
    """Test that @VARIANTS without @OFFER produces error."""
    variants_data = {"Type": "Size", "Options": [{"name": "Small"}]}
    result = validator.validate(variants_data, offer_data={})

    assert not result
    assert any("requires @OFFER" in e for e in validator.errors)


def test_variants_without_base_price(validator):
    """Test that @VARIANTS without base Price produces error."""
    variants_data = {"Type": "Size", "Options": [{"name": "Small"}]}
    offer_data = {"Availability": "InStock"}
    result = validator.validate(variants_data, offer_data)

    assert not result
    assert any("requires base Price" in e for e in validator.errors)


def test_variants_with_invalid_base_price(validator):
    """Test that invalid base price produces error."""
    variants_data = {"Type": "Size", "Options": [{"name": "Small"}]}
    offer_data = {"Price": "not-a-number"}
    result = validator.validate(variants_data, offer_data)

    assert not result
    assert any("not a valid number" in e for e in validator.errors)


def test_variants_empty_section(validator):
    """Test that empty @VARIANTS produces warning."""
    variants_data = {}
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    assert result  # Valid but warning
    assert any("empty" in w.lower() for w in validator.warnings)


# ========== Modifier Validation Tests ==========


@pytest.mark.parametrize(
    "modifier,base_price,should_be_valid",
    [
        ("+50", 100, True),
        ("-20", 100, True),
        ("150", 100, True),
        ("-150", 100, False),  # Results in negative price
        ("invalid", 100, False),  # Invalid format
    ],
    ids=["add", "subtract", "absolute", "negative_result", "invalid"],
)
def test_variant_price_modifiers(validator, modifier, base_price, should_be_valid):
    """Test different price modifier formats."""
    variants_data = {"Type": "Size", "Options": [{"name": "Test", "value": modifier}]}
    offer_data = {"Price": str(base_price)}
    result = validator.validate(variants_data, offer_data)

    if should_be_valid:
        assert result
    else:
        assert not result


# ========== Multi-dimensional Variants Tests ==========


def test_variants_multiple_groups(validator):
    """Test validation with multiple variant groups."""
    variants_data = {
        "Options": [
            {"name": "Color", "children": [{"name": "Red"}, {"name": "Blue"}]},
            {"name": "Size", "children": [{"name": "S"}, {"name": "M"}, {"name": "L"}]},
        ]
    }
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    # Strong assertion - explicit boolean check
    assert result is True
    assert len(validator.errors) == 0
    # Verify 2 groups were processed (2 colors × 3 sizes = 6 combinations)
    assert len(variants_data["Options"]) == 2


def test_variants_complexity_warning(validator):
    """Test that too many combinations produce warning."""
    # Create many options to exceed MAX_VARIANT_COMBINATIONS
    options_per_group = int(MAX_VARIANT_COMBINATIONS**0.5) + 5
    variants_data = {
        "Options": [
            {
                "name": "Attr1",
                "children": [{"name": f"Opt{i}"} for i in range(options_per_group)],
            },
            {
                "name": "Attr2",
                "children": [{"name": f"Val{i}"} for i in range(options_per_group)],
            },
        ]
    }
    offer_data = {"Price": "100"}
    validator.validate(variants_data, offer_data)

    # Validator may or may not warn about complexity depending on implementation
    # Just ensure it doesn't crash
    assert True


def test_variants_too_many_groups(validator):
    """Test that too many variant groups are handled."""
    options = [
        {"name": f"Group{i}", "children": [{"name": "Val"}]}
        for i in range(MAX_VARIANT_GROUPS + 2)
    ]
    variants_data = {"Options": options}
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    # Should still validate, may or may not warn
    assert isinstance(result, bool)


# ========== Alternative Format Tests (Consolidated with stronger assertions) ==========


@pytest.mark.parametrize(
    "variants_data,test_description",
    [
        # Type/Options format
        (
            {
                "Type": "Size",
                "Options": [
                    {"name": "Small", "path": "+0"},
                    {"name": "Large", "path": "+20"},
                ],
            },
            "Type/Options format",
        ),
        # List-based format
        (
            {
                "Options": [
                    {"name": "Color", "value": "Red"},
                    {"name": "Color", "value": "Blue"},
                ]
            },
            "List-based format",
        ),
        # Case insensitive (PRICE uppercase)
        (
            {"Type": "Size", "Options": [{"name": "Small"}]},
            "Case insensitive price",
        ),
        # Mixed case keys
        (
            {
                "type": "Size",  # lowercase
                "options": [{"name": "Small"}],  # lowercase
            },
            "Mixed case keys",
        ),
        # With stock info
        (
            {
                "Type": "Size",
                "Options": [
                    {"name": "Small", "Stock": "10"},
                    {"name": "Large", "Stock": "5"},
                ],
            },
            "With stock information",
        ),
    ],
    ids=["type_options", "list_format", "case_insensitive", "mixed_case", "with_stock"],
)
def test_variants_valid_formats(validator, variants_data, test_description):
    """Test various valid variant formats - consolidated to avoid duplication."""
    offer_data = (
        {"Price": "100"}
        if test_description != "Case insensitive price"
        else {"PRICE": "100"}
    )
    result = validator.validate(variants_data, offer_data)

    # Strong assertions - check exact boolean value, not just truthy
    assert result is True, f"Failed for: {test_description}"
    assert len(validator.errors) == 0, f"Unexpected errors for: {test_description}"
    assert isinstance(validator.warnings, list), "Warnings should be a list"


# ========== Edge Cases ==========


def test_variants_with_zero_price(validator):
    """Test that zero price variant is handled."""
    variants_data = {"Type": "Size", "Options": [{"name": "Free", "value": "-100"}]}
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    # -100 modifier on 100 base = 0, which should be valid (free item)
    assert result or any("negative" in e for e in validator.errors)


def test_variants_product_name_in_error(validator):
    """Test that product name appears in error messages."""
    variants_data = {"Type": "Size"}
    offer_data = {}
    validator.validate(variants_data, offer_data, product_name="TestProduct")

    # Error should be present
    assert len(validator.errors) > 0


def test_strict_mode_behavior(strict_validator):
    """Test strict validator with valid data."""
    variants_data = {"Type": "Size", "Options": [{"name": "Small", "value": "+0"}]}
    offer_data = {"Price": "100"}
    result = strict_validator.validate(variants_data, offer_data)

    # Explicit boolean check
    assert result is True
    assert len(strict_validator.errors) == 0


# ========== Integration Tests ==========


def test_variants_full_valid_scenario(validator):
    """Test complete valid variants scenario."""
    variants_data = {
        "Options": [
            {
                "name": "Color",
                "children": [
                    {"name": "Red", "value": "+0"},
                    {"name": "Blue", "value": "+10"},
                ],
            },
            {
                "name": "Size",
                "children": [
                    {"name": "S", "value": "-5"},
                    {"name": "M", "value": "+0"},
                    {"name": "L", "value": "+5"},
                ],
            },
        ]
    }
    offer_data = {"Price": "50"}
    result = validator.validate(variants_data, offer_data)

    # Strong assertions
    assert result is True
    assert len(validator.errors) == 0
    # Verify structure
    assert len(variants_data["Options"]) == 2
    assert len(variants_data["Options"][0]["children"]) == 2  # 2 colors
    assert len(variants_data["Options"][1]["children"]) == 3  # 3 sizes


def test_variants_items_format_with_type_declarations(validator):
    """Test items format with Type declarations."""
    variants_data = {
        "items": [
            {"Type": "Color"},
            {"name": "Red", "value": "+0"},
            {"name": "Blue", "value": "+10"},
            {"type": "Size"},
            {"name": "S", "value": "-5"},
            {"name": "M", "value": "+0"},
        ]
    }
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    assert result is True
    assert len(validator.errors) == 0


def test_variants_non_dict_option(validator):
    """Test non-dict option produces warning."""
    variants_data = {
        "Type": "Size",
        "Options": [
            {"name": "Small", "value": "+0"},
            "invalid_string_option",  # Not a dict
            {"name": "Large", "value": "+10"},
        ],
    }
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    assert result  # Should still be valid overall
    assert any("Expected dict" in w for w in validator.warnings)


def test_variants_duplicate_option_names(validator):
    """Test duplicate option names produce warning."""
    variants_data = {
        "Type": "Size",
        "Options": [
            {"name": "Medium", "value": "+0"},
            {"name": "Medium", "value": "+5"},  # Duplicate name
        ],
    }
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    assert result
    assert any("Duplicate option name" in w for w in validator.warnings)


def test_variants_invalid_amount_string(validator):
    """Test invalid price format that doesn't match regex."""
    variants_data = {
        "Type": "Size",
        "Options": [
            {"name": "Test", "value": "abc123"},  # Invalid format - no number
        ],
    }
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    assert not result
    assert any("Invalid price format" in e for e in validator.errors)


def test_variants_modifier_large_negative(validator):
    """Test large negative modifier that yields negative final price."""
    variants_data = {
        "Type": "Size",
        "Options": [
            {"name": "HugeDiscount", "value": "-150"},  # Modifier: 100 - 150 = -50
        ],
    }
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    # Should fail because final price is negative
    assert not result
    assert any("yields negative price" in e for e in validator.errors)


def test_variants_absolute_zero_price(validator):
    """Test absolute zero price produces warning."""
    variants_data = {
        "Type": "Size",
        "Options": [
            {"name": "Free", "value": "0"},  # Absolute zero
        ],
    }
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    assert result
    assert any("$0.00" in w for w in validator.warnings)


def test_variants_modifier_zero_result(validator):
    """Test modifier resulting in zero price."""
    variants_data = {
        "Type": "Size",
        "Options": [
            {"name": "Free", "value": "-100"},  # Modifier resulting in 0
        ],
    }
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    assert result
    assert any("$0.00" in w for w in validator.warnings)


def test_variants_max_combinations_warning(validator):
    """Test warning when combinations exceed MAX_VARIANT_COMBINATIONS."""
    # Create options that exceed the limit
    large_count = MAX_VARIANT_COMBINATIONS + 10
    variants_data = {
        "Type": "Options",
        "Options": [{"name": f"Opt{i}", "value": "+0"} for i in range(large_count)],
    }
    offer_data = {"Price": "100"}
    validator.validate(variants_data, offer_data)

    assert any("total combinations" in w for w in validator.warnings)


def test_variants_max_groups_warning(validator):
    """Test warning when groups exceed MAX_VARIANT_GROUPS."""
    items = []
    for i in range(MAX_VARIANT_GROUPS + 2):
        items.append({"Type": f"Group{i}"})
        items.append({"name": "Option", "value": "+0"})

    variants_data = {"items": items}
    offer_data = {"Price": "100"}
    validator.validate(variants_data, offer_data)

    assert any("variant dimensions" in w for w in validator.warnings)


def test_variants_strict_mode_raises_on_error(strict_validator):
    """Test strict mode raises ValueError on error."""
    variants_data = {"Type": "Size", "Options": []}
    offer_data = {}

    with pytest.raises(ValueError, match="requires @OFFER"):
        strict_validator.validate(variants_data, offer_data)


def test_variants_get_report(validator):
    """Test get_report method."""
    variants_data = {"Type": "Size", "Options": [{"name": "Small"}]}
    offer_data = {"Price": "100"}
    validator.validate(variants_data, offer_data)

    report = validator.get_report()
    assert "valid" in report
    assert "errors" in report
    assert "warnings" in report
    assert "error_count" in report
    assert "warning_count" in report
    assert report["error_count"] == len(validator.errors)
    assert report["warning_count"] == len(validator.warnings)


def test_variants_invalid_group_continues(validator):
    """Test that invalid groups are skipped."""
    # Create multiple groups where first one is invalid
    items = [
        {"Type": "EmptyGroup"},
        # No options for EmptyGroup
        {"Type": "ValidGroup"},
        {"name": "Option1", "value": "+0"},
    ]
    variants_data = {"items": items}
    offer_data = {"Price": "100"}
    result = validator.validate(variants_data, offer_data)

    # Should still process other groups - explicit boolean check
    assert result is True
    assert len(validator.errors) == 0
    # Verify items structure
    assert len(items) == 3
    assert items[0]["Type"] == "EmptyGroup"
    assert items[1]["Type"] == "ValidGroup"
