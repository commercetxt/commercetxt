"""
Tests for RAG tools: AIHealthChecker, SchemaBridge, SemanticNormalizer
"""

from commercetxt.rag.tools import AIHealthChecker, SchemaBridge, SemanticNormalizer

# ========== AIHealthChecker Tests ==========


def test_health_checker_critical_fields():
    """Test health checker detects missing critical fields"""
    data = {"ITEM": "Test"}  # Missing PRICE
    result = AIHealthChecker().assess(data)
    assert result["score"] < 70
    assert "Missing core commercial fields" in result["suggestions"][0]


def test_health_checker_complete_data():
    """Test health checker with complete product data"""
    data = {
        "ITEM": "Test Product",
        "PRICE": "100",
        "CURRENCY": "USD",
        "BRAND": "TestBrand",
        "AVAILABILITY": "InStock",
        "DESCRIPTION": "A test product",
        "SPECS": {
            "Weight": "500g",
            "Dimensions": "10x10x5 cm",
            "Material": "Plastic",
            "Color": "Black",
            "Processor": "Test CPU",
            "RAM": "8GB",
            "Storage": "256GB",
            "Display": "6 inch OLED",
        },
    }
    result = AIHealthChecker().assess(data)
    assert result["score"] >= 70


def test_health_checker_empty_data():
    """Test health checker with empty data"""
    result = AIHealthChecker().assess({})
    assert result["score"] < 50
    assert len(result["suggestions"]) > 0


def test_health_checker_missing_specs():
    """Test health checker penalizes missing SPECS"""
    data = {
        "ITEM": "Test",
        "PRICE": "100",
        "CURRENCY": "USD",
        "BRAND": "Brand",
        "AVAILABILITY": "InStock",
    }
    result = AIHealthChecker().assess(data)

    assert result["score"] == 60
    assert any("@SPECS" in s for s in result["suggestions"])


def test_health_checker_few_specs():
    """Test health checker penalizes insufficient specs"""
    data = {
        "ITEM": "Test",
        "PRICE": "100",
        "CURRENCY": "USD",
        "BRAND": "Brand",
        "AVAILABILITY": "InStock",
        "SPECS": {"Color": "Red", "Size": "M"},
    }
    result = AIHealthChecker().assess(data)

    assert result["score"] == 80
    assert any("Few technical specs" in s for s in result["suggestions"])


def test_health_checker_excellent_score():
    """Test health checker gives excellent score for complete data"""
    data = {
        "ITEM": "Test Product",
        "PRICE": "100",
        "CURRENCY": "USD",
        "BRAND": "TestBrand",
        "AVAILABILITY": "InStock",
        "DESCRIPTION": "A well-described test product",
        "SEMANTIC_LOGIC": "When user asks about durability, emphasize 2-year warranty",
        "SPECS": {
            "Weight": "500g",
            "Dimensions": "10x10x5 cm",
            "Material": "Aluminum",
            "Color": "Black",
            "Processor": "Test CPU",
            "RAM": "8GB",
            "Storage": "256GB",
            "Display": "6 inch OLED",
        },
    }
    result = AIHealthChecker().assess(data)
    assert result["score"] >= 90
    assert result["status"] == "EXCELLENT"


def test_health_checker_marketing_buzzwords():
    """Test health checker penalizes marketing fluff"""
    data = {
        "ITEM": "Test",
        "PRICE": "100",
        "CURRENCY": "USD",
        "BRAND": "Brand",
        "AVAILABILITY": "InStock",
        "DESCRIPTION": "This is the best in the world product! Amazing! Click here!",
        "SPECS": {"Feature": "Value"},
    }
    result = AIHealthChecker().assess(data)
    assert any("marketing buzzwords" in s.lower() for s in result["suggestions"])


def test_health_checker_long_description():
    """Test health checker warns about long descriptions"""
    data = {
        "ITEM": "Test",
        "PRICE": "100",
        "CURRENCY": "USD",
        "BRAND": "Brand",
        "AVAILABILITY": "InStock",
        "DESCRIPTION": "A" * 2000,  # Very long description
        "SPECS": {"Feature": "Value"},
    }
    result = AIHealthChecker().assess(data)
    assert any("Long description" in s for s in result["suggestions"])


# ========== SchemaBridge Tests ==========


def test_schema_bridge_json_ld():
    """Test schema bridge converts to JSON-LD format"""
    data = {"NAME": "Test", "PRICE": "100", "CURRENCY": "USD"}
    json_ld = SchemaBridge().to_json_ld(data)
    assert '"@type": "Product"' in json_ld
    assert '"price": "100"' in json_ld


def test_schema_bridge_with_brand():
    """Test schema bridge includes brand information"""
    data = {
        "NAME": "Test Product",
        "BRAND": "TestBrand",
        "PRICE": "100",
        "CURRENCY": "USD",
    }
    json_ld = SchemaBridge().to_json_ld(data)
    assert '"@type": "Product"' in json_ld
    assert "TestBrand" in json_ld


def test_schema_bridge_empty_data():
    """Test schema bridge with minimal data"""
    data = {"NAME": "Minimal"}
    json_ld = SchemaBridge().to_json_ld(data)
    assert '"@type": "Product"' in json_ld
    assert "Minimal" in json_ld


def test_schema_bridge_with_reviews():
    """Test schema bridge includes aggregateRating from REVIEWS"""
    data = {
        "NAME": "Test Product",
        "PRICE": "100",
        "REVIEWS": {"RATING": "4.5", "COUNT": "150", "RATINGSCALE": "5"},
    }
    json_ld = SchemaBridge().to_json_ld(data)
    assert '"@type": "Product"' in json_ld
    assert '"aggregateRating"' in json_ld
    assert '"ratingValue": "4.5"' in json_ld
    assert '"reviewCount": "150"' in json_ld
    assert '"bestRating": "5"' in json_ld


def test_schema_bridge_with_specs():
    """Test schema bridge includes additionalProperty from SPECS"""
    data = {
        "NAME": "Test Product",
        "PRICE": "100",
        "SPECS": {"Weight": "500g", "Color": "Black", "Material": "Aluminum"},
    }
    json_ld = SchemaBridge().to_json_ld(data)
    assert '"@type": "Product"' in json_ld
    assert '"additionalProperty"' in json_ld
    assert '"PropertyValue"' in json_ld
    assert '"Weight"' in json_ld or "Weight" in json_ld
    assert '"Color"' in json_ld or "Color" in json_ld


def test_schema_bridge_complete_product():
    """Test schema bridge with all fields including reviews and specs"""
    data = {
        "NAME": "Complete Product",
        "BRAND": "TestBrand",
        "PRICE": "999",
        "CURRENCY": "USD",
        "REVIEWS": {"RATING": "4.8", "COUNT": "500"},
        "SPECS": {"Processor": "TestCPU", "RAM": "16GB"},
    }
    json_ld = SchemaBridge().to_json_ld(data)
    assert '"@type": "Product"' in json_ld
    assert '"aggregateRating"' in json_ld
    assert '"additionalProperty"' in json_ld
    assert "TestBrand" in json_ld
    assert '"999"' in json_ld


# ========== SemanticNormalizer Tests ==========


def test_normalizer_weight():
    """Test normalizer converts weight units"""
    n = SemanticNormalizer()
    assert n.normalize_value("1500 g") == "1.5 kg"
    assert n.normalize_value("10 lb") == "4.536 kg"


def test_normalizer_weight_already_kg():
    """Test normalizer handles values already in kg"""
    n = SemanticNormalizer()
    assert n.normalize_value("5 kg") == "5 kg"
    assert n.normalize_value("0.5 kg") == "0.5 kg"
    assert n.normalize_value("0.321 kg") == "0.321 kg"


def test_normalizer_dimensions():
    """Test normalizer converts dimension units"""
    n = SemanticNormalizer()
    result = n.normalize_value("10 in")
    assert "m" in result


def test_normalizer_no_units():
    """Test normalizer with values without units"""
    n = SemanticNormalizer()
    result = n.normalize_value("100")
    assert result is not None


def test_normalizer_invalid_input():
    """Test normalizer with invalid input"""
    n = SemanticNormalizer()
    result = n.normalize_value("invalid text")
    assert result is not None


def test_normalizer_volume_units():
    """Test normalizer converts volume units"""
    n = SemanticNormalizer()
    result = n.normalize_value("500 ml")
    assert "l" in result  # Should convert to liters

    result = n.normalize_value("2 l")
    assert "l" in result


def test_normalizer_distance_units():
    """Test normalizer converts distance units to meters"""
    n = SemanticNormalizer()

    # Test inches to meters
    result = n.normalize_value("10 in")
    assert "m" in result

    # Test centimeters to meters
    result = n.normalize_value("100 cm")
    assert "m" in result

    # Test feet to meters
    result = n.normalize_value("5 ft")
    assert "m" in result


def test_normalizer_normalize_specs():
    """Test normalize_specs method that processes entire spec dictionaries"""
    n = SemanticNormalizer()

    specs = {
        "Weight": "1500 g",
        "Height": "10 in",
        "Volume": "500 ml",
        "Material": "Aluminum",  # Non-measurable value
        "Count": 5,  # Non-string value
    }

    normalized = n.normalize_specs(specs)

    # Check that measurable values are normalized
    assert "kg" in normalized["Weight"]
    assert "m" in normalized["Height"]
    assert "l" in normalized["Volume"]

    assert normalized["Material"] == "Aluminum"
    assert normalized["Count"] == 5


def test_normalizer_rstrip_trailing_zeros():
    """Test that normalizer formats with 3 decimal places"""
    n = SemanticNormalizer()

    result = n.normalize_value("1000 g")
    assert result == "1 kg"


# ========== NEW E-COMMERCE UNITS TESTS ==========


def test_normalizer_imperial_shorthand():
    """Test common e-commerce shorthand units (", ', lbs, cc)"""
    n = SemanticNormalizer()

    result = n.normalize_value('15"')
    assert "m" in result  # Should convert inches to meters

    result = n.normalize_value("6'")
    assert "m" in result  # Should convert feet to meters

    result = n.normalize_value("3.5 lbs")
    assert "kg" in result


def test_normalizer_uk_imperial_units():
    """Test UK imperial units (stone, uk pint, uk gallon)"""
    n = SemanticNormalizer()

    result = n.normalize_value("12 stone")
    assert "kg" in result

    result = n.normalize_value("1 uk pint")
    assert "l" in result

    result = n.normalize_value("5 uk gal")
    assert "l" in result


def test_normalizer_cooking_units():
    """Test cooking units (cups, tbsp, tsp)"""
    n = SemanticNormalizer()

    result = n.normalize_value("2 cups")
    assert "l" in result

    # Tablespoon
    result = n.normalize_value("3 tbsp")
    assert "l" in result

    # Teaspoon
    result = n.normalize_value("1 tsp")
    assert "l" in result


def test_normalizer_metric_variations():
    """Test metric variations (cl, dl, cc, m³)"""
    n = SemanticNormalizer()

    result = n.normalize_value("75 cl")
    assert "l" in result

    result = n.normalize_value("2000 cc")
    assert "l" in result

    result = n.normalize_value("2 m3")
    assert "l" in result


def test_normalizer_uk_spelling_variations():
    """Test UK spelling variations (metre, litre, tonne)"""
    n = SemanticNormalizer()

    result = n.normalize_value("5 metres")
    assert "m" in result

    result = n.normalize_value("2 litres")
    assert "l" in result or result == "2 litres"


def test_normalizer_large_units():
    """Test large units (metric ton, yard, mile)"""
    n = SemanticNormalizer()

    result = n.normalize_value("0.5 ton")
    assert "kg" in result

    result = n.normalize_value("5 yards")
    assert "m" in result

    result = n.normalize_value("100 miles")
    assert "m" in result


def test_normalizer_small_units():
    """Test small units (mg, mm, fl oz)"""
    n = SemanticNormalizer()

    result = n.normalize_value("500 mg")
    assert "kg" in result

    result = n.normalize_value("15 mm")
    assert "m" in result

    result = n.normalize_value("1 fl oz")
    assert "l" in result


def test_normalizer_real_world_amazon_units():
    """Test real-world Amazon product units"""
    n = SemanticNormalizer()

    result = n.normalize_value('27"')
    assert "m" in result

    result = n.normalize_value("3.5 lbs")
    assert "kg" in result

    result = n.normalize_value("6.5 inches")
    assert "m" in result


def test_normalizer_real_world_beverage_units():
    """Test real-world beverage industry units"""
    n = SemanticNormalizer()

    result = n.normalize_value("75 cl")
    assert "l" in result

    result = n.normalize_value("1 uk pint")
    assert "l" in result

    result = n.normalize_value("2 liters")
    assert "l" in result or "2" in result
