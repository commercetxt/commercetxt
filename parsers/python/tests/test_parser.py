"""
Tests for the CommerceTXT Parser.
Verify parsing logic. Protect the syntax.
"""

import json
from pathlib import Path
import pytest

from commercetxt import CommerceTXTParser
from commercetxt.resolver import CommerceTXTResolver
from commercetxt.model import ParseResult
from commercetxt.logging_config import get_logger
from commercetxt.cache import parse_cached

VECTORS_DIR = Path(__file__).parent / "vectors"


def load_vectors(category: str):
    """Load JSON test vectors. Skip if missing."""
    category_dir = VECTORS_DIR / category
    if not category_dir.exists():
        pytest.skip(f"Vectors directory not found: {category_dir}")
        return
    for file in category_dir.glob("*.json"):
        with open(file, "r", encoding="utf-8") as f:
            yield file.stem, json.load(f)


def test_minimal_valid_document():
    """Check basic structure. Verify metadata and normalization."""
    parser = CommerceTXTParser()
    content = """
Version: 1.0.1
# @IDENTITY
Name: Demo Store
Currency: USD
# @OFFER
Price: 19.99
Availability: InStock
"""
    result = parser.parse(content)
    assert result.version == "1.0.1"
    assert result.directives["IDENTITY"]["Name"] == "Demo Store"
    assert result.directives["IDENTITY"]["Currency"] == "USD"


def test_utf8_sanity_parsing():
    """Ensure UTF-8 characters and emojis parse correctly."""
    parser = CommerceTXTParser()
    content = """
Version: 1.0.1
# @IDENTITY
Name: Магазин „Техно" 🚀
Currency: BGN
# @PRODUCT
Name: Смартфон „Звезда"
Description: Best model for 2025. ✨
"""
    result = parser.parse(content)
    assert result.directives["IDENTITY"]["Name"] == 'Магазин „Техно" 🚀'
    assert result.directives["PRODUCT"]["Name"] == 'Смартфон „Звезда"'
    assert "✨" in result.directives["PRODUCT"]["Description"]


def test_list_parsing():
    """Verify flat lists store items correctly."""
    parser = CommerceTXTParser()
    content = """
# @CATALOG
- Electronics: /categories/electronics.txt
"""
    result = parser.parse(content)
    # Global lists are stored under 'items'.
    assert "items" in result.directives["CATALOG"]
    assert result.directives["CATALOG"]["items"][0]["name"] == "Electronics"


def test_subscription_nested_parsing():
    """Verify nested attributes in lists parse as TitleCase keys."""
    parser = CommerceTXTParser()
    content = """
# @SUBSCRIPTION
Plans:
  - Monthly: 29.00 | Features: Basic
"""
    result = parser.parse(content)
    assert result.directives["SUBSCRIPTION"]["Plans"][0]["Features"] == "Basic"


def test_deep_n_level_nesting():
    """Ensure infinite nesting works when enabled."""
    parser = CommerceTXTParser(nested=True)
    content = """
# @VARIANTS
Options:
  - Color:
      - Black:
          - SKU: A1
      - White
  - Size:
      - Small
"""
    result = parser.parse(content)
    options = result.directives["VARIANTS"]["Options"]

    color_node = options[0]
    assert color_node["name"] == "Color"

    black_node = color_node["children"][0]
    assert black_node["name"] == "Black"

    sku_node = black_node["children"][0]
    assert sku_node["name"] == "SKU"
    assert sku_node["path"] == "A1"

    assert options[1]["name"] == "Size"


def test_empty_file_handling():
    """Empty files must not crash. Return empty result."""
    parser = CommerceTXTParser()
    result = parser.parse("")
    assert result.directives == {}
    assert result.version is None
    assert not result.errors


def test_only_comments_file():
    """Comment-only files must produce no data and no warnings."""
    parser = CommerceTXTParser()
    result = parser.parse("# Comment 1\n# Comment 2")
    assert result.directives == {}
    assert not result.warnings


def test_whitespace_only_file():
    """Ignore files containing only whitespace."""
    parser = CommerceTXTParser()
    result = parser.parse("   \n\n\t\t\n   ")
    assert result.directives == {}
    assert not result.errors


def test_malformed_section_header():
    """Invalid headers must trigger a syntax warning."""
    parser = CommerceTXTParser()
    result = parser.parse("# @ IDENTITY\nName: Test")
    assert len(result.warnings) > 0
    assert "Unknown syntax" in result.warnings[0]


def test_duplicate_section_override():
    """New sections overwrite old ones with the same name."""
    parser = CommerceTXTParser()
    result = parser.parse("# @OFFER\nPrice: 10\n# @OFFER\nPrice: 20")
    assert result.directives["OFFER"]["Price"] == "20"


def test_very_long_line():
    """Long lines must not crash the system."""
    parser = CommerceTXTParser()
    long_value = "A" * 100000
    result = parser.parse(f"# @IDENTITY\nName: {long_value}")
    assert len(result.directives["IDENTITY"]["Name"]) == 100000


def test_url_with_query_params():
    """URLs with complex query strings must parse cleanly."""
    parser = CommerceTXTParser()
    result = parser.parse("# @IMAGES\n- Main: http://example.com/img.jpg?w=500&h=300")
    assert "w=500" in result.directives["IMAGES"]["items"][0]["path"]


def test_inconsistent_indentation_warning():
    """Warn when indentation is not divisible by indent_width."""
    parser = CommerceTXTParser(indent_width=2)
    content = """
# @SECTION
  - Item 1
   - Item 2
"""
    result = parser.parse(content)
    assert any("Inconsistent indentation" in w for w in result.warnings)


def test_directive_case_normalization():
    """Force all directive names to uppercase."""
    parser = CommerceTXTParser()
    result = parser.parse("# @identity\nName: Test")
    assert "IDENTITY" in result.directives


def test_colon_in_value():
    """Handle colons inside values, such as timestamps."""
    parser = CommerceTXTParser()
    content = """
# @MISC
Time: 12:00:00
URL: http://example.com
"""
    result = parser.parse(content)
    assert result.directives["MISC"]["Time"] == "12:00:00"
    assert result.directives["MISC"]["URL"] == "http://example.com"


def test_currency_invalid_length_parsing():
    """Verify currency code validation errors. Expect Hemingway messages."""
    parser = CommerceTXTParser()
    res_short = parser.parse("# @IDENTITY\nName: X\nCurrency: U")
    res_long = parser.parse("# @IDENTITY\nName: X\nCurrency: USDTD")

    from commercetxt.validator import CommerceTXTValidator

    validator = CommerceTXTValidator()
    validator.validate(res_short)
    validator.validate(res_long)

    # Sync with Hemingway: 'Use ISO 4217 code'
    assert any("Use ISO 4217 code" in e for e in res_short.errors)
    assert any("Use ISO 4217 code" in e for e in res_long.errors)


def test_multi_value_parsing_coverage():
    """Check piped values within keys."""
    parser = CommerceTXTParser()
    content = "# @LINKS\nSocial: Facebook: fb.com | Twitter: tw.com | JustValue"
    result = parser.parse(content)
    social = result.directives["LINKS"]["Social"]

    assert social["Facebook"] == "fb.com"
    assert social["Twitter"] == "tw.com"
    assert social["value"] == "JustValue"


def test_parser_strict_mode_raises_error():
    """Strict mode must raise ValueError on parsing issues."""
    parser = CommerceTXTParser(strict=True, indent_width=2)
    content = "# @SECTION\n   - Bad Indentation"
    with pytest.raises(ValueError, match="Inconsistent indentation"):
        parser.parse(content)


def test_list_item_complex_parsing():
    """Handle mixed content types in lists."""
    parser = CommerceTXTParser()
    content = """
# @LINKS
- http://example.com | Meta: Data
- Key: Value | Link: http://example.com/image.jpg
- Complex: http://site.com | http: //not-a-url
"""
    result = parser.parse(content)
    items = result.directives["LINKS"]["items"]

    assert items[0]["value"] == "http://example.com"
    assert items[0]["Meta"] == "Data"
    assert items[1]["Link"] == "http://example.com/image.jpg"
    assert items[2]["url"] == "http: //not-a-url"


def test_max_sections_limit():
    """Guard against section overflow."""
    from commercetxt.limits import MAX_SECTIONS

    parser = CommerceTXTParser()
    content = "\n".join(
        [f"# @SECTION_{i}\nKey: Value" for i in range(MAX_SECTIONS + 1)]
    )
    result = parser.parse(content)

    assert len(result.directives) == MAX_SECTIONS
    assert any(
        f"Max sections limit ({MAX_SECTIONS}) reached" in w for w in result.warnings
    )


def test_max_nesting_depth_protection():
    """Guard against infinite recursion in nested lists."""
    from commercetxt.limits import MAX_NESTING_DEPTH

    parser = CommerceTXTParser(nested=True)
    content = "# @DEEP\n"
    for i in range(MAX_NESTING_DEPTH + 5):
        content += "  " * i + "- Item\n"

    result = parser.parse(content)
    assert any(
        f"Max nesting depth ({MAX_NESTING_DEPTH}) exceeded" in w
        for w in result.warnings
    )


def test_resolver_path_traversal_security():
    """Resolver must block path traversal attempts."""
    from commercetxt.resolver import resolve_path

    def mock_loader(p):
        return ""

    result_etc = resolve_path("/etc/passwd", mock_loader)
    result_traversal = resolve_path("../../config.php", mock_loader)

    assert any("Security: Path traversal" in e for e in result_etc.errors)
    assert any("Security: Path traversal" in e for e in result_traversal.errors)


def test_resolver_merge_logic():
    """Child data must overwrite parent data during merge."""
    resolver = CommerceTXTResolver()
    parent = ParseResult(directives={"IDENTITY": {"Name": "Parent", "Currency": "USD"}})
    child = ParseResult(directives={"IDENTITY": {"Name": "Child"}})

    merged = resolver.merge(parent, child)
    assert merged.directives["IDENTITY"]["Name"] == "Child"
    assert merged.directives["IDENTITY"]["Currency"] == "USD"


def test_ai_readiness_calculation():
    """Calculate the score for LLM readiness."""
    from commercetxt.bridge import CommerceAIBridge

    bad_res = ParseResult(directives={"IDENTITY": {"Name": "Store"}})
    bridge_bad = CommerceAIBridge(bad_res)
    score_bad = bridge_bad.calculate_readiness_score()

    good_res = ParseResult(
        version="1.0.1",
        directives={
            "IDENTITY": {"Name": "Store", "Currency": "USD"},
            "OFFER": {"Price": "100", "Availability": "InStock"},
        },
    )
    bridge_good = CommerceAIBridge(good_res)
    score_good = bridge_good.calculate_readiness_score()

    assert score_good["score"] > score_bad["score"]
    assert score_good["grade"] == "A"


def test_nested_list_with_no_root_key():
    """Verify that nesting works even without an explicit key."""
    parser = CommerceTXTParser()
    content = "# @SECTION\n  - Item 1\n    - Sub 1"
    result = parser.parse(content)
    assert "items" in result.directives["SECTION"]
    assert result.directives["SECTION"]["items"][0]["children"][0]["value"] == "Sub 1"


def test_long_key_handling():
    """Keys with many characters must parse correctly."""
    parser = CommerceTXTParser()
    long_key = "A" * 100
    result = parser.parse(f"# @SECTION\n{long_key}: Value")
    assert result.directives["SECTION"][long_key] == "Value"


def test_duplicate_key_in_section():
    """Last key wins if a section has duplicates."""
    parser = CommerceTXTParser()
    result = parser.parse("# @SECTION\nKey: First\nKey: Second")
    assert result.directives["SECTION"]["Key"] == "Second"


def test_multiple_pipes_parsing():
    """Parser must split multiple pipes into keys."""
    parser = CommerceTXTParser()
    content = "# @S\nK: V1 | K2: V2 | K3: V3"
    result = parser.parse(content)
    assert result.directives["S"]["K"]["K2"] == "V2"
    assert result.directives["S"]["K"]["K3"] == "V3"


def test_empty_section_header():
    """Empty section names should be ignored or warned."""
    parser = CommerceTXTParser()
    result = parser.parse("# @\nKey: Value")
    assert not result.directives


def test_bom_removal():
    """Parser should strip UTF-8 BOM and detect the first header correctly."""
    parser = CommerceTXTParser()
    content = "\ufeff# @IDENTITY\nName: Store"
    result = parser.parse(content)
    assert "IDENTITY" in result.directives
    assert result.directives["IDENTITY"]["Name"] == "Store"
    assert not result.warnings


def test_multiline_empty_space():
    """Deeply indented empty lines must not affect nesting stack."""
    parser = CommerceTXTParser()
    content = "# @S\n- Item 1\n\n    \n- Item 2"
    result = parser.parse(content)
    assert len(result.directives["S"]["items"]) == 2


def test_escaped_colon_logic():
    """Verify that only the first colon acts as a delimiter."""
    parser = CommerceTXTParser()
    result = parser.parse("# @S\nKey: Value: With: Colons")
    assert result.directives["S"]["Key"] == "Value: With: Colons"


def test_indentation_tabs_vs_spaces():
    """Mixing tabs and spaces should trigger a warning."""
    parser = CommerceTXTParser()
    result = parser.parse("# @S\n\t- Item")
    assert any("Inconsistent indentation" in w for w in result.warnings)


def test_directive_start_without_name():
    """Line starting with # @ but no name should be ignored."""
    parser = CommerceTXTParser()
    result = parser.parse("# @ \nKey: Value")
    assert not result.directives


def test_trailing_whitespace_in_directives():
    """Directives with trailing spaces must be normalized."""
    parser = CommerceTXTParser()
    result = parser.parse("# @IDENTITY   \nName: Store")
    assert "IDENTITY" in result.directives


def test_empty_lines_between_items():
    """Empty lines should not break list nesting logic."""
    parser = CommerceTXTParser()
    content = "# @S\n- A\n\n- B"
    result = parser.parse(content)
    assert len(result.directives["S"]["items"]) == 2


def test_case_insensitive_metadata():
    """Metadata keys like Version should be case-insensitive."""
    parser = CommerceTXTParser()
    result = parser.parse("version: 1.0.1\nlastupdated: 2024")
    assert result.version == "1.0.1"
    assert result.last_updated == "2024"


def test_parser_list_named_path_vs_url():
    """Test the branch distinguishing named paths from protocols."""
    p = CommerceTXTParser()
    # Path with colon (not a URL).
    item = p._parse_list_item_content("Manual: /docs/guide.pdf")
    assert item["name"] == "Manual"
    assert item["path"] == "/docs/guide.pdf"


def test_parser_list_pipe_without_colon():
    """Test behavior for list items with pipes but no colons."""
    p = CommerceTXTParser()
    content = "Standard Shipping | 3-5 Days"
    item = p._parse_list_item_content(content)
    assert item["value"] == "Standard Shipping | 3-5 Days"


def test_logging_handler_reuse():
    """Ensure get_logger does not duplicate handlers on multiple calls."""
    l1 = get_logger("commercetxt.test")
    l2 = get_logger("commercetxt.test")
    assert l1 == l2
    assert len(l1.handlers) == 1


def test_cache_logic():
    """Verify that repeated calls return the same object (fast)."""
    content = "# @IDENTITY\nName: CacheTest\nCurrency: USD"
    res1 = parse_cached(content)
    res2 = parse_cached(content)

    assert res1 is res2  # Проверка за еднакъв адрес в паметта (cache hit)
    assert res1.directives["IDENTITY"]["Name"] == "CacheTest"


def test_parser_edge_cases(tmp_path, run_cli):
    """Test edge cases via CLI interface."""
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    code, stdout, stderr = run_cli([str(empty)])
    assert code == 1
    assert "Missing @IDENTITY" in stderr or "ERROR" in stdout

    bad_syntax = tmp_path / "syntax.txt"
    bad_syntax.write_text("This line has no colon and no at-sign", encoding="utf-8")
    code, stdout, stderr = run_cli([str(bad_syntax)])

    assert "Unknown syntax" in stdout or "WARN" in stdout
