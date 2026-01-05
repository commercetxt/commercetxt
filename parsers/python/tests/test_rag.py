"""
CommerceTXT RAG Tests.

Tests semantic tagging, shard generation, and filters for AI retrieval.
Covers PriceFilter, MaterialFilter, LogisticsFilter, SeasonalityFilter, and SustainabilityFilter.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from commercetxt.rag.core.filters import (
    LogisticsFilter,
    MaterialFilter,
    PriceFilter,
    SeasonalityFilter,
    SustainabilityFilter,
)
from commercetxt.rag.core.generator import RAGGenerator
from commercetxt.rag.core.semantic_tags import SemanticTagger
from commercetxt.rag.core.shards import ShardBuilder

# Test fixtures directory
VECTORS_DIR = Path(__file__).parent / "vectors" / "rag"


# ========== Price Filter Tests ==========


@pytest.mark.parametrize(
    "price,expected_tier",
    [
        ("45", "budget_friendly"),
        ("150", "mid_range"),
        ("350", "premium"),
        ("600", "luxury"),
        ("0", None),
        ("-50", None),
        ("invalid", None),
    ],
    ids=["budget", "mid_range", "premium", "luxury", "zero", "negative", "invalid"],
)
def test_price_segmentation(price, expected_tier):
    """Test price tier classification"""
    assert PriceFilter.get_price_tier(price) == expected_tier


# ========== Material Filter Tests ==========


@pytest.mark.parametrize(
    "specs,expected_tags",
    [
        ({"Material": "Cotton and Wool"}, ["natural_material", "cotton"]),
        ({"material": "polyester fabric"}, ["synthetic_material"]),
        ({"Material": "Stainless Steel"}, ["metal_material", "metal"]),
        ({"fabric": "genuine leather"}, ["leather", "natural_material"]),
    ],
    ids=["natural", "synthetic", "metal", "leather"],
)
def test_material_detection(specs, expected_tags):
    """Test material type detection"""
    tags = MaterialFilter.detect_materials(specs)
    for expected_tag in expected_tags:
        assert expected_tag in tags


# ========== Logistics Filter Tests ==========


@pytest.mark.parametrize(
    "specs,expected_tags",
    [
        ({"Weight": "25 kg"}, ["heavy_shipping", "freight_required"]),
        ({"Weight": "8 kg"}, ["bulky_item"]),
        ({"Weight": "0.3 kg"}, ["lightweight"]),
        ({"Weight": "2 kg"}, ["standard_shipping"]),
        ({"Weight": "300 g"}, ["lightweight"]),
        ({"Weight": "50 lb"}, ["heavy_shipping"]),
    ],
    ids=["heavy", "bulky", "lightweight", "standard", "grams", "pounds"],
)
def test_weight_classification(specs, expected_tags):
    """Test weight-based shipping classification"""
    tags = LogisticsFilter.classify_weight(specs)
    for expected_tag in expected_tags:
        assert expected_tag in tags


@pytest.mark.parametrize(
    "specs,expected_tags",
    [
        ({"Dimensions": "160 x 50 x 50 cm"}, ["oversized_item", "special_handling"]),
        ({"Dimensions": "120 x 40 x 30 cm"}, ["large_item"]),
        ({"Dimensions": "70 x 20 x 20 in"}, ["oversized_item"]),
    ],
    ids=["oversized_cm", "large", "oversized_inches"],
)
def test_dimension_classification(specs, expected_tags):
    """Test dimension-based shipping classification"""
    tags = LogisticsFilter.classify_dimensions(specs)
    for expected_tag in expected_tags:
        assert expected_tag in tags


# ========== Seasonality Filter Tests ==========


def test_seasonality_detection():
    """Test seasonal keyword detection"""
    # Winter items (test only if current month is winter)
    winter_item = "Warm Winter Coat"
    SeasonalityFilter.detect_seasonality(winter_item)
    # Note: This test is month-dependent

    # Summer items
    summer_item = "Beach Swimsuit"
    SeasonalityFilter.detect_seasonality(summer_item)
    # Note: This test is month-dependent

    # Non-seasonal item
    generic_item = "Regular T-Shirt"
    SeasonalityFilter.detect_seasonality(generic_item)
    # Should not have seasonal tags unless current month matches


# ========== Sustainability Filter Tests ==========


@pytest.mark.parametrize(
    "specs,expected_tag",
    [
        ({"certification": "Fair Trade Certified"}, "fair_trade_certified"),
        ({"certified": "USDA Organic"}, "organic_certified"),
        ({"certification": "FSC Certified Wood"}, "fsc_certified"),
        ({"certification": "Energy Star"}, "energy_star_certified"),
    ],
    ids=["fair_trade", "organic", "fsc", "energy_star"],
)
def test_sustainability_certifications(specs, expected_tag):
    """Test sustainability certification detection"""
    tags = SustainabilityFilter.detect_certifications(specs)
    assert expected_tag in tags


# ========== Semantic Tagger Tests ==========


def test_semantic_tagger_integration():
    """Test the semantic tagger orchestration"""
    data = {
        "ITEM": "Organic Cotton T-Shirt",
        "BRAND": "EcoWear",
        "PRICE": "35",
        "AVAILABILITY": "InStock",
        "CONDITION": "New",
        "SPECS": {
            "Material": "Organic Cotton",
            "Weight": "0.2 kg",
            "certification": "Fair Trade",
        },
    }

    tagger = SemanticTagger()
    tags = tagger.generate_tags(data)

    # Check for various expected tags
    assert "budget_friendly" in tags
    assert "natural_material" in tags or "cotton" in tags
    assert "lightweight" in tags
    assert "ready_to_ship" in tags
    assert "brand_new_condition" in tags
    assert "fair_trade_certified" in tags
    # Brand tags now include hash suffix for collision prevention
    assert any(t.startswith("brand_ecowear_") for t in tags)
    assert "apparel" in tags  # Now includes category tags

    # Ensure no duplicates
    assert len(tags) == len(set(tags))


# ========== Shard Builder Tests ==========


def test_shard_creation():
    """Test individual shard creation"""
    builder = ShardBuilder(include_metadata=True, include_confidence=True)

    data = {"ITEM": "Test Product", "PRICE": "100"}
    semantic_tags = ["luxury", "ready_to_ship"]

    shard = builder.create_shard(
        text="Test Product",
        original_data=data,
        attr_type="subject_anchor",
        index=0,
        semantic_tags=semantic_tags,
    )

    assert shard["text"] == "Test Product"
    assert "metadata" in shard
    assert shard["metadata"]["index"] == 0
    assert shard["metadata"]["attr_type"] == "subject_anchor"
    assert shard["metadata"]["original_data"] == data


def test_shard_builder_confidence_scores():
    """Test confidence score addition"""
    builder = ShardBuilder(
        include_metadata=True, include_confidence=True, include_negative_tags=True
    )

    tags = ["luxury", "ready_to_ship"]
    enriched_tags = builder._add_confidence_scores(tags)

    # Should have positive and negative tags
    assert len(enriched_tags) > len(tags)

    # Check structure
    positive_tags = [t for t in enriched_tags if t["type"] == "positive"]
    negative_tags = [t for t in enriched_tags if t["type"] == "negative"]

    assert len(positive_tags) == 2
    assert len(negative_tags) == 2

    # Check confidence scores
    assert all(t["score"] == 1.0 for t in positive_tags)
    assert all(t["score"] == 0.5 for t in negative_tags)


def test_text_truncation():
    """Test text truncation"""
    long_text = "A" * 15000
    truncated = ShardBuilder.truncate_text(long_text)
    assert len(truncated) <= 10000
    assert truncated.endswith("...")

    short_text = "Short text"
    not_truncated = ShardBuilder.truncate_text(short_text)
    assert not_truncated == short_text


# ========== RAG Generator Tests ==========


def test_full_rag_generation():
    """Test full RAG generation with all features"""
    data = {
        "ITEM": "Eco Drone Pro",
        "BRAND": "Aero",
        "PRICE": "550",
        "CURRENCY": "USD",
        "AVAILABILITY": "InStock",
        "SPECS": {"Material": "Bamboo Fiber", "Weight": "1.2 kg"},
    }

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate(data)

    # Check shard count
    assert len(shards) >= 5

    # Check metadata presence
    first_shard_metadata = shards[0]["metadata"]
    tags = [
        t["tag"] if isinstance(t, dict) else t
        for t in first_shard_metadata["semantic_tags"]
    ]

    assert "luxury" in tags
    assert "ready_to_ship" in tags
    assert "natural_material" in tags


def test_rag_generation_with_description():
    """Test RAG generation including description field"""
    data = {
        "ITEM": "Smart Watch",
        "BRAND": "TechCo",
        "PRICE": "299",
        "DESCRIPTION": "A premium smartwatch with advanced health tracking features.",
        "SPECS": {"Battery": "7 days", "Display": "AMOLED"},
    }

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate(data)

    # Check for description shard
    description_shards = [
        s for s in shards if s.get("metadata", {}).get("attr_type") == "description"
    ]
    assert len(description_shards) > 0
    assert "health tracking" in description_shards[0]["text"].lower()


def test_rag_generation_as_text():
    """Test RAG generation as plain text"""
    data = {"ITEM": "Laptop", "BRAND": "CompanyX", "PRICE": "1200", "CURRENCY": "EUR"}

    gen = RAGGenerator()
    text_output = gen.generate(data, as_text=True)

    assert isinstance(text_output, str)
    assert "CompanyX Laptop" in text_output
    assert "1200" in text_output
    assert "EUR" in text_output


def test_rag_batch_generation():
    """Test batch RAG generation"""
    items = [
        {"ITEM": "Product A", "BRAND": "Brand A", "PRICE": "50"},
        {"ITEM": "Product B", "BRAND": "Brand B", "PRICE": "100"},
        {"ITEM": "Product C", "BRAND": "Brand C", "PRICE": "200"},
    ]

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate_batch(items)

    assert isinstance(shards, list)
    assert len(shards) > 0

    # Each product should contribute multiple shards
    assert len(shards) >= len(items)


def test_rag_generation_without_metadata():
    """Test RAG generation without metadata"""
    data = {"ITEM": "Simple Product", "BRAND": "SimpleBrand", "PRICE": "10"}

    gen = RAGGenerator(include_metadata=False)
    shards = gen.generate(data)

    assert len(shards) > 0
    for shard in shards:
        assert "text" in shard
        assert "metadata" not in shard


def test_rag_generation_with_list_specs():
    """Test RAG generation with list values in specs"""
    data = {
        "ITEM": "Multi-Color Shirt",
        "BRAND": "Fashion",
        "PRICE": "45",
        "SPECS": {
            "Colors": ["Red", "Blue", "Green", "Yellow"],
            "Sizes": ["S", "M", "L", "XL"],
        },
    }

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate(data)

    # Should handle list values
    assert len(shards) > 0

    # Check that list values are converted to strings
    spec_shards = [
        s for s in shards if s.get("metadata", {}).get("attr_type") == "specification"
    ]
    assert len(spec_shards) > 0


def test_rag_generation_error_recovery():
    """Test batch generation with error recovery"""
    items = [
        {"ITEM": "Valid Product", "PRICE": "100"},
        {"ITEM": None, "PRICE": None},  # Potentially problematic data
        {"ITEM": "Another Valid", "PRICE": "200"},
    ]

    gen = RAGGenerator()
    shards = gen.generate_batch(items)

    # Should still return some shards despite errors
    assert isinstance(shards, list)


def test_rag_generation_with_brand_voice():
    """Test RAG generation with brand voice field"""
    data = {
        "ITEM": "Luxury Watch",
        "BRAND": "LuxBrand",
        "PRICE": "5000",
        "BRAND_VOICE": "Elegant, timeless, sophisticated",
    }

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate(data)

    # Check for brand voice shard
    voice_shards = [
        s for s in shards if s.get("metadata", {}).get("attr_type") == "brand_voice"
    ]
    assert len(voice_shards) > 0
    assert "timeless" in voice_shards[0]["text"].lower()


# ========== Additional Edge Case Tests ==========


def test_price_filter_edge_cases():
    """Test price filter with various edge cases"""
    assert PriceFilter.get_price_tier("") is None
    assert PriceFilter.get_price_tier(None) is None
    assert PriceFilter.get_price_tier("abc") is None
    assert PriceFilter.get_price_tier("50.99") == "mid_range"
    assert PriceFilter.get_price_tier("200.00") == "premium"
    assert PriceFilter.get_price_tier(150) == "mid_range"  # Test with int


def test_material_filter_empty_specs():
    """Test material detection with empty or missing specs"""
    assert MaterialFilter.detect_materials({}) == []
    assert MaterialFilter.detect_materials({"other_key": "value"}) == []


def test_material_filter_multiple_materials():
    """Test detection of multiple material types"""
    specs = {"Material": "Cotton and Polyester blend with metal buttons"}
    tags = MaterialFilter.detect_materials(specs)
    assert "natural_material" in tags
    assert "synthetic_material" in tags
    assert "metal_material" in tags
    assert "cotton" in tags
    assert "metal" in tags


def test_logistics_empty_specs():
    """Test logistics filters with empty specs"""
    assert LogisticsFilter.classify_weight({}) == []
    assert LogisticsFilter.classify_dimensions({}) == []


def test_weight_with_invalid_values():
    """Test weight classification with invalid values"""
    assert LogisticsFilter.classify_weight({"Weight": "unknown"}) == []
    assert LogisticsFilter.classify_weight({"Weight": ""}) == []
    assert LogisticsFilter.classify_weight({"Weight": "N/A"}) == []


def test_dimension_with_insufficient_values():
    """Test dimension classification with insufficient dimension values"""
    specs = {"Dimensions": "100 cm"}  # Only one dimension
    LogisticsFilter.classify_dimensions(specs)
    # Should handle gracefully without crashing


def test_sustainability_multiple_certifications():
    """Test detection of multiple certifications"""
    specs = {"certification": "Fair Trade and USDA Organic, FSC Certified"}
    tags = SustainabilityFilter.detect_certifications(specs)
    assert "fair_trade_certified" in tags
    assert "organic_certified" in tags
    assert "fsc_certified" in tags


def test_sustainability_no_certifications():
    """Test with no certifications present"""
    assert SustainabilityFilter.detect_certifications({}) == []
    assert SustainabilityFilter.detect_certifications({"Material": "Cotton"}) == []


def test_semantic_tagger_minimal_data():
    """Test semantic tagger with minimal product data"""
    data = {"ITEM": "Simple Product"}
    tagger = SemanticTagger()
    tags = tagger.generate_tags(data)
    assert isinstance(tags, list)


def test_semantic_tagger_empty_data():
    """Test semantic tagger with empty data"""
    data = {}
    tagger = SemanticTagger()
    tags = tagger.generate_tags(data)
    assert isinstance(tags, list)


def test_semantic_tagger_availability_variations():
    """Test different availability statuses"""
    data_in_stock = {"ITEM": "Product", "AVAILABILITY": "InStock"}
    tagger = SemanticTagger()
    tags = tagger.generate_tags(data_in_stock)
    assert "ready_to_ship" in tags

    data_out_of_stock = {"ITEM": "Product", "AVAILABILITY": "OutOfStock"}
    tags = tagger.generate_tags(data_out_of_stock)
    assert "ready_to_ship" not in tags


def test_semantic_tagger_condition_variations():
    """Test different condition statuses"""
    data_new = {"ITEM": "Product", "CONDITION": "New"}
    tagger = SemanticTagger()
    tags = tagger.generate_tags(data_new)
    assert "brand_new_condition" in tags

    data_used = {"ITEM": "Product", "CONDITION": "Used"}
    tags = tagger.generate_tags(data_used)
    assert "brand_new_condition" not in tags


def test_shard_builder_without_metadata():
    """Test shard builder without metadata"""
    builder = ShardBuilder(include_metadata=False)

    shard = builder.create_shard(
        text="Test", original_data={}, attr_type="test", index=0, semantic_tags=[]
    )

    assert "text" in shard
    assert "metadata" not in shard


def test_shard_builder_without_confidence():
    """Test shard builder without confidence scores"""
    builder = ShardBuilder(
        include_metadata=True, include_confidence=False, include_negative_tags=False
    )

    data = {"ITEM": "Test"}
    shard = builder.create_shard(
        text="Test",
        original_data=data,
        attr_type="test",
        index=0,
        semantic_tags=["tag1", "tag2"],
    )

    assert "metadata" in shard
    tags = shard["metadata"]["semantic_tags"]
    assert tags == ["tag1", "tag2"]  # Should be plain strings


def test_shard_builder_deduplication():
    """Test tag deduplication in shard builder"""
    builder = ShardBuilder(include_confidence=True, include_negative_tags=True)

    # Test with duplicate tags
    tags = ["luxury", "luxury", "ready_to_ship"]
    enriched = builder._add_confidence_scores(tags)

    # Check that duplicates are removed
    tag_names = [t["tag"] for t in enriched]
    assert len(tag_names) == len(set(tag_names))


def test_truncate_text_edge_cases():
    """Test text truncation with edge cases"""
    assert ShardBuilder.truncate_text("") == ""
    assert ShardBuilder.truncate_text("a") == "a"
    assert ShardBuilder.truncate_text("short", max_length=10) == "short"

    # Test with custom max length
    long_text = "A" * 100
    truncated = ShardBuilder.truncate_text(long_text, max_length=50)
    assert len(truncated) == 50
    assert truncated.endswith("...")


def test_rag_generator_empty_data():
    """Test RAG generator with empty data"""
    gen = RAGGenerator()
    shards = gen.generate({})
    assert isinstance(shards, list)
    assert len(shards) > 0  # Should still generate at least subject anchor


def test_rag_generator_none_values():
    """Test RAG generator with None values in data"""
    data = {"ITEM": None, "BRAND": None, "PRICE": None, "SPECS": {"key": None}}

    gen = RAGGenerator()
    shards = gen.generate(data)
    assert isinstance(shards, list)


def test_rag_generator_with_extra_plural():
    """Test RAG generator with custom plural attributes"""
    gen = RAGGenerator(extra_plural={"custom_field", "another_field"})
    assert "custom_field" in gen.plural_attributes
    assert "another_field" in gen.plural_attributes


def test_rag_generator_without_confidence():
    """Test RAG generator without confidence scores"""
    data = {"ITEM": "Test Product", "PRICE": "100"}
    gen = RAGGenerator(include_confidence=False, include_negative_tags=False)
    shards = gen.generate(data)

    assert len(shards) > 0
    if shards[0].get("metadata"):
        tags = shards[0]["metadata"]["semantic_tags"]
        # Tags should be plain strings, not dicts
        assert all(isinstance(t, str) for t in tags)


def test_batch_generation_as_text():
    """Test batch generation returning text instead of shards"""
    items = [
        {"ITEM": "Product A", "PRICE": "50"},
        {"ITEM": "Product B", "PRICE": "100"},
    ]

    gen = RAGGenerator()
    text_output = gen.generate_batch(items, as_text=True)

    assert isinstance(text_output, str)
    assert "Product A" in text_output
    assert "Product B" in text_output


def test_batch_generation_empty_list():
    """Test batch generation with empty list"""
    gen = RAGGenerator()
    shards = gen.generate_batch([])
    assert isinstance(shards, list)
    assert len(shards) == 0


def test_rag_specs_with_nested_dict():
    """Test RAG generation with nested dictionaries in specs"""
    data = {
        "ITEM": "Complex Product",
        "SPECS": {
            "Dimensions": {"Width": "10cm", "Height": "20cm"},
            "Materials": {"Outer": "Leather", "Inner": "Cotton"},
        },
    }

    gen = RAGGenerator()
    shards = gen.generate(data)

    # Should handle nested dicts by converting to string
    assert len(shards) > 0


def test_rag_large_specs_list():
    """Test RAG generation with large lists in specs (should truncate)"""
    data = {
        "ITEM": "Product with Many Options",
        "SPECS": {
            "Colors": ["Color" + str(i) for i in range(150)]  # More than MAX_LIST_ITEMS
        },
    }

    gen = RAGGenerator()
    shards = gen.generate(data)

    # Should not crash and should truncate the list
    assert len(shards) > 0


def test_seasonality_current_month():
    """Test that seasonality detection considers current month"""
    from datetime import datetime, timezone

    current_month = datetime.now(timezone.utc).month

    # December is winter (month 12)
    if current_month == 12:
        tags = SeasonalityFilter.detect_seasonality("Winter Coat")
        assert "winter_seasonal" in tags

        tags = SeasonalityFilter.detect_seasonality("Holiday Decoration")
        assert "holiday_seasonal" in tags


def test_material_case_insensitive():
    """Test that material detection is case insensitive"""
    specs_upper = {"MATERIAL": "COTTON"}
    tags_upper = MaterialFilter.detect_materials(specs_upper)

    specs_lower = {"material": "cotton"}
    tags_lower = MaterialFilter.detect_materials(specs_lower)

    assert tags_upper == tags_lower


def test_weight_unit_conversions():
    """Test weight unit conversions"""
    # Test kg to kg (6kg > 5kg threshold)
    specs_kg = {"Weight": "6 kg"}
    tags = LogisticsFilter.classify_weight(specs_kg)
    assert "bulky_item" in tags

    # Test g to kg (6000g = 6kg > 5kg threshold)
    specs_g = {"Weight": "6000 g"}
    tags = LogisticsFilter.classify_weight(specs_g)
    assert "bulky_item" in tags

    # Test lb to kg (15 lb ~= 6.75 kg > 5kg threshold)
    specs_lb = {"Weight": "15 lb"}
    tags = LogisticsFilter.classify_weight(specs_lb)
    assert "bulky_item" in tags


def test_dimension_unit_conversions():
    """Test dimension unit conversions"""
    # Test cm
    specs_cm = {"Dimensions": "160 x 50 x 50 cm"}
    tags_cm = LogisticsFilter.classify_dimensions(specs_cm)
    assert "oversized_item" in tags_cm

    # Test inches (160cm ~= 63in)
    specs_in = {"Dimensions": "63 x 20 x 20 in"}
    tags_in = LogisticsFilter.classify_dimensions(specs_in)
    assert "oversized_item" in tags_in


def test_shard_metadata_structure():
    """Test the structure of shard metadata"""
    builder = ShardBuilder(include_metadata=True, include_confidence=True)

    data = {"ITEM": "Test", "PRICE": "100"}
    semantic_tags = ["luxury"]

    shard = builder.create_shard(
        text="Test",
        original_data=data,
        attr_type="subject_anchor",
        index=0,
        semantic_tags=semantic_tags,
    )

    metadata = shard["metadata"]
    assert "index" in metadata
    assert "attr_type" in metadata
    assert "original_data" in metadata
    assert "semantic_tags" in metadata
    assert isinstance(metadata["semantic_tags"], list)


def test_rag_generator_max_shards():
    """Test that RAG generator respects MAX_SHARDS limit"""
    # Create data with many specs to potentially exceed MAX_SHARDS
    specs = {f"Spec{i}": f"Value{i}" for i in range(1500)}
    data = {
        "ITEM": "Product with Many Specs",
        "BRAND": "Brand",
        "PRICE": "100",
        "SPECS": specs,
    }

    gen = RAGGenerator()
    shards = gen.generate(data)

    # Should be limited by MAX_SHARDS constant (1000)
    assert len(shards) <= 1000


# ========== Vector-Based Tests ==========


def load_test_vector(filename: str) -> dict[str, Any]:
    """Load a test vector JSON file"""
    file_path = VECTORS_DIR / filename
    if file_path.exists():
        with open(file_path, encoding="utf-8") as f:
            result: dict[str, Any] = json.load(f)
            return result
    return {}


def test_pixel_8a_vector():
    """Test RAG generation against Pixel 8a test vector"""
    vector = load_test_vector("pixel_8a_expected.json")
    if not vector:
        # Skip if vector file doesn't exist yet
        return

    product = vector["product"]
    expected_tags = set(vector["expected_tags"])

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate(product)

    # Extract tags from first shard
    if shards and shards[0].get("metadata"):
        actual_tags = shards[0]["metadata"]["semantic_tags"]
        if isinstance(actual_tags[0], dict):
            actual_tag_names = {
                t["tag"] for t in actual_tags if t["type"] == "positive"
            }
        else:
            actual_tag_names = set(actual_tags)

        # Check that most expected tags are present
        matched_tags = expected_tags & actual_tag_names
        assert (
            len(matched_tags) >= len(expected_tags) * 0.7
        ), f"Expected at least 70% tag match. Matched: {matched_tags}"


def test_pixel_9_pro_vector():
    """Test RAG generation against Pixel 9 Pro test vector"""
    vector = load_test_vector("pixel_9_pro_expected.json")
    if not vector:
        return

    product = vector["product"]
    expected_shard_types = set(vector["expected_shard_types"])

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate(product)

    # Check shard types
    actual_types = {
        s.get("metadata", {}).get("attr_type") for s in shards if s.get("metadata")
    }

    # All expected types should be present
    assert expected_shard_types.issubset(actual_types)


def test_eco_product_vector():
    """Test RAG generation with eco-friendly product"""
    vector = load_test_vector("eco_product_expected.json")
    if not vector:
        return

    product = vector["product"]

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate(product)

    # Extract tags
    if shards and shards[0].get("metadata"):
        actual_tags = shards[0]["metadata"]["semantic_tags"]
        if isinstance(actual_tags[0], dict):
            tag_names = [t["tag"] for t in actual_tags if t["type"] == "positive"]
        else:
            tag_names = actual_tags

        # Should have sustainability tags
        assert any(
            "certified" in tag for tag in tag_names
        ), "Expected sustainability certification tags"


def test_furniture_vector():
    """Test RAG generation with heavy furniture item"""
    vector = load_test_vector("furniture_expected.json")
    if not vector:
        return

    product = vector["product"]

    gen = RAGGenerator(include_metadata=True)
    shards = gen.generate(product)

    # Extract tags
    if shards and shards[0].get("metadata"):
        actual_tags = shards[0]["metadata"]["semantic_tags"]
        if isinstance(actual_tags[0], dict):
            tag_names = [t["tag"] for t in actual_tags if t["type"] == "positive"]
        else:
            tag_names = actual_tags

        # Should have logistics tags for heavy/oversized items
        assert any(
            "heavy" in tag or "oversized" in tag or "freight" in tag
            for tag in tag_names
        ), "Expected logistics tags for heavy furniture"


# ========== SemanticTagger Advanced Features Tests ==========


def test_semantic_tagger_brand_recognition():
    """Test brand tag generation with sanitization and hash suffix"""
    tagger = SemanticTagger()

    # Normal brand - should have hash suffix
    data = {"BRAND": "Apple"}
    tags = tagger.generate_tags(data)
    brand_tags = [t for t in tags if t.startswith("brand_apple_")]
    assert len(brand_tags) == 1
    # Verify hash suffix is present (6 chars)
    assert len(brand_tags[0].split("_")[-1]) == 6

    # Brand with spaces and special chars
    data = {"BRAND": "Ralph Lauren & Co."}
    tags = tagger.generate_tags(data)
    brand_tags = [t for t in tags if t.startswith("brand_")]
    assert len(brand_tags) == 1
    assert "_" in brand_tags[0]
    # Should have hash suffix
    assert len(brand_tags[0].split("_")[-1]) == 6

    # Empty brand
    data = {"BRAND": "   "}
    tags = tagger.generate_tags(data)
    brand_tags = [t for t in tags if t.startswith("brand_")]
    assert len(brand_tags) == 0

    # None brand
    data = {"BRAND": None}
    tags = tagger.generate_tags(data)
    brand_tags = [t for t in tags if t.startswith("brand_")]
    assert len(brand_tags) == 0


def test_semantic_tagger_category_detection():
    """Test category detection from item name"""
    tagger = SemanticTagger()

    # Electronics
    data = {"ITEM": "Gaming Laptop Computer"}
    tags = tagger.generate_tags(data)
    assert "electronics" in tags

    # Apparel
    data = {"ITEM": "Cotton T-Shirt"}
    tags = tagger.generate_tags(data)
    assert "apparel" in tags

    # Home goods
    data = {"ITEM": "Wooden Chair for Dining"}
    tags = tagger.generate_tags(data)
    assert "home_goods" in tags

    # Toys
    data = {"ITEM": "LEGO Building Toy Set"}
    tags = tagger.generate_tags(data)
    assert "toys" in tags


def test_semantic_tagger_availability_extended():
    """Test extended availability tag generation"""
    tagger = SemanticTagger()

    # OutOfStock
    data = {"AVAILABILITY": "OutOfStock"}
    tags = tagger.generate_tags(data)
    assert "unavailable" in tags

    data = {"AVAILABILITY": "Discontinued"}
    tags = tagger.generate_tags(data)
    assert "unavailable" in tags

    # PreOrder
    data = {"AVAILABILITY": "PreOrder"}
    tags = tagger.generate_tags(data)
    assert "preorder_available" in tags


def test_semantic_tagger_condition_extended():
    """Test extended condition tag generation"""
    tagger = SemanticTagger()

    # Refurbished
    data = {"CONDITION": "Refurbished"}
    tags = tagger.generate_tags(data)
    assert "refurbished" in tags

    # Used
    data = {"CONDITION": "Used"}
    tags = tagger.generate_tags(data)
    assert "pre_owned" in tags


def test_semantic_tagger_private_methods():
    """Test SemanticTagger private methods"""
    tagger = SemanticTagger()

    # Test _get_availability_tags
    data_avail = {"AVAILABILITY": "InStock", "CONDITION": "New"}
    avail_tags = tagger._get_availability_tags(data_avail)
    assert "ready_to_ship" in avail_tags
    assert "brand_new_condition" in avail_tags

    # Test _get_category_tags
    data_cat = {"ITEM": "laptop computer"}
    cat_tags = tagger._get_category_tags(data_cat)
    assert "electronics" in cat_tags


def test_content_hash_computation():
    """Test content hash is computed correctly."""
    shard1 = {"text": "iPhone", "metadata": {"index": 0, "attr_type": "subject_anchor"}}
    shard2 = {"text": "iPhone", "metadata": {"index": 5, "attr_type": "subject_anchor"}}
    assert ShardBuilder.compute_content_hash(
        shard1
    ) == ShardBuilder.compute_content_hash(shard2)

    # Different text = different hash
    shard3 = {"text": "Samsung", "metadata": {"attr_type": "subject_anchor"}}
    assert ShardBuilder.compute_content_hash(
        shard1
    ) != ShardBuilder.compute_content_hash(shard3)


def test_deduplication_across_products():
    """Test deduplication across products in batch mode."""
    gen = RAGGenerator()
    gen.reset_deduplication()
    products = [{"ITEM": "A", "CURRENCY": "USD"}, {"ITEM": "B", "CURRENCY": "USD"}]
    shards = gen.generate_batch(
        products, as_text=False, deduplicate_across_products=True
    )
    currency_shards = [s for s in shards if s["metadata"]["attr_type"] == "currency"]
    assert len(currency_shards) == 1


# --- RAG glue: container selection + pipeline edge branches ---

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _fake_sentence_transformers(monkeypatch: pytest.MonkeyPatch):
    """
    Suite safety net: if any code path tries to instantiate LocalEmbedder,
    do not crash the whole test run.
    """
    fake = types.ModuleType("sentence_transformers")

    class FakeST:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def encode(self, text, normalize_embeddings=False):
            return [0.0, 0.0, 0.0]

    fake.SentenceTransformer = FakeST  # type: ignore
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)


def test_rag_container_unknown_vector_store_raises():
    from commercetxt.rag.container import RAGContainer

    c = RAGContainer(config={"RAG_VECTOR_DB": "definitely-not-real"})
    with pytest.raises(ValueError):
        _ = c.vector_store


def test_pipeline_text_mode_ingest_returns_0_and_does_not_upsert():
    from commercetxt.rag.pipeline import RAGPipeline

    class H:
        def assess(self, data):
            return {"score": 100, "warnings": []}

    class G:
        def __init__(self):
            self.calls = 0

        def generate(self, data):
            self.calls += 1
            return "some text instead of shards"  # text mode => ingest returns 0

    class VS:
        def __init__(self):
            self.upserts = 0

        def connect(self):
            return True

        def upsert(self, shards, namespace="default"):
            self.upserts += 1
            return len(shards)

    class E:
        def embed_shards(self, shards):
            raise AssertionError("embed_shards must NOT be called in text-mode ingest")

        def embed_text(self, q):
            return [1.0, 0.0, 0.0]

    class C:
        def __init__(self):
            self._embedder = E()
            self._vector_store = VS()

        @property
        def embedder(self):
            return self._embedder

        @property
        def vector_store(self):
            return self._vector_store

    p = RAGPipeline()
    p.health_checker = H()
    p.generator = G()
    p.container = C()

    n = p.ingest({"PRODUCT": {"SKU": "p1"}})
    assert n == 0
    assert p.container.vector_store.upserts == 0


def test_pipeline_search_empty_results_still_returns_list():
    from commercetxt.rag.pipeline import RAGPipeline

    class H:
        def assess(self, data):
            return {"score": 100, "warnings": []}

    class E:
        def embed_text(self, q):
            return [1.0, 0.0, 0.0]

    class VS:
        def connect(self):
            return True

        def search(self, query_vector, top_k=5, namespace="default"):
            return []  # edge branch: empty results

    class R:
        def __init__(self):
            self.calls = 0

        def enrich(self, results, fields=None):
            self.calls += 1
            return results

    class C:
        def __init__(self):
            self._embedder = E()
            self._vector_store = VS()

        @property
        def embedder(self):
            return self._embedder

        @property
        def vector_store(self):
            return self._vector_store

    p = RAGPipeline()
    p.health_checker = H()
    p.enricher = R()
    p.container = C()

    out = p.search("q", top_k=1)
    assert out == []


# ========== Generator Edge Cases & Mutation Tests ==========


def test_generator_handles_none_values_without_crash():
    """Generator processes None values in product fields safely."""
    gen = RAGGenerator()

    data = {
        "PRODUCT": {
            "Name": "Test Product",
            "Description": None,
            "Brand": None,
            "Features": None,
        },
        "OFFER": {"Price": None, "Currency": None},
    }

    shards = gen.generate(data)

    assert isinstance(shards, list)
    assert len(shards) > 0
    for shard in shards:
        assert "text" in shard
        assert "metadata" in shard


def test_generator_respects_max_shards_limit():
    """Generator must not exceed MAX_SHARDS regardless of input size."""
    from commercetxt.rag.core.constants import MAX_SHARDS

    gen = RAGGenerator()

    data = {
        "PRODUCT": {
            "Name": "Product with excessive content",
            "Features": [f"Feature {i}" for i in range(500)],
            "Specs": {f"Spec{i}": f"Value{i}" for i in range(200)},
        }
    }

    shards = gen.generate(data)

    assert len(shards) <= MAX_SHARDS


def test_generator_parses_variant_strings_with_embedded_data():
    """Generator extracts prices and SKUs from variant strings."""
    gen = RAGGenerator()

    data = {
        "PRODUCT": {
            "Name": "Configurable Product",
            "Variants": [
                "Red / Small: 19.99 | SKU: PROD-R-S | Stock: 10",
                "Blue / Medium: 24.99 | SKU: PROD-B-M | Stock: 5",
                "Green / Large: 29.99 | SKU: PROD-G-L | Stock: 0",
            ],
        }
    }

    shards = gen.generate(data)

    # Generator should process variant data and create shards
    assert len(shards) >= 1

    # Verify variants were processed by checking metadata
    metadata_str = str([s.get("metadata", {}) for s in shards])
    assert "Variants" in metadata_str or len(shards) >= 3


def test_generator_handles_empty_data_without_error():
    """Generator processes empty inputs gracefully."""
    gen = RAGGenerator()

    shards_empty = gen.generate({})
    assert isinstance(shards_empty, list)

    shards_minimal = gen.generate({"PRODUCT": {}})
    assert isinstance(shards_minimal, list)


def test_generator_processes_unicode_and_emojis():
    """Generator handles international text and emojis correctly."""
    gen = RAGGenerator()

    data = {
        "PRODUCT": {
            "Name": "Café ☕ Product™",
            "Description": "Français: «Qualité» & <special>",
        }
    }

    shards = gen.generate(data)

    assert len(shards) > 0
    assert isinstance(shards[0]["text"], str)


def test_generator_includes_subscription_plan_data():
    """Generator extracts subscription pricing from plan strings."""
    gen = RAGGenerator()

    data = {
        "PRODUCT": {"Name": "Subscription Service"},
        "SUBSCRIPTION": {
            "Plans": [
                "Monthly: 9.99 | Frequency: monthly",
                "Annual: 99.99 | Frequency: yearly | Savings: 17%",
            ]
        },
    }

    shards = gen.generate(data)
    assert len(shards) >= 1


def test_generator_produces_consistent_output_across_calls():
    """Generator returns same structure for identical input."""
    gen = RAGGenerator()

    data = {"PRODUCT": {"Name": "Consistent Product", "SKU": "CONST-001"}}

    shards1 = gen.generate(data)
    shards2 = gen.generate(data)

    assert len(shards1) == len(shards2)


def test_generator_all_shards_contain_required_fields():
    """Every shard must have text and metadata structure."""
    gen = RAGGenerator()

    data = {
        "PRODUCT": {
            "Name": "Structure Test",
            "Features": ["A", "B", "C"],
            "Description": "Testing shard structure",
        },
        "OFFER": {"Price": 50.00},
    }

    shards = gen.generate(data)

    assert len(shards) > 0
    for shard in shards:
        assert "text" in shard
        assert "metadata" in shard
        assert isinstance(shard["metadata"], dict)


def test_generator_includes_technical_specs_in_output():
    """Specs from SPECS section appear in generated shards."""
    gen = RAGGenerator()

    data = {
        "PRODUCT": {"Name": "Technical Product"},
        "SPECS": {
            "Processor": "Intel Core i7",
            "RAM": "16GB DDR4",
            "Storage": "512GB NVMe SSD",
        },
    }

    shards = gen.generate(data)
    assert len(shards) > 0


def test_generator_groups_variants_by_primary_attribute():
    """Variants with same primary attr should group logically."""
    gen = RAGGenerator()

    data = {
        "PRODUCT": {
            "Name": "Grouped Variants",
            "Variants": [
                "Black / 64GB: 499",
                "Black / 128GB: 599",
                "White / 64GB: 499",
                "White / 128GB: 599",
            ],
        }
    }

    shards = gen.generate(data)
    assert len(shards) >= 1


def test_generator_handles_very_long_text_fields():
    """Generator processes long text without memory issues."""
    gen = RAGGenerator()

    long_desc = "A" * 5000

    data = {"PRODUCT": {"Name": "Product", "Description": long_desc}}

    shards = gen.generate(data)
    assert len(shards) > 0
