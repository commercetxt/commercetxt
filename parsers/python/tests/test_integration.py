"""
Integration tests for CommerceTXT.
Test the whole. Verify the parts.
"""

import pytest
from datetime import datetime, timedelta

from commercetxt import ParseResult
from commercetxt.parser import CommerceTXTParser
from commercetxt.validator import CommerceTXTValidator
from commercetxt.resolver import CommerceTXTResolver


def test_full_pipeline_root_to_product():
    """Run the complete flow. Parse, validate, and merge root with product."""
    parser = CommerceTXTParser()
    validator = CommerceTXTValidator()
    resolver = CommerceTXTResolver()

    # 1. Root context.
    root_content = """
# @IDENTITY
Name: Global Store
Currency: USD

# @SHIPPING
- Standard: Free over $50
"""
    root = parser.parse(root_content)
    validator.validate(root)

    # 2. Product context.
    product_content = """
# @PRODUCT
Name: Widget
SKU: W123

# @OFFER
Price: 29.99
Availability: InStock
"""
    product = parser.parse(product_content)
    validator.validate(product)

    # 3. Inheritance. Merge contexts.
    merged = resolver.merge(root, product)

    # 4. Verify the merge.
    assert merged.directives["IDENTITY"]["Name"] == "Global Store"
    assert merged.directives["OFFER"]["Price"] == "29.99"
    assert "SHIPPING" in merged.directives

    shipping_items = merged.directives["SHIPPING"]["items"]
    assert len(shipping_items) > 0
    assert shipping_items[0]["name"] == "Standard"


def test_malformed_input_recovery():
    """Parser must recover from junk lines. Stay resilient."""
    parser = CommerceTXTParser(strict=False)

    content = """
# @IDENTITY
Name: Store
~~~GARBAGE LINE 1~~~
Currency: USD

# @OFFER
Invalid syntax here!!!
Price: 10.00
Availability: InStock
"""
    result = parser.parse(content)

    # Valid parts should remain intact.
    assert result.directives["IDENTITY"]["Name"] == "Store"
    assert result.directives["IDENTITY"]["Currency"] == "USD"
    assert result.directives["OFFER"]["Price"] == "10.00"

    # Garbage lines should trigger warnings.
    assert len(result.warnings) >= 2
    assert "Unknown syntax" in result.warnings[0]


def test_validator_strict_mode():
    """Strict mode must raise an exception on negative prices."""
    parser = CommerceTXTParser()
    validator = CommerceTXTValidator(strict=True)

    # Valid identity but negative price.
    content = """
# @IDENTITY
Name: Store
Currency: USD
# @OFFER
Price: -50.00
Availability: InStock
"""
    result = parser.parse(content)

    with pytest.raises(ValueError) as excinfo:
        validator.validate(result)

    # Hemingway style: Check for the core message.
    assert "@OFFER Price cannot be negative" in str(excinfo.value)


def test_locale_resolution_logic():
    """Test locale matching. Exact match first, then language, then root."""
    root_result = ParseResult(
        directives={
            "LOCALES": {
                "en-US": "/commerce.txt (Current)",
                "en-GB": "/uk/commerce.txt",
                "fr": "/fr/commerce.txt",
                "de-DE": "/de/commerce.txt",
            }
        }
    )

    resolver = CommerceTXTResolver()

    # Exact match.
    path = resolver.resolve_locales(root_result, "fr")
    assert path == "/fr/commerce.txt"

    # Language fallback.
    path = resolver.resolve_locales(root_result, "fr-CA")
    assert path == "/fr/commerce.txt"

    # Default fallback.
    path = resolver.resolve_locales(root_result, "ja-JP")
    assert path == "/"


def test_tier3_variants_structure():
    """Verify complex nested structures like Variants."""
    parser = CommerceTXTParser(nested=True)

    content = """
# @VARIANTS
Type: Storage
Options:
  - 128GB: 999.00 | SKU: A1
  - 256GB: 1099.00 | SKU: A2
"""
    result = parser.parse(content)

    variants = result.directives.get("VARIANTS", {})
    options = variants.get("Options", [])

    assert len(options) == 2
    assert options[0]["name"] == "128GB"

    # Values following a colon in a list are mapped to 'path'.
    assert options[0]["path"] == "999.00"
    assert options[0]["SKU"] == "A1"


def test_circular_reference_safety():
    """Ensure merging is idempotent. Corrupt no data."""
    parser = CommerceTXTParser()
    resolver = CommerceTXTResolver()

    base_content = "# @IDENTITY\nName: Base"
    base = parser.parse(base_content)

    merged_once = resolver.merge(base, base)
    assert merged_once.directives["IDENTITY"]["Name"] == "Base"

    merged_twice = resolver.merge(merged_once, base)
    assert merged_twice.directives["IDENTITY"]["Name"] == "Base"


def test_real_world_complex_product():
    """Validate a complete real-world scenario."""
    parser = CommerceTXTParser(nested=True)
    validator = CommerceTXTValidator()

    content = """
# @IDENTITY
Name: TechStore
Currency: USD

# @PRODUCT
Name: Pro Laptop 2024
SKU: PRO-2024
URL: http://example.com/pro-laptop

# @OFFER
Price: 1999.00
Availability: InStock
Condition: New

# @IMAGES
- Main: http://example.com/img1.jpg
- Side: http://example.com/img2.jpg

# @SPECS
- CPU: M3 Max
- RAM: 32GB

# @VARIANTS
Options:
  - 1TB SSD: +0
  - 2TB SSD: +400.00
"""
    result = parser.parse(content)

    validator.validate(result)
    assert not result.errors

    assert result.directives["SPECS"]["items"][0]["name"] == "CPU"
    assert result.directives["VARIANTS"]["Options"][1]["path"] == "+400.00"


def test_full_tier_compliance():
    """Test full spec compliance using a robust data string."""
    parser = CommerceTXTParser()
    validator = CommerceTXTValidator()

    content = """
# @IDENTITY
Name: Demo Store
Currency: USD
# @OFFER
Price: 348.00
Availability: InStock
# @VARIANTS
Options:
  - Color: Black
  - Color: Silver
"""
    result = parser.parse(content)
    validator.validate(result)

    assert not result.errors
    assert "VARIANTS" in result.directives
    assert result.directives["OFFER"]["Price"] == "348.00"


def test_inventory_trust_flags_propagation():
    """Test that stale inventory data triggers trust flags."""

    parser = CommerceTXTParser()
    validator = CommerceTXTValidator()

    content = f"""
# @IDENTITY
Name: Store
Currency: USD

# @INVENTORY
LastUpdated: {(datetime.now() - timedelta(days=10)).isoformat()}
"""
    result = parser.parse(content)
    validator.validate(result)

    assert "inventory_very_stale" in result.trust_flags


def test_offer_partial_override():
    """Test that product-level OFFER overrides root-level OFFER partially."""

    parser = CommerceTXTParser()
    resolver = CommerceTXTResolver()
    validator = CommerceTXTValidator()

    root = parser.parse(
        """
# @IDENTITY
Name: Store
Currency: USD
# @OFFER
Price: 100
Availability: InStock
"""
    )

    product = parser.parse(
        """
# @PRODUCT
Name: Item
# @OFFER
Price: 80
"""
    )

    validator.validate(root)
    validator.validate(product)

    merged = resolver.merge(root, product)

    assert merged.directives["OFFER"]["Price"] == "80"
    assert merged.directives["OFFER"]["Availability"] == "InStock"


def test_reviews_unverified_trust_flag():
    """Test that unverified reviews trigger the correct trust flag."""
    parser = CommerceTXTParser()
    validator = CommerceTXTValidator()

    content = """
# @REVIEWS
RatingScale: 5
Rating: 4.5
Source: some-random-site.com
"""
    result = parser.parse(content)
    validator.validate(result)

    assert "reviews_unverified" in result.trust_flags


def test_semantic_logic_merge_behavior():
    """Test that SEMANTIC_LOGIC directives are merged correctly."""
    parser = CommerceTXTParser()
    resolver = CommerceTXTResolver()
    validator = CommerceTXTValidator()

    root = parser.parse(
        """
# @SEMANTIC_LOGIC
- override price dynamically
"""
    )

    product = parser.parse(
        """
# @OFFER
Price: 100
Availability: InStock
"""
    )

    validator.validate(root)
    validator.validate(product)

    merged = resolver.merge(root, product)

    assert "SEMANTIC_LOGIC" in merged.directives
    assert any("Logic overrides facts" in w for w in merged.warnings)


def test_inventory_merge_consistency():
    """Test that INVENTORY directives are merged and trust flags set."""
    parser = CommerceTXTParser()
    resolver = CommerceTXTResolver()
    validator = CommerceTXTValidator()

    root = parser.parse(
        """
# @IDENTITY
Name: Store
Currency: USD
# @INVENTORY
LastUpdated: 2020-01-01
"""
    )

    product = parser.parse(
        """
# @PRODUCT
Name: Item
"""
    )

    validator.validate(root)
    validator.validate(product)

    merged = resolver.merge(root, product)

    assert "INVENTORY" in merged.directives
    assert "inventory_very_stale" in merged.trust_flags
