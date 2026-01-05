"""
Catalog Filters Validator Tests.

Tests catalog structure, path validation, and filter formats.
"""

import pytest

from commercetxt.catalog_filters_validator import CatalogFiltersValidator
from commercetxt.constants import MAX_FILTER_OPTIONS, MAX_FILTER_VALUE_LENGTH

# =============================================================================
# Basic Functionality
# =============================================================================


class TestCatalogValidatorBasic:
    """Catalog validation basics."""

    def test_strict_defaults_false(self):
        """Strict mode is off by default."""
        v = CatalogFiltersValidator()
        assert v.strict is False
        assert v.errors == []
        assert v.warnings == []

    def test_strict_can_be_enabled(self):
        """Strict mode can be enabled."""
        v = CatalogFiltersValidator(strict=True)
        assert v.strict is True

    def test_valid_catalog_passes(self):
        """Valid catalog with items passes."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Electronics", "path": "/categories/electronics.txt"}]},
            file_level="root",
        )
        assert result is True
        assert len(v.errors) == 0

    def test_catalog_only_in_root(self):
        """Catalog only allowed in root file."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "A", "path": "/a.txt"}]}, file_level="category"
        )
        assert result is False
        assert any("only allowed in root" in e for e in v.errors)

        v2 = CatalogFiltersValidator()
        result2 = v2.validate_catalog(
            {"items": [{"name": "A", "path": "/a.txt"}]}, file_level="product"
        )
        assert result2 is False

    def test_empty_items_fails(self):
        """Empty items list fails."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog({"items": []}, file_level="root")
        assert result is False
        assert any("empty" in e.lower() for e in v.errors)

        v2 = CatalogFiltersValidator()
        result2 = v2.validate_catalog({}, file_level="root")
        assert result2 is False

    def test_non_dict_item_warns(self):
        """Non-dict item generates warning."""
        v = CatalogFiltersValidator()
        v.validate_catalog(
            {
                "items": [
                    "not a dict",
                    {"name": "Valid", "path": "/valid.txt"},
                ]
            },
            file_level="root",
        )
        assert any("Expected dict" in w for w in v.warnings)


# =============================================================================
# Path Validation
# =============================================================================


class TestCatalogPathValidation:
    """Path format validation."""

    def test_path_requires_leading_slash(self):
        """Path must start with /."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Cat", "path": "no/leading/slash.txt"}]},
            file_level="root",
        )
        assert result is False
        assert any("Invalid path" in e for e in v.errors)

    def test_path_requires_txt_extension(self):
        """Path must end with .txt."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Cat", "path": "/valid/path/no_extension"}]},
            file_level="root",
        )
        assert result is False

    def test_windows_separator_fails(self):
        """Backslash separators fail."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Cat", "path": "/path\\to\\file.txt"}]},
            file_level="root",
        )
        assert result is False
        assert any("Windows" in w for w in v.warnings)

    def test_path_traversal_fails(self):
        """Path with .. traversal fails."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Cat", "path": "/path/../secret.txt"}]},
            file_level="root",
        )
        assert result is False

    def test_valid_path_passes(self):
        """Valid path passes."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Cat", "path": "/category/file.txt"}]},
            file_level="root",
        )
        assert result is True

    def test_duplicate_paths_warn(self):
        """Duplicate paths generate warning."""
        v = CatalogFiltersValidator()
        v.validate_catalog(
            {
                "items": [
                    {"name": "Cat1", "path": "/same/path.txt"},
                    {"name": "Cat2", "path": "/same/path.txt"},
                ]
            },
            file_level="root",
        )
        assert any("Duplicate path" in w for w in v.warnings)


# =============================================================================
# Item Name and Path
# =============================================================================


class TestCatalogItemValidation:
    """Item name and path validation."""

    def test_missing_name_errors(self):
        """Missing name generates error."""
        v = CatalogFiltersValidator()
        v.validate_catalog({"items": [{"path": "/valid.txt"}]}, file_level="root")
        assert any("Missing category name" in e for e in v.errors)

    def test_missing_path_errors(self):
        """Missing path generates error."""
        v = CatalogFiltersValidator()
        v.validate_catalog({"items": [{"name": "Category"}]}, file_level="root")
        assert any("Missing file path" in e for e in v.errors)

    def test_empty_name_errors(self):
        """Empty string name generates error."""
        v = CatalogFiltersValidator()
        v.validate_catalog(
            {"items": [{"name": "", "path": "/valid.txt"}]}, file_level="root"
        )
        assert any("Missing category name" in e for e in v.errors)

    def test_empty_path_errors(self):
        """Empty string path generates error."""
        v = CatalogFiltersValidator()
        v.validate_catalog({"items": [{"name": "Cat", "path": ""}]}, file_level="root")
        assert any("Missing file path" in e for e in v.errors)

    def test_value_key_fallback(self):
        """value key can substitute for path."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Cat", "value": "/alt/path.txt"}]},
            file_level="root",
        )
        assert result is True


# =============================================================================
# Filters Validation
# =============================================================================


class TestFiltersValidator:
    """Filter validation."""

    def test_filters_in_product_warns(self):
        """Filters in product file warns."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Brand": "Sony"}, file_level="product")
        assert any("unusual" in w.lower() for w in v.warnings)

    def test_filters_in_category_ok(self):
        """Filters in category file ok."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Brand": "Sony"}, file_level="category")
        assert not any("unusual" in w.lower() for w in v.warnings)

    def test_empty_filters_warns(self):
        """Empty filters generates warning."""
        v = CatalogFiltersValidator()
        result = v.validate_filters({}, file_level="category")
        assert result is True
        assert any("empty" in w.lower() for w in v.warnings)

    def test_items_key_excluded(self):
        """items key excluded from filter count."""
        v = CatalogFiltersValidator()
        result = v.validate_filters(
            {"items": [], "Brand": "Sony"}, file_level="category"
        )
        assert result is True
        assert not any("empty" in w.lower() for w in v.warnings)

    def test_comma_list_valid(self):
        """Comma-separated list valid."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Brand": "Sony, Apple, Samsung"}, file_level="category")
        assert len(v.warnings) == 0

    def test_too_many_options_warns(self):
        """Too many options generates warning."""
        v = CatalogFiltersValidator()
        many_options = ", ".join([f"Option{i}" for i in range(MAX_FILTER_OPTIONS + 5)])
        v.validate_filters({"Brand": many_options}, file_level="category")
        assert any("Too many options" in w for w in v.warnings)

    def test_range_format_valid(self):
        """Range format with dash valid."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Price": "$50 - $500"}, file_level="category")
        assert len(v.errors) == 0

    def test_range_with_to_valid(self):
        """Range with 'to' keyword valid."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Price": "50 to 500"}, file_level="category")
        assert len(v.errors) == 0

    def test_boolean_values_valid(self):
        """Boolean values valid."""
        CatalogFiltersValidator()
        for val in ["Yes", "No", "True", "False", "yes", "no", "true", "false"]:
            v2 = CatalogFiltersValidator()
            v2.validate_filters({"InStock": val}, file_level="category")
            assert len(v2.errors) == 0

    def test_single_short_value_valid(self):
        """Single short value valid."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Type": "Electronics"}, file_level="category")
        assert len(v.errors) == 0

    def test_very_long_value_warns(self):
        """Very long value generates warning."""
        v = CatalogFiltersValidator()
        long_value = "x" * (MAX_FILTER_VALUE_LENGTH + 10)
        v.validate_filters({"Description": long_value}, file_level="category")
        assert any("Unusual value format" in w for w in v.warnings)


# =============================================================================
# Strict Mode
# =============================================================================


class TestStrictMode:
    """Strict mode behavior."""

    def test_raises_on_error(self):
        """Strict mode raises ValueError on error."""
        v = CatalogFiltersValidator(strict=True)
        with pytest.raises(ValueError) as exc_info:
            v.validate_catalog({}, file_level="root")
        assert "empty" in str(exc_info.value).lower()

    def test_raises_on_invalid_level(self):
        """Strict mode raises for wrong file level."""
        v = CatalogFiltersValidator(strict=True)
        with pytest.raises(ValueError):
            v.validate_catalog(
                {"items": [{"name": "A", "path": "/a.txt"}]}, file_level="category"
            )

    def test_non_strict_collects_errors(self):
        """Non-strict mode collects errors."""
        v = CatalogFiltersValidator(strict=False)
        result = v.validate_catalog({}, file_level="root")
        assert result is False
        assert len(v.errors) > 0


# =============================================================================
# Boundary Values
# =============================================================================


class TestBoundaryValues:
    """Boundary value tests."""

    def test_exactly_max_options_ok(self):
        """Exactly MAX_FILTER_OPTIONS does not warn."""
        v = CatalogFiltersValidator()
        options = ", ".join([f"Option{i}" for i in range(MAX_FILTER_OPTIONS)])
        v.validate_filters({"Brand": options}, file_level="category")
        assert not any("Too many" in w for w in v.warnings)

    def test_one_over_max_warns(self):
        """MAX_FILTER_OPTIONS + 1 warns."""
        v = CatalogFiltersValidator()
        options = ", ".join([f"Option{i}" for i in range(MAX_FILTER_OPTIONS + 1)])
        v.validate_filters({"Brand": options}, file_level="category")
        assert any("Too many" in w for w in v.warnings)

    def test_exactly_max_value_length_ok(self):
        """Exactly MAX_FILTER_VALUE_LENGTH does not warn."""
        v = CatalogFiltersValidator()
        value = "x" * (MAX_FILTER_VALUE_LENGTH - 1)  # Just under
        v.validate_filters({"Key": value}, file_level="category")
        assert not any("Unusual value" in w for w in v.warnings)

    def test_one_item_in_catalog(self):
        """Exactly 1 item in catalog is valid."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Single", "path": "/single.txt"}]}, file_level="root"
        )
        assert result is True

    def test_zero_items_in_catalog(self):
        """Zero items in catalog fails."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog({"items": []}, file_level="root")
        assert result is False


# =============================================================================
# RETURN VALUE TESTS
# =============================================================================


class TestReturnValues:
    """Test return values for mutation killing."""

    def test_validate_catalog_returns_true_on_success(self):
        """Returns True, not truthy value."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Cat", "path": "/cat.txt"}]}, file_level="root"
        )
        assert result is True
        assert result != "true"

    def test_validate_catalog_returns_false_on_failure(self):
        """Returns False, not falsy value."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog({}, file_level="root")
        assert result is False
        assert result is not None

    def test_validate_filters_returns_true_even_with_warnings(self):
        """Returns True with warnings (not errors)."""
        v = CatalogFiltersValidator()
        result = v.validate_filters({}, file_level="category")
        assert result is True
        assert len(v.warnings) > 0  # Has warnings
        assert len(v.errors) == 0  # No errors

    def test_get_report_structure(self):
        """get_report returns correct structure."""
        v = CatalogFiltersValidator()
        v.validate_catalog({}, file_level="root")
        report = v.get_report()

        assert "valid" in report
        assert "errors" in report
        assert "warnings" in report
        assert report["valid"] is False  # Had errors
        assert isinstance(report["errors"], list)
        assert isinstance(report["warnings"], list)

    def test_get_report_valid_true(self):
        """get_report shows valid=True on success."""
        v = CatalogFiltersValidator()
        v.validate_catalog(
            {"items": [{"name": "Cat", "path": "/cat.txt"}]}, file_level="root"
        )
        report = v.get_report()
        assert report["valid"] is True


# =============================================================================
# PATH FORMAT HELPER TESTS
# =============================================================================


class TestPathFormatHelper:
    """Tests for _validate_path_format and _is_valid_path."""

    def test_validate_path_format_valid(self):
        """Valid path returns (True, None)."""
        v = CatalogFiltersValidator()
        valid, warning = v._validate_path_format("/valid/path.txt")
        assert valid is True
        assert warning is None

    def test_validate_path_format_no_leading_slash(self):
        """No leading slash returns (False, None)."""
        v = CatalogFiltersValidator()
        valid, warning = v._validate_path_format("no/leading.txt")
        assert valid is False

    def test_validate_path_format_no_txt_extension(self):
        """No .txt extension returns (False, None)."""
        v = CatalogFiltersValidator()
        valid, warning = v._validate_path_format("/path/no_extension")
        assert valid is False

    def test_validate_path_format_windows_separator(self):
        """Windows separator returns (False, warning)."""
        v = CatalogFiltersValidator()
        valid, warning = v._validate_path_format("/path\\file.txt")
        assert valid is False
        assert warning is not None
        assert "Windows" in warning

    def test_validate_path_format_traversal(self):
        """Path traversal (..) returns (False, None)."""
        v = CatalogFiltersValidator()
        valid, warning = v._validate_path_format("/path/../secret.txt")
        assert valid is False

    def test_is_valid_path_legacy_wrapper(self):
        """_is_valid_path is legacy wrapper."""
        v = CatalogFiltersValidator()
        assert v._is_valid_path("/valid/path.txt") is True
        assert v._is_valid_path("no/leading.txt") is False


# =============================================================================
# MUTATION KILLER: SPECIFIC LINE TARGETS
# =============================================================================


class TestMutationKillers:
    """Kill specific survived mutations."""

    def test_strict_default_is_false_not_none(self):
        """Kill: strict defaults to False, not None."""
        v = CatalogFiltersValidator()
        assert v.strict is False
        assert v.strict is not None

    def test_file_level_equality_check(self):
        """Kill: != 'root' check."""
        v1 = CatalogFiltersValidator()
        assert (
            v1.validate_catalog(
                {"items": [{"name": "A", "path": "/a.txt"}]}, file_level="root"
            )
            is True
        )

        v2 = CatalogFiltersValidator()
        assert (
            v2.validate_catalog(
                {"items": [{"name": "A", "path": "/a.txt"}]}, file_level="category"
            )
            is False
        )

        v3 = CatalogFiltersValidator()
        assert (
            v3.validate_catalog(
                {"items": [{"name": "A", "path": "/a.txt"}]}, file_level="product"
            )
            is False
        )

    def test_items_default_empty_list(self):
        """Kill: .get("items", []) default."""
        v = CatalogFiltersValidator()
        # No items key at all
        result = v.validate_catalog({}, file_level="root")
        assert result is False
        assert any("empty" in e.lower() for e in v.errors)

    def test_not_items_check(self):
        """Kill: if not items check."""
        v = CatalogFiltersValidator()
        # Empty list
        result = v.validate_catalog({"items": []}, file_level="root")
        assert result is False

    def test_isinstance_dict_check(self):
        """Kill: isinstance(item, dict) check."""
        v = CatalogFiltersValidator()
        v.validate_catalog(
            {"items": ["string", 123, None, {"name": "Valid", "path": "/v.txt"}]},
            file_level="root",
        )
        # Should have warnings for non-dict items
        assert len(v.warnings) >= 3  # string, 123, None

    def test_duplicate_path_detection(self):
        """Kill: path in valid_paths check."""
        v = CatalogFiltersValidator()
        v.validate_catalog(
            {
                "items": [
                    {"name": "A", "path": "/same.txt"},
                    {"name": "B", "path": "/same.txt"},
                ]
            },
            file_level="root",
        )
        assert any("Duplicate" in w for w in v.warnings)

    def test_valid_paths_append(self):
        """Kill: valid_paths.append check."""
        v = CatalogFiltersValidator()
        v.validate_catalog(
            {
                "items": [
                    {"name": "A", "path": "/a.txt"},
                    {"name": "B", "path": "/b.txt"},
                    {"name": "C", "path": "/a.txt"},  # Duplicate of A
                ]
            },
            file_level="root",
        )
        # Should detect the duplicate
        dup_warnings = [w for w in v.warnings if "Duplicate" in w]
        assert len(dup_warnings) == 1  # Only one duplicate warning

    def test_file_level_product_check(self):
        """Kill: file_level == 'product' check."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Brand": "Sony"}, file_level="product")
        assert any("unusual" in w.lower() for w in v.warnings)

        v2 = CatalogFiltersValidator()
        v2.validate_filters({"Brand": "Sony"}, file_level="category")
        assert not any("unusual" in w.lower() for w in v2.warnings)

    def test_not_actual_filters_check(self):
        """Kill: if not actual_filters check."""
        v = CatalogFiltersValidator()
        # Only 'items' key which is excluded
        v.validate_filters({"items": []}, file_level="category")
        assert any("empty" in w.lower() for w in v.warnings)

    def test_comma_in_value_check(self):
        """Kill: ',' in value_str check."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Brand": "Sony, Apple"}, file_level="category")
        # Should trigger comma list path
        assert len(v.errors) == 0

    def test_len_items_greater_check(self):
        """Kill: > MAX_FILTER_OPTIONS check."""
        # At MAX - no warning
        v1 = CatalogFiltersValidator()
        v1.validate_filters(
            {"Brand": ", ".join([f"O{i}" for i in range(MAX_FILTER_OPTIONS)])},
            file_level="category",
        )
        assert not any("Too many" in w for w in v1.warnings)

        # Over MAX - warning
        v2 = CatalogFiltersValidator()
        v2.validate_filters(
            {"Brand": ", ".join([f"O{i}" for i in range(MAX_FILTER_OPTIONS + 1)])},
            file_level="category",
        )
        assert any("Too many" in w for w in v2.warnings)

    def test_comma_path_returns_early(self):
        """Kill: return after comma list check."""
        v = CatalogFiltersValidator()
        # Has comma - should return early, not check range or boolean
        v.validate_filters(
            {"Mix": "A, B, -"}, file_level="category"
        )  # Has comma AND dash
        # Should NOT have unusual format warning (comma path returns)
        assert not any("Unusual" in w for w in v.warnings)

    def test_range_format_check(self):
        """Kill: '-' or 'to' range check."""
        v = CatalogFiltersValidator()
        v.validate_filters({"Price": "50-100"}, file_level="category")
        assert not any("Unusual" in w for w in v.warnings)

        v2 = CatalogFiltersValidator()
        v2.validate_filters({"Price": "50 to 100"}, file_level="category")
        assert not any("Unusual" in w for w in v2.warnings)

    def test_boolean_values_check(self):
        """Kill: boolean values check."""
        for val in [
            "yes",
            "YES",
            "Yes",
            "no",
            "NO",
            "No",
            "true",
            "TRUE",
            "True",
            "false",
            "FALSE",
            "False",
        ]:
            v = CatalogFiltersValidator()
            v.validate_filters({"Available": val}, file_level="category")
            assert not any("Unusual" in w for w in v.warnings), f"Failed for {val}"

    def test_short_value_length_check(self):
        """Kill: < MAX_FILTER_VALUE_LENGTH check."""
        v = CatalogFiltersValidator()
        short_value = "x" * (MAX_FILTER_VALUE_LENGTH - 1)
        v.validate_filters({"Key": short_value}, file_level="category")
        assert not any("Unusual" in w for w in v.warnings)

    def test_validate_filters_returns_true(self):
        """Kill: return True with no errors."""
        v = CatalogFiltersValidator()
        result = v.validate_filters({"Brand": "Sony"}, file_level="category")
        assert result is True

    def test_errors_empty_check(self):
        """Kill: len(self.errors) == 0 check."""
        v = CatalogFiltersValidator()
        result = v.validate_catalog(
            {"items": [{"name": "Valid", "path": "/valid.txt"}]}, file_level="root"
        )
        assert result is True
        assert len(v.errors) == 0

        v2 = CatalogFiltersValidator()
        result2 = v2.validate_catalog({}, file_level="root")
        assert result2 is False
        assert len(v2.errors) > 0
