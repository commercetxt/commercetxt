"""
Tests for ProductComparator - intelligent product comparison.

"""

import pytest

from commercetxt.rag.tools.comparator import ProductComparator


class TestProductComparator:
    """Test suite for ProductComparator class."""

    @pytest.fixture
    def comparator(self):
        """Create a fresh comparator instance for each test."""
        return ProductComparator()

    # ========== Price Comparison Tests ==========

    @pytest.mark.parametrize(
        "price_a,price_b,expected_advantage,expected_savings",
        [
            (100, 150, "a", "$50.00 cheaper"),
            (200, 100, "b", "$100.00 cheaper"),
            (100, 100, None, None),  # Equal prices
            (0, 50, "a", "$50.00 cheaper"),
            (50, 0, "b", "$50.00 cheaper"),
        ],
        ids=["a_cheaper", "b_cheaper", "equal", "a_zero", "b_zero"],
    )
    def test_price_comparison(
        self, comparator, price_a, price_b, expected_advantage, expected_savings
    ):
        """Test price comparison logic."""
        product_a = {"PRICE": price_a, "SPECS": {}}
        product_b = {"PRICE": price_b, "SPECS": {}}

        result = comparator.compare(product_a, product_b)

        assert result["price_advantage"] == expected_advantage
        if expected_savings:
            assert result["savings"] == expected_savings
        else:
            assert result["savings"] is None

    # ========== Spec Comparison Tests ==========

    def test_spec_differences_detected(self, comparator):
        """Test that spec differences are properly detected and reported."""
        product_a = {
            "PRICE": 100,
            "SPECS": {"RAM": "8 GB", "Storage": "256 GB", "Color": "Black"},
        }
        product_b = {
            "PRICE": 120,
            "SPECS": {"RAM": "16 GB", "Storage": "512 GB", "Color": "Black"},
        }

        result = comparator.compare(product_a, product_b)

        # Should have differences for RAM and Storage, not for Color
        diff_attrs = [d["attribute"] for d in result["spec_differences"]]
        assert "RAM" in diff_attrs
        assert "Storage" in diff_attrs
        assert "Color" not in diff_attrs  # Same value

    def test_missing_spec_advantage(self, comparator):
        """Test that N/A specs are handled correctly."""
        product_a = {"PRICE": 100, "SPECS": {"Battery": "4000 mAh"}}
        product_b = {"PRICE": 100, "SPECS": {}}  # Missing Battery

        result = comparator.compare(product_a, product_b)

        battery_diff = next(
            (d for d in result["spec_differences"] if d["attribute"] == "Battery"), None
        )
        assert battery_diff is not None
        assert battery_diff["product_b"] == "N/A"
        assert battery_diff["advantage"] == "a"

    def test_missing_spec_advantage_reverse(self, comparator):
        """Test N/A advantage when product A is missing spec."""
        product_a = {"PRICE": 100, "SPECS": {}}
        product_b = {"PRICE": 100, "SPECS": {"Feature": "Value"}}

        result = comparator.compare(product_a, product_b)

        diff = next(
            (d for d in result["spec_differences"] if d["attribute"] == "Feature"), None
        )
        assert diff is not None
        assert diff["product_a"] == "N/A"
        assert diff["advantage"] == "b"

    # ========== Advantage Detection Tests ==========

    @pytest.mark.parametrize(
        "attribute,value_a,value_b,expected_advantage",
        [
            # Higher is better attributes
            ("Battery", "5000 mAh", "4000 mAh", "a"),
            ("RAM", "16 GB", "8 GB", "a"),
            ("Storage", "256 GB", "512 GB", "b"),
            ("Screen", "6.5 inch", "5.5 inch", "a"),
            ("Camera", "50 MP", "12 MP", "a"),
            ("Resolution", "1920x1080", "1280x720", "a"),
            # Lower is better attributes
            ("Weight", "150 g", "200 g", "a"),
            ("Price", "100", "150", "a"),
            ("Thickness", "7.5 mm", "9 mm", "a"),
            ("Latency", "10 ms", "20 ms", "a"),
            # Neutral attributes (no preference)
            ("Color", "Red", "Blue", "neutral"),
            ("Model", "X1", "X2", "neutral"),
        ],
        ids=[
            "battery_higher_wins",
            "ram_higher_wins",
            "storage_higher_wins",
            "screen_higher_wins",
            "camera_higher_wins",
            "resolution_higher_wins",
            "weight_lower_wins",
            "price_lower_wins",
            "thickness_lower_wins",
            "latency_lower_wins",
            "color_neutral",
            "model_neutral",
        ],
    )
    def test_advantage_detection(
        self, comparator, attribute, value_a, value_b, expected_advantage
    ):
        """Test smart advantage detection based on attribute type."""
        product_a = {"PRICE": 100, "SPECS": {attribute: value_a}}
        product_b = {"PRICE": 100, "SPECS": {attribute: value_b}}

        result = comparator.compare(product_a, product_b)

        if result["spec_differences"]:
            diff = result["spec_differences"][0]
            assert diff["advantage"] == expected_advantage

    def test_equal_numeric_values_neutral(self, comparator):
        """Test that equal numeric values return neutral advantage."""
        product_a = {"PRICE": 100, "SPECS": {"RAM": "8 GB"}}
        product_b = {"PRICE": 100, "SPECS": {"RAM": "8 GB"}}

        result = comparator.compare(product_a, product_b)

        # Same values = no differences
        assert len(result["spec_differences"]) == 0

    def test_non_numeric_values_neutral(self, comparator):
        """Test that non-numeric values return neutral advantage."""
        product_a = {"PRICE": 100, "SPECS": {"Material": "Aluminum"}}
        product_b = {"PRICE": 100, "SPECS": {"Material": "Plastic"}}

        result = comparator.compare(product_a, product_b)

        diff = result["spec_differences"][0]
        assert diff["advantage"] == "neutral"

    def test_invalid_numeric_parsing(self, comparator):
        """Test handling of values that look numeric but aren't."""
        product_a = {"PRICE": 100, "SPECS": {"Version": "v2.0"}}
        product_b = {"PRICE": 100, "SPECS": {"Version": "v1.0"}}

        result = comparator.compare(product_a, product_b)

        diff = result["spec_differences"][0]
        # Should be neutral since version strings aren't pure numbers
        assert diff["advantage"] in ["neutral", "a"]  # 2 > 1 if parsed as numbers

    # ========== Recommendation Generation Tests ==========

    @pytest.mark.parametrize(
        "price_a,price_b,expected_recommendation",
        [
            (50, 100, "Product A offers better value for money."),
            (100, 50, "Product B is the premium choice."),
            (100, 100, "Both products are competitive."),
        ],
        ids=["a_cheaper", "b_cheaper", "equal"],
    )
    def test_recommendation_generation(
        self, comparator, price_a, price_b, expected_recommendation
    ):
        """Test recommendation generation based on price advantage."""
        product_a = {"PRICE": price_a, "SPECS": {}}
        product_b = {"PRICE": price_b, "SPECS": {}}

        result = comparator.compare(product_a, product_b)

        assert result["recommendation"] == expected_recommendation

    # ========== Edge Cases ==========

    def test_empty_specs(self, comparator):
        """Test comparison with empty SPECS."""
        product_a = {"PRICE": 100, "SPECS": {}}
        product_b = {"PRICE": 100, "SPECS": {}}

        result = comparator.compare(product_a, product_b)

        assert result["spec_differences"] == []
        assert result["winner"] is None

    def test_missing_specs_key(self, comparator):
        """Test comparison when SPECS key is missing."""
        product_a = {"PRICE": 100}
        product_b = {"PRICE": 100}

        result = comparator.compare(product_a, product_b)

        assert result["spec_differences"] == []

    def test_missing_price_key(self, comparator):
        """Test comparison when PRICE key is missing."""
        product_a = {"SPECS": {"RAM": "8 GB"}}
        product_b = {"SPECS": {"RAM": "16 GB"}}

        result = comparator.compare(product_a, product_b)

        # Should default to 0 for missing prices
        assert result["price_advantage"] is None  # Both 0

    def test_unique_features_structure(self, comparator):
        """Test that unique_features dict is properly structured."""
        product_a = {"PRICE": 100, "SPECS": {}}
        product_b = {"PRICE": 100, "SPECS": {}}

        result = comparator.compare(product_a, product_b)

        assert "unique_features" in result
        assert "a" in result["unique_features"]
        assert "b" in result["unique_features"]
        assert isinstance(result["unique_features"]["a"], list)
        assert isinstance(result["unique_features"]["b"], list)

    def test_complex_comparison(self, comparator):
        """Test a realistic product comparison."""
        phone_a = {
            "PRICE": 799,
            "SPECS": {
                "Display": "6.1 inch OLED",
                "RAM": "8 GB",
                "Storage": "128 GB",
                "Battery": "4000 mAh",
                "Weight": "174 g",
                "Camera": "48 MP",
            },
        }
        phone_b = {
            "PRICE": 999,
            "SPECS": {
                "Display": "6.7 inch OLED",
                "RAM": "12 GB",
                "Storage": "256 GB",
                "Battery": "5000 mAh",
                "Weight": "195 g",
                "Camera": "50 MP",
            },
        }

        result = comparator.compare(phone_a, phone_b)

        # Phone A should have price advantage
        assert result["price_advantage"] == "a"
        assert "$200.00 cheaper" in result["savings"]

        # Check spec differences exist
        assert len(result["spec_differences"]) > 0

        # Verify recommendation
        assert "value" in result["recommendation"].lower()
