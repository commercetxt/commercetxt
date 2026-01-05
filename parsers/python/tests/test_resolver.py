"""
Tests for the CommerceTXT Resolver.
Find the files. Merge the data. Stay secure.
"""

import json
from pathlib import Path

import pytest

from commercetxt import CommerceTXTResolver, ParseResult
from commercetxt.resolver import resolve_path

VECTORS_DIR = Path(__file__).parent / "vectors"


def load_vector(path_parts: list):
    """Load test vector from JSON. Skip if missing."""
    vector_path = VECTORS_DIR.joinpath(*path_parts)
    if not vector_path.exists():
        pytest.skip(f"Test vector not found: {vector_path}")
    with open(vector_path, encoding="utf-8") as f:
        return json.load(f)


def test_locale_resolution_logic():
    """Exact match first. Then language code. Then fallback to root."""
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
    assert resolver.resolve_locales(root_result, "fr") == "/fr/commerce.txt"
    # Fallback to language.
    assert resolver.resolve_locales(root_result, "fr-CA") == "/fr/commerce.txt"
    # Root fallback.
    assert resolver.resolve_locales(root_result, "ja-JP") == "/"


def test_fractal_inheritance_merge():
    """Specific data must override general data. Preserve the rest."""
    root = ParseResult(
        directives={
            "IDENTITY": {"Name": "Global Store", "Currency": "USD"},
            "POLICIES": {"Returns": "30 Days"},
        }
    )
    product = ParseResult(
        directives={
            "IDENTITY": {"Currency": "EUR"},
            "OFFER": {"Price": "100.00"},
        }
    )
    merged = CommerceTXTResolver().merge(root, product)

    assert merged.directives["IDENTITY"]["Currency"] == "EUR"
    assert merged.directives["IDENTITY"]["Name"] == "Global Store"
    assert merged.directives["OFFER"]["Price"] == "100.00"


def test_resolver_version_inheritance():
    """Child version always wins."""
    parent = ParseResult(version="1.0.0")
    child = ParseResult(version="1.0.1")
    result = CommerceTXTResolver().merge(parent, child)
    assert result.version == "1.0.1"


def test_deep_merge_nested_dicts():
    """Merge dictionaries recursively. Overwrite values. Preserve keys."""
    parent = ParseResult(
        directives={"OFFER": {"Details": {"Tax": "In", "Ship": "Free"}}}
    )
    child = ParseResult(directives={"OFFER": {"Details": {"Tax": "Ex", "Disc": "10%"}}})
    merged = CommerceTXTResolver().merge(parent, child)

    details = merged.directives["OFFER"]["Details"]
    assert details["Tax"] == "Ex"
    assert details["Ship"] == "Free"
    assert details["Disc"] == "10%"


def test_error_accumulation():
    """Combine errors and warnings from both files. Remove duplicates."""
    parent = ParseResult(errors=["Err1"], warnings=["Warn1"], trust_flags=["T1"])
    child = ParseResult(errors=["Err2"], warnings=["Warn2"], trust_flags=["T2"])
    merged = CommerceTXTResolver().merge(parent, child)

    assert "Err1" in merged.errors
    assert "Err2" in merged.errors
    assert "Warn1" in merged.warnings
    assert "Warn2" in merged.warnings
    assert "T1" in merged.trust_flags
    assert "T2" in merged.trust_flags


def test_resolve_path_404_handling():
    """Return a result with an error on 404. Do not crash."""
    from commercetxt.resolver import resolve_path

    def mock_loader(p):
        raise FileNotFoundError

    result = resolve_path("/missing.txt", mock_loader)
    assert "404" in result.errors[0]


def test_merge_trust_flags_deduplication():
    """Trust flags must be unique. No duplicates allowed."""
    p = ParseResult(trust_flags=["stale", "unverified"])
    c = ParseResult(trust_flags=["stale", "new"])
    merged = CommerceTXTResolver().merge(p, c)
    assert len(merged.trust_flags) == 3


def test_list_replacement_logic():
    """Replace lists entirely. Do not merge list items."""
    parent = ParseResult(directives={"S": {"items": [{"name": "A"}]}})
    child = ParseResult(directives={"S": {"items": [{"name": "B"}]}})
    merged = CommerceTXTResolver().merge(parent, child)
    assert len(merged.directives["S"]["items"]) == 1
    assert merged.directives["S"]["items"][0]["name"] == "B"


def test_type_mismatch_override():
    """Child types overwrite parent types. Strings become dicts."""
    parent = ParseResult(directives={"M": {"Data": "Str"}})
    child = ParseResult(directives={"M": {"Data": {"Key": "Val"}}})
    merged = CommerceTXTResolver().merge(parent, child)
    assert isinstance(merged.directives["M"]["Data"], dict)


# --- RECOVERY OF MISSING 8 TESTS ---


def test_merge_preserves_trust_flags():
    """Combine trust flags from both sources. Lose nothing."""
    p1 = ParseResult(trust_flags=["flag1"])
    p2 = ParseResult(trust_flags=["flag2"])
    merged = CommerceTXTResolver().merge(p1, p2)
    assert "flag1" in merged.trust_flags
    assert "flag2" in merged.trust_flags


def test_resolver_handles_none_parent():
    """Handle empty parents gracefully. Return child data."""
    child = ParseResult(directives={"S": {"K": "V"}})
    merged = CommerceTXTResolver().merge(ParseResult(), child)
    assert merged.directives == child.directives


def test_deep_merge_list_override():
    """Override lists at any depth. Replacement is absolute."""
    parent = {"D": {"L": [1, 2]}}
    child = {"D": {"L": [3]}}
    merged = CommerceTXTResolver()._deep_merge(parent, child)
    assert merged["D"]["L"] == [3]


def test_resolve_path_strips_query_params():
    """Query parameters should not interfere with local path resolution."""
    from commercetxt.resolver import resolve_path

    def mock_loader(p):
        return "# @ID\nName: Ok"

    # Implementation dependent: if loader strips it, logic is sound.
    res = resolve_path("file.txt?v=1", mock_loader)
    assert not res.errors


def test_ssrf_blocked_range():
    """Block private network IPs. Protect the internal infrastructure."""
    from commercetxt.resolver import resolve_path

    def mock_loader(p):
        return ""

    res = resolve_path("http://192.168.1.1/commerce.txt", mock_loader)
    assert any("Security: Blocked" in e for e in res.errors)


def test_resolve_path_unicode_name():
    """Support files with non-ASCII filenames."""
    from commercetxt.resolver import resolve_path

    def mock_loader(p):
        return "# @ID\nName: Ok"

    res = resolve_path("магазин.txt", mock_loader)
    assert res.directives["ID"]["Name"] == "Ok"


def test_fractal_inheritance_depth_3():
    """Test inheritance across three generations. Grandparent to Child."""
    r = CommerceTXTResolver()
    g = ParseResult(directives={"A": {"V": 1}})
    p = ParseResult(directives={"A": {"V": 2}, "B": {"V": 3}})
    c = ParseResult(directives={"B": {"V": 4}})

    m1 = r.merge(g, p)
    m2 = r.merge(m1, c)
    assert m2.directives["A"]["V"] == 2
    assert m2.directives["B"]["V"] == 4


def test_resolver_last_updated_inheritance():
    """Child timestamps overwrite parent timestamps. Keep data fresh."""
    p = ParseResult(last_updated="2020")
    c = ParseResult(last_updated="2024")
    merged = CommerceTXTResolver().merge(p, c)
    assert merged.last_updated == "2024"


def test_resolve_path_generic_exception():
    """Catch unexpected loader errors. Return them as results."""

    def bomb_loader(path):
        msg = "Fatal Disk Error"
        raise RuntimeError(msg)

    result = resolve_path("test.txt", bomb_loader)
    assert "Fatal Disk Error" in result.errors[0]


class TestCircularDependency:
    """Circular dependency detection tests."""

    def test_detection(self):
        """Test circular dependency detection."""
        resolver = CommerceTXTResolver()
        parent = ParseResult()
        parent._source_path = "/root/file1.txt"
        child = ParseResult()
        child._source_path = "/root/file2.txt"

        merged1 = resolver.merge(parent, child)
        assert merged1 is not None

        circular = ParseResult()
        circular._source_path = "/root/file1.txt"

        with pytest.raises(ValueError, match="Circular dependency"):
            resolver.merge(merged1, circular)

    def test_reset_tracking(self):
        """Test resolver tracking reset."""
        resolver = CommerceTXTResolver()
        r1 = ParseResult()
        r1._source_path = "/file1.txt"
        r2 = ParseResult()
        r2._source_path = "/file2.txt"

        resolver.merge(r1, r2)
        resolver.reset_tracking()

        r3 = ParseResult()
        r3._source_path = "/file1.txt"
        r4 = ParseResult()
        r4._source_path = "/file2.txt"

        merged = resolver.merge(r3, r4)
        assert merged is not None

    def test_no_source_path(self):
        """Test merge without _source_path."""
        resolver = CommerceTXTResolver()
        merged = resolver.merge(ParseResult(), ParseResult())
        assert merged is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
