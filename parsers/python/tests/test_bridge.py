"""
CommerceAIBridge Tests.

Tests prompt generation, readiness scoring, and field handling.
Covers defaults, boundaries, collections, type validation.
"""

import pytest

from commercetxt.bridge import CommerceAIBridge
from commercetxt.constants import (
    DEFAULT_AVAILABILITY,
    DEFAULT_CURRENCY,
    DEFAULT_ITEM_NAME,
    DEFAULT_PRICE,
    DEFAULT_STORE_NAME,
    GRADE_B_THRESHOLD,
    MAX_SPECS_DISPLAY,
    MAX_VARIANT_OPTIONS_DISPLAY,
    PENALTY_MISSING_OFFER,
    PENALTY_MISSING_VERSION,
    PENALTY_PER_ERROR,
)
from commercetxt.model import ParseResult

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def result():
    """Standard ParseResult with minimal valid data."""
    return ParseResult(
        directives={
            "IDENTITY": {"Name": "Store", "Currency": "USD"},
            "PRODUCT": {"Name": "Widget"},
            "OFFER": {
                "Price": "10",
                "Availability": "InStock",
                "URL": "http://buy.com",
            },
        }
    )


@pytest.fixture
def bridge(result):
    """Bridge with standard result."""
    return CommerceAIBridge(result)


# =============================================================================
# Prompt Generation
# =============================================================================


class TestPromptGeneration:
    """Prompt output contains required sections."""

    def test_core_sections_present(self, bridge):
        """Store, item, price, URL appear in prompt."""
        prompt = bridge.generate_low_token_prompt()
        assert "STORE: Store" in prompt
        assert "ITEM: Widget" in prompt
        assert "PRICE: 10" in prompt
        assert "URL: http://buy.com" in prompt

    def test_empty_directives_yield_empty_prompt(self):
        """No data produces no output."""
        bridge = CommerceAIBridge(ParseResult(directives={}))
        assert not bridge.generate_low_token_prompt().strip()

    def test_empty_section_dicts_return_early(self, result):
        """Empty section dicts produce no headers."""
        result.directives = {"IDENTITY": {}, "PRODUCT": {}, "OFFER": {}}
        assert not CommerceAIBridge(result).generate_low_token_prompt().strip()


# =============================================================================
# Optional Fields
# =============================================================================


class TestOptionalFields:
    """None and empty values are omitted from output."""

    @pytest.mark.parametrize(
        "section,field,label",
        [
            ("PRODUCT", "SKU", "SKU:"),
            ("PRODUCT", "Brand", "BRAND:"),
            ("OFFER", "Condition", "CONDITION:"),
            ("REVIEWS", "TopTags", "TAGS:"),
        ],
    )
    def test_none_omitted(self, result, section, field, label):
        """None values do not generate labels."""
        result.directives[section] = {field: None}
        assert label not in CommerceAIBridge(result).generate_low_token_prompt()

    @pytest.mark.parametrize(
        "section,field,label",
        [
            ("PRODUCT", "SKU", "SKU:"),
            ("PRODUCT", "Brand", "BRAND:"),
            ("OFFER", "Condition", "CONDITION:"),
        ],
    )
    def test_empty_string_omitted(self, result, section, field, label):
        """Empty strings do not generate labels."""
        result.directives[section] = {field: ""}
        assert label not in CommerceAIBridge(result).generate_low_token_prompt()

    def test_zero_string_valid(self, result):
        """String '0' is valid and appears in output."""
        result.directives["PRODUCT"] = {"Name": "P", "SKU": "0"}
        assert "SKU: 0" in CommerceAIBridge(result).generate_low_token_prompt()

    def test_integer_values_convert(self, bridge):
        """Integer values convert to string."""
        lines = []
        bridge._add_product(lines, {"Name": "T", "SKU": 999, "Brand": 999})
        content = "\n".join(lines)
        assert "SKU: 999" in content
        assert "BRAND: 999" in content


# =============================================================================
# Default Values
# =============================================================================


class TestDefaults:
    """Missing fields use defined defaults."""

    @pytest.mark.parametrize(
        "section,field,default,prefix",
        [
            ("IDENTITY", "Name", DEFAULT_STORE_NAME, "STORE:"),
            ("IDENTITY", "Currency", DEFAULT_CURRENCY, "CURRENCY:"),
            ("PRODUCT", "Name", DEFAULT_ITEM_NAME, "ITEM:"),
            ("OFFER", "Price", DEFAULT_PRICE, "PRICE:"),
            ("OFFER", "Availability", DEFAULT_AVAILABILITY, "AVAILABILITY:"),
        ],
    )
    def test_defaults_applied(self, result, section, field, default, prefix):
        """Missing field triggers default value."""
        if section not in result.directives:
            result.directives[section] = {}
        result.directives[section]["__dummy__"] = True
        result.directives[section].pop(field, None)
        assert (
            f"{prefix} {default}"
            in CommerceAIBridge(result).generate_low_token_prompt()
        )


# =============================================================================
# Inventory
# =============================================================================


class TestInventory:
    """Stock display handles boundaries and types."""

    def test_zero_displayed(self, bridge):
        """Zero stock is valid."""
        lines = []
        bridge._add_inventory(lines, {"Stock": 0})
        assert "STOCK: 0 units" in lines

    def test_positive_displayed(self, bridge):
        """Positive stock works."""
        lines = []
        bridge._add_inventory(lines, {"Stock": "10"})
        assert any("STOCK: 10 units" in l for l in lines)

    def test_float_displayed(self, bridge):
        """Float stock converts correctly."""
        lines = []
        bridge._add_inventory(lines, {"Stock": "10.5"})
        assert "STOCK: 10.5 units" in lines

    def test_negative_rejected(self, bridge):
        """Negative stock invalid."""
        lines = []
        bridge._add_inventory(lines, {"Stock": -1})
        assert not lines

    def test_non_numeric_rejected(self, bridge):
        """Non-numeric stock invalid."""
        lines = []
        bridge._add_inventory(lines, {"Stock": "many"})
        assert not lines

    def test_list_rejected(self, bridge):
        """List type invalid."""
        lines = []
        bridge._add_inventory(lines, {"Stock": [1, 2]})
        assert "STOCK:" not in "\n".join(lines)

    def test_dict_rejected(self, bridge):
        """Dict type invalid."""
        lines = []
        bridge._add_inventory(lines, {"Stock": {"v": 5}})
        assert "STOCK:" not in "\n".join(lines)


# =============================================================================
# Reviews
# =============================================================================


class TestReviews:
    """Reviews require both rating and count."""

    def test_rating_alone_rejected(self, bridge):
        """Rating alone produces no output."""
        lines = []
        bridge._add_reviews(lines, {"Rating": "5"})
        assert "RATING:" not in "\n".join(lines)

    def test_count_alone_rejected(self, bridge):
        """Count alone produces no output."""
        lines = []
        bridge._add_reviews(lines, {"Count": "10"})
        assert "RATING:" not in "\n".join(lines)

    def test_empty_rating_rejected(self, bridge):
        """Empty rating with count produces no output."""
        lines = []
        bridge._add_reviews(lines, {"Rating": "", "Count": "10"})
        assert "RATING:" not in "\n".join(lines)

    def test_both_present_works(self, bridge):
        """Valid rating and count produce output."""
        lines = []
        bridge._add_reviews(lines, {"Rating": "5", "Count": "10"})
        assert "RATING: 5/5 (10 reviews)" in "\n".join(lines)


# =============================================================================
# Variants
# =============================================================================


class TestVariants:
    """Variant options handle type validation."""

    def test_string_rejected(self, bridge):
        """String instead of list rejected."""
        lines = []
        bridge._add_variants(lines, {"Options": "not a list"})
        assert lines == []

    def test_none_rejected(self, bridge):
        """None options rejected."""
        lines = []
        bridge._add_variants(lines, {"Options": None})
        assert lines == []

    def test_empty_list_rejected(self, bridge):
        """Empty list rejected."""
        lines = []
        bridge._add_variants(lines, {"Options": []})
        assert lines == []

    def test_mixed_types_handled(self, bridge):
        """Non-dict items skipped without crash."""
        options = [{"name": "Red"}, "Blue", {"name": "Green"}, None]
        lines = []
        bridge._add_variants(lines, {"Options": options})
        content = "\n".join(lines)
        assert "Red" in content
        assert "Green" in content

    def test_truncation_shows_count(self, result):
        """Excess variants show remaining count."""
        opts = [{"name": f"O{i}"} for i in range(MAX_VARIANT_OPTIONS_DISPLAY + 5)]
        result.directives["VARIANTS"] = {"Options": opts}
        assert "(+5 more)" in CommerceAIBridge(result).generate_low_token_prompt()


# =============================================================================
# Collections
# =============================================================================


class TestCollections:
    """Specs and shipping respect limits."""

    def test_specs_truncated(self, result):
        """Only MAX_SPECS_DISPLAY specs appear."""
        specs = {f"k{i}": f"v{i}" for i in range(MAX_SPECS_DISPLAY + 2)}
        result.directives["SPECS"] = specs
        prompt = CommerceAIBridge(result).generate_low_token_prompt()
        assert f"k{MAX_SPECS_DISPLAY - 1}:" in prompt
        assert f"k{MAX_SPECS_DISPLAY}:" not in prompt

    def test_shipping_non_list_rejected(self, bridge):
        """Shipping items must be list."""
        lines = []
        bridge._add_shipping(lines, {"items": "Free"})
        assert "SHIPPING:" not in "\n".join(lines)

    def test_shipping_empty_rejected(self, bridge):
        """Empty shipping list rejected."""
        lines = []
        bridge._add_shipping(lines, {"items": []})
        assert "SHIPPING:" not in "\n".join(lines)


# =============================================================================
# Readiness Score
# =============================================================================


class TestReadinessScore:
    """Score calculation with penalties and grades."""

    def test_full_score(self, result):
        """Complete data with version scores 100."""
        result.version = "1.0.0"
        assert CommerceAIBridge(result).calculate_readiness_score()["score"] == 100

    def test_missing_version_penalty(self, result):
        """No version subtracts penalty."""
        result.version = None
        assert (
            CommerceAIBridge(result).calculate_readiness_score()["score"]
            == 100 - PENALTY_MISSING_VERSION
        )

    def test_missing_offer_penalty(self, result):
        """Empty offer subtracts penalty."""
        result.version = None
        result.directives["OFFER"] = {}
        expected = 100 - PENALTY_MISSING_VERSION - PENALTY_MISSING_OFFER
        assert CommerceAIBridge(result).calculate_readiness_score()["score"] == expected

    def test_error_penalties(self, result):
        """Each error subtracts penalty."""
        result.version = None
        result.directives["OFFER"] = {}
        result.errors = ["E1", "E2"]
        expected = (
            100
            - PENALTY_MISSING_VERSION
            - PENALTY_MISSING_OFFER
            - (2 * PENALTY_PER_ERROR)
        )
        assert CommerceAIBridge(result).calculate_readiness_score()["score"] == expected

    def test_score_clamped_at_zero(self):
        """Score never negative."""
        result = ParseResult(directives={"OFFER": {}})
        result.errors = ["E"] * 10
        assert CommerceAIBridge(result).calculate_readiness_score()["score"] == 0

    def test_stale_inventory_issue(self, result):
        """Stale flag adds issue."""
        result.version = "1.0"
        result.trust_flags = ["inventory_stale"]
        score = CommerceAIBridge(result).calculate_readiness_score()
        assert any("Stale" in i for i in score["issues"])

    def test_grade_a(self, result):
        """Score > 90 gets grade A."""
        result.version = "1.0.0"
        assert CommerceAIBridge(result).calculate_readiness_score()["grade"] == "A"

    def test_grade_b(self, result):
        """Score 71-90 gets grade B."""
        result.version = "1.0.0"
        result.errors = ["E1"]
        assert CommerceAIBridge(result).calculate_readiness_score()["grade"] == "B"

    def test_grade_c(self, result):
        """Score <= 70 gets grade C."""
        result.version = "1.0.0"
        result.directives["OFFER"] = {}
        res = CommerceAIBridge(result).calculate_readiness_score()
        assert res["score"] == GRADE_B_THRESHOLD
        assert res["grade"] == "C"


# =============================================================================
# Complex Directives
# =============================================================================


class TestComplexDirectives:
    """Promos, compatibility, images, logic, voice, shipping."""

    def test_all_sections_render(self, result):
        """All complex directive types render."""
        result.directives.update(
            {
                "PROMOS": {"items": [{"name": "S10", "value": "10%"}]},
                "COMPATIBILITY": {"WorksWith": "USB-C"},
                "IMAGES": {"items": [{"name": "Main", "Alt": "Front"}]},
                "SEMANTIC_LOGIC": {"items": [{"name": "Q", "path": "A"}]},
                "BRAND_VOICE": {"Tone": "Bold"},
                "AGE_RESTRICTION": {"MinimumAge": "18"},
                "SHIPPING": {"items": [{"name": "Exp", "path": "Air"}]},
            }
        )
        prompt = CommerceAIBridge(result).generate_low_token_prompt()
        assert "S10: 10%" in prompt
        assert "COMPATIBILITY:" in prompt
        assert "Q -> A" in prompt
        assert "TONE_OF_VOICE: Bold" in prompt
        assert "Restricted to ages 18+" in prompt

    def test_ai_logic_string_items(self, result):
        """String items in SEMANTIC_LOGIC work."""
        result.directives["SEMANTIC_LOGIC"] = {"items": ["Rule One"]}
        prompt = CommerceAIBridge(result).generate_low_token_prompt()
        assert "- Rule One" in prompt


# =============================================================================
# Internal Methods
# =============================================================================


class TestInternalMethods:
    """Internal methods return None."""

    def test_add_methods_return_none(self, bridge):
        """All _add_* return None."""
        lines = []
        assert bridge._add_identity(lines, {"Name": "S"}) is None
        assert bridge._add_product(lines, {"Name": "P"}) is None
        assert bridge._add_offer(lines, {"Price": "10"}) is None
        assert bridge._add_inventory(lines, {"Stock": "5"}) is None
        assert bridge._add_specs(lines, {"Color": "R"}) is None

    def test_empty_dict_no_output(self, bridge):
        """Empty dict produces no output."""
        lines = []
        bridge._add_identity(lines, {})
        assert lines == []
        bridge._add_product(lines, {})
        assert lines == []
        bridge._add_offer(lines, {})
        assert lines == []
