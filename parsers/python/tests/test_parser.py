"""
CommerceTXT Parser Tests.

Tests parsing, encoding, sections, nesting, and list handling.
"""

import pytest

from commercetxt import CommerceTXTParser, parse_file
from commercetxt.limits import MAX_LINE_LENGTH, MAX_NESTING_DEPTH, MAX_SECTIONS
from commercetxt.parser import _try_read_with_encoding, read_commerce_file


@pytest.fixture
def parser():
    """Default parser instance."""
    return CommerceTXTParser()


# =============================================================================
# Encoding & File Reading
# =============================================================================


def test_encoding_detection(tmp_path):
    """UTF-8 BOM detected. Invalid encodings rejected."""
    content = "# @IDENTITY\nName: Store\nCurrency: USD"

    # UTF-8 with BOM
    f = tmp_path / "bom.txt"
    f.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    c, e = read_commerce_file(f)
    assert "IDENTITY" in c
    assert e in ("utf-8", "utf-8-sig")

    # Invalid encoding
    f_inv = tmp_path / "invalid.txt"
    f_inv.write_bytes(b"\xff\xfe\x00\xd8")
    with pytest.raises(UnicodeDecodeError):
        read_commerce_file(f_inv, encoding="ascii")

    # Explicit encoding mismatch
    f_utf16 = tmp_path / "utf16.txt"
    f_utf16.write_text("Data", encoding="utf-16")
    with pytest.raises(UnicodeDecodeError):
        read_commerce_file(f_utf16, encoding="ascii")

    # Successful explicit encoding
    f_utf8 = tmp_path / "utf8.txt"
    f_utf8.write_text("Data", encoding="utf-8")
    c, e = read_commerce_file(f_utf8, encoding="utf-8")
    assert c == "Data" and e == "utf-8"


def test_read_non_existent_file():
    """Missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        read_commerce_file("non_existent_file_xyz_123.txt")


# =============================================================================
# Line Processing & Limits
# =============================================================================


@pytest.mark.parametrize(
    "line, expected_key",
    [
        ("  # @TEST  ", "TEST"),
        ("#@TEST", "TEST"),
        ("# @test", "TEST"),
    ],
)
def test_directive_normalization(parser, line, expected_key):
    """Section headers normalize whitespace and case."""
    result = parser.parse(f"{line}\nK: V")
    assert expected_key in result.directives


def test_max_line_length(parser):
    """Long lines are truncated with warning."""
    long_line = "K: " + ("x" * (MAX_LINE_LENGTH + 1))
    result = parser.parse("# @TEST\n" + long_line)
    assert any("truncating" in w.lower() for w in result.warnings)


def test_max_sections(parser):
    """Section count is capped at MAX_SECTIONS."""
    content = "\n".join([f"# @S{i}\nKey: Value" for i in range(MAX_SECTIONS + 1)])
    result = parser.parse(content)
    assert len(result.directives) == MAX_SECTIONS
    assert any("limit" in w.lower() for w in result.warnings)


def test_large_file_boundary(parser):
    """File at exact limit passes. One byte over fails."""
    from commercetxt.limits import MAX_FILE_SIZE

    content_ok = "v" * MAX_FILE_SIZE
    result_ok = parser.parse(content_ok)
    assert not result_ok.errors

    content_fail = "v" * (MAX_FILE_SIZE + 1)
    result_fail = parser.parse(content_fail)
    assert any("Security: File too large" in e for e in result_fail.errors)


def test_max_sections_boundary(parser):
    """Exactly MAX_SECTIONS is allowed. One more triggers warning."""
    content = "\n".join([f"# @S{i}\nK: V" for i in range(MAX_SECTIONS)])
    result = parser.parse(content)
    assert len(result.directives) == MAX_SECTIONS
    assert not any("limit" in w.lower() for w in result.warnings)

    result2 = parser.parse(content + "\n# @EXTRA\nK: V")
    assert len(result2.directives) == MAX_SECTIONS
    assert any("limit" in w.lower() for w in result2.warnings)


def test_malformed_section_warn(parser):
    """Malformed section header produces warning."""
    result = parser.parse("# @ INVALID SECTION")
    assert any("Malformed section header" in w for w in result.warnings)


def test_strict_mode_failure():
    """Strict mode raises on malformed sections."""
    parser = CommerceTXTParser(strict=True)
    with pytest.raises(ValueError, match="Malformed section header"):
        parser.parse("# @ INVALID SECTION")


# =============================================================================
# Section & Key-Value Logic
# =============================================================================


def test_duplicate_key_wins_last(parser):
    """Last value wins for duplicate keys."""
    result = parser.parse("# @T\nKey: First\nKey: Last")
    assert result.directives["T"]["Key"] == "Last"


def test_metadata_detection(parser):
    """Version and LastUpdated extracted from file header."""
    result = parser.parse("Version: 1.0.0\nLastUpdated: 2025-01-01\n# @T\nK: V")
    assert result.version == "1.0.0"
    assert result.last_updated == "2025-01-01"


def test_multi_value_pipe(parser):
    """Pipe separates multiple values. URLs preserve internal pipes."""
    result = parser.parse("# @T\nTags: A | B | C")
    tags = result.directives["T"]["Tags"]
    assert "A" in str(tags) and "B" in str(tags)

    result = parser.parse("# @S\nURL: http://ex.com?q=1|2 | note: test")
    assert result.directives["S"]["URL"]["url"] == "http://ex.com?q=1|2"
    assert result.directives["S"]["URL"]["note"] == "test"


# =============================================================================
# List & Nesting
# =============================================================================


def test_list_parsing_basic(parser):
    """List items parsed with name and path."""
    result = parser.parse("# @CATALOG\n- Electronics: /e.txt\n- Books: /b.txt")
    items = result.directives["CATALOG"]["items"]
    assert len(items) == 2
    assert items[0]["name"] == "Electronics"


def test_nested_list_depth(parser):
    """Nesting beyond MAX_NESTING_DEPTH produces warning."""
    parser_nested = CommerceTXTParser(nested=True)
    content = "# @T\n"
    for i in range(MAX_NESTING_DEPTH + 1):
        content += ("  " * i) + f"- L{i}\n"
    result = parser_nested.parse(content)
    assert any("nesting depth" in w.lower() for w in result.warnings)


def test_list_non_nested(parser):
    """Non-nested mode flattens all list items."""
    p = CommerceTXTParser(nested=False)
    result = p.parse("# @S\n- A\n  - B")
    assert len(result.directives["S"]["items"]) == 2
    assert result.directives["S"]["items"][1]["value"] == "B"


def test_last_empty_key_persistence(parser):
    """Empty key collects subsequent list items."""
    result = parser.parse("# @S\nList:\n- A\n- B\nNewKey: V")
    assert result.directives["S"]["List"] == [{"value": "A"}, {"value": "B"}]
    assert result.directives["S"]["NewKey"] == "V"

    result = parser.parse("# @S1\nEmptyKey:\n# @S2\n- Item")
    assert "EmptyKey" not in result.directives["S1"]
    assert result.directives["S2"]["items"] == [{"value": "Item"}]


def test_duplicate_case_insensitive_keys(parser):
    """Keys are case-insensitive. Last value wins."""
    result = parser.parse("# @S\nname: Alice\nNAME: Bob")
    assert len(result.directives["S"]) == 1
    assert result.directives["S"]["NAME"] == "Bob"


def test_list_without_section(parser):
    """Orphan list items without section are ignored."""
    result = parser.parse("- Orphaned Item")
    assert "items" not in result.directives
    assert not result.directives


# =============================================================================
# Level Detection
# =============================================================================


@pytest.mark.parametrize(
    "directive, expected_level",
    [
        ("CATALOG", "root"),
        ("ITEMS", "category"),
        ("FILTERS", "category"),
        ("PRODUCT", "product"),
    ],
)
def test_level_detection(parser, directive, expected_level):
    """Section type determines context level."""
    result = parser.parse(f"# @{directive}\nK: Value")
    assert result.level == expected_level


# =============================================================================
# URL & Integration
# =============================================================================


def test_url_unwrapping_special(parser):
    """Single URL unwrapped. Multi-value with path preserved."""
    result = parser.parse("# @T\nLINK: https://ex.com")
    assert result.directives["T"]["LINK"] == "https://ex.com"

    result = parser.parse("# @T\nDATA: item.json | path: /data")
    assert result.directives["T"]["DATA"]["path"] == "/data"


def test_url_preservation(parser):
    """Complex URLs with colons and pipes preserved."""
    url = "https://example.com/api?q=1|2&t=a:b"
    result = parser.parse(f"# @T\nURL: {url}")
    assert result.directives["T"]["URL"] == url


def test_parse_file_integration(tmp_path):
    """parse_file reads and parses a file."""
    f = tmp_path / "test.txt"
    f.write_text("# @IDENTITY\nName: Test", encoding="utf-8")
    result = parse_file(str(f))
    assert result.directives["IDENTITY"]["Name"] == "Test"


def test_bom_handling(parser):
    """UTF-8 BOM stripped from content."""
    content = "\ufeff# @IDENTITY\nName: BOM"
    assert parser.parse(content).directives["IDENTITY"]["Name"] == "BOM"


# =============================================================================
# Source Mapping & Comments
# =============================================================================


def test_source_mapping(parser):
    """Source map tracks section line numbers. Comments preserved."""
    content = "# C1\n# @T1\nK1: V1\n\n# @T2"
    result = parser.parse(content)
    assert result.source_map["T1"] == 2
    assert result.source_map["T2"] == 5
    assert result.comments[1] == "C1"


def test_parser_unicode_preservation(parser):
    """Unicode in keys and values preserved."""
    content = "# @МЕНЮ\nКатегория: Храна 🍎"
    result = parser.parse(content)
    assert result.directives["МЕНЮ"]["Категория"] == "Храна 🍎"


def test_nested_list_handling_complex(parser):
    """Nested children attached to parent item."""
    content = "# @S\n- P\n  - C1\n  - C2"
    result = parser.parse(content)
    children = result.directives["S"]["items"][0]["children"]
    assert len(children) == 2
    assert children[0]["value"] == "C1"


def test_auto_indent_detection(parser):
    """Auto-detect overrides initial indent width."""
    p = CommerceTXTParser(indent_width=4, auto_detect_indent=True)
    content = "# @S\n- A\n  - B"
    p.parse(content)
    assert p.indent_width == 2


def test_inconsistent_indent_strict(parser):
    """Strict mode raises on inconsistent indentation."""
    content = "# @S\n- A\n   - B"
    p = CommerceTXTParser(strict=True, auto_detect_indent=False, indent_width=2)
    with pytest.raises(ValueError, match="Inconsistent indentation"):
        p.parse(content)


def test_unknown_syntax_warning(parser):
    """Unrecognized syntax produces warning."""
    result = parser.parse("# @S\n!!! This is not KV or List")
    assert any("Unknown syntax" in w for w in result.warnings)


def test_url_list_item_with_pipe(parser):
    """List item URL with pipe metadata."""
    result = parser.parse("# @S\n- http://ex.com | note: test")
    assert result.directives["S"]["items"][0]["value"] == "http://ex.com"
    assert result.directives["S"]["items"][0]["note"] == "test"


def test_multi_value_collisions(parser):
    """Multi-value handles duplicates, empties, and URLs."""
    result = parser.parse("# @S\nK: V1 | V2")
    assert result.directives["S"]["K"]["values"] == ["V1", "V2"]

    result = parser.parse("# @S\nK: V1 | | V2")
    assert len(result.directives["S"]["K"]["values"]) == 2

    result = parser.parse("# @S\nK: note: A | NOTE: B")
    assert result.directives["S"]["K"]["NOTE"] == "B"

    result = parser.parse("# @S\nK: http://a.com | http://b.com")
    assert result.directives["S"]["K"]["url"] == "http://a.com"
    assert result.directives["S"]["K"]["value"] == "http://b.com"

    result = parser.parse("# @S\nK: http://first.com | https: //second.com")
    assert result.directives["S"]["K"]["url"] == "http://first.com"
    assert result.directives["S"]["K"]["value"] == "https: //second.com"


def test_smart_split_specials(parser):
    """Double slash not treated as URL. Space exits URL mode."""
    result = parser.parse("# @S\nK: //comment-like-url | note: test")
    assert result.directives["S"]["K"]["value"] == "//comment-like-url"
    assert result.directives["S"]["K"]["note"] == "test"

    result = parser.parse("# @S\nK: http://ex.com?q=1 path | note: test")
    assert result.directives["S"]["K"]["url"] == "http://ex.com?q=1 path"


def test_indent_detection_limits(parser):
    """Standard indents detected. Extreme indents capped at 8."""
    p = CommerceTXTParser(auto_detect_indent=True)
    p.parse("# @S\n    - A\n    - B")
    assert p.indent_width == 4

    p2 = CommerceTXTParser(auto_detect_indent=True)
    p2.parse("# @S\n          - A\n          - B")
    assert p2.indent_width == 8


def test_list_item_complex_paths(parser):
    """List item with name, path, and metadata."""
    result = parser.parse("# @S\n- Item Name : /some/path | key: val")
    item = result.directives["S"]["items"][0]
    assert item["name"] == "Item Name"
    assert item["path"] == "/some/path"
    assert item["key"] == "val"


def test_smart_split_mutation_killers(parser):
    """Pipe in URL query preserved. Pipe after whitespace splits."""
    result = parser.parse("# @S\nURL: http://ex.com?a=1|b=2 | note: test")
    assert result.directives["S"]["URL"]["url"] == "http://ex.com?a=1|b=2"

    result = parser.parse("# @S\nK: http://ex.com  | note: test")
    assert result.directives["S"]["K"]["url"] == "http://ex.com"
    assert result.directives["S"]["K"]["note"] == "test"


def test_indent_parity_mutation_killer(parser):
    """Indent zero is valid. Non-multiple indent warns."""
    p = CommerceTXTParser(auto_detect_indent=False, indent_width=2)

    result = p.parse("# @S\nK: V")
    assert not result.warnings

    result2 = p.parse("# @S\n K: V")
    assert len(result2.warnings) > 0


def test_key_replacement_case_killer(parser):
    """Old key deleted before adding case-variant."""
    result = parser.parse("# @S\nname: old\nNAME: new")
    assert "name" not in result.directives["S"]
    assert result.directives["S"]["NAME"] == "new"


def test_regex_stability_paranoid(parser):
    """Sections only match word characters."""
    result = parser.parse("# @SECTION WITH SPACES\nK: V")
    assert "SECTION" not in result.directives
    assert any("Unknown syntax" in w for w in result.warnings)


def test_state_isolation_paranoid(parser):
    """New section resets indent state."""
    content = "# @S1\n- P\n  - C\n# @S2\n- NewItem"
    result = parser.parse(content)
    assert result.directives["S2"]["items"] == [{"value": "NewItem"}]


def test_encoding_fallback_deep(tmp_path):
    """Invalid bytes in all encodings raises UnicodeDecodeError."""
    f = tmp_path / "total_garbage.bin"
    f.write_bytes(b"\xff\xfe\xfd\xfc\x00\x00\x00")
    with pytest.raises(
        UnicodeDecodeError, match="Could not decode file with any supported encoding"
    ):
        read_commerce_file(f)


def test_indent_detection_noise(parser):
    """Detection works even with 100+ comment lines."""
    content = "# Comment\n" * 105 + "  - Indented Item"
    p = CommerceTXTParser(auto_detect_indent=True)
    p.parse(content)
    assert p.indent_width == 2


def test_multi_value_pipe_with_url_at_end(parser):
    """URL at end of multi-value extracted."""
    result = parser.parse("# @S\nK: label | http://example.com")
    assert result.directives["S"]["K"]["url"] == "http://example.com"
    assert result.directives["S"]["K"]["value"] == "label"


def test_list_item_with_only_colon(parser):
    """List item with just colon is valid."""
    result = parser.parse("# @S\n- :")
    assert len(result.directives["S"]["items"]) == 1


def test_bom_removal_mutation_killer(parser):
    """BOM present or absent both parse correctly."""
    res1 = parser.parse("\ufeff# @S\nK: V")
    assert "S" in res1.directives

    res2 = parser.parse("# @S\nK: V")
    assert "S" in res2.directives


def test_detect_indent_extra_cases(parser):
    """Most common indent wins in frequency detection."""
    content = "# @S\n  - A\n  - B\n    - C\n  - D"
    p = CommerceTXTParser(auto_detect_indent=True)
    p.parse(content)
    assert p.indent_width == 2


def test_try_read_encoding_failures(tmp_path):
    """Invalid sequence returns None from try_read."""
    f = tmp_path / "test.txt"
    f.write_bytes(b"\xff\xfe\x00")
    assert _try_read_with_encoding(f, "utf-8") is None


def test_section_chars_validation(parser):
    """Sections reject spaces and special characters."""
    content = "# @MY SECTION\nK: V"
    result = parser.parse(content)
    assert "MY SECTION" not in result.directives

    content2 = "# @S%ECTION\nK: V"
    result2 = parser.parse(content2)
    assert "S%ECTION" not in result2.directives


def test_line_skip_logic_paranoid(parser):
    """Empty lines are skipped without error."""
    content = "# @S\n\n\n\nK: V\n\n\n# @S2\nK2: V2"
    result = parser.parse(content)
    assert len(result.directives) == 2
    assert result.directives["S"]["K"] == "V"
    assert result.directives["S2"]["K2"] == "V2"


def test_encoding_unsupported_paranoid():
    """Manual encoding override works if file matches."""
    import os

    from commercetxt.parser import read_commerce_file

    p = "unsupported.txt"
    with open(p, "w", encoding="ascii") as f:
        f.write("test")

    try:
        content, enc = read_commerce_file(p, encoding="ascii")
        assert enc == "ascii"
    finally:
        if os.path.exists(p):
            os.remove(p)
