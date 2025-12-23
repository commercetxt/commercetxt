"""
Stress and Performance tests for CommerceTXT.
Tests boundaries, concurrency, and heavy data loads.
"""

import time
import random
import string
import pytest
from concurrent.futures import ThreadPoolExecutor
from commercetxt.limits import MAX_NESTING_DEPTH, MAX_SECTIONS
from commercetxt.async_parser import AsyncCommerceTXTParser
from commercetxt import (
    CommerceTXTParser,
    CommerceTXTValidator,
    CommerceTXTResolver,
    ParseResult,
)


def generate_random_string(length=10):
    """Generates a random alphanumeric string."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_massive_content(lines=10000):
    """Generates a massive file with thousands of keys and lists."""
    content = [
        "Version: 1.0.1",
        "# @IDENTITY",
        "Name: Stress Store",
        "Currency: USD",
        "# @CATALOG",
    ]
    for i in range(lines):
        if i % 10 == 0:
            content.append(f"# @SECTION_{i}")
        content.append(f"Key_{i}: Value_{generate_random_string(20)}")
        content.append(f"  - Item_{i}: /path/{i} | Meta: {generate_random_string(5)}")
    return "\n".join(content)


def test_high_volume_parsing():
    """Test parsing a file with thousands of sections (DoS protection check)."""
    parser = CommerceTXTParser()
    content = "\n".join([f"# @SECTION_{i}\nKey: Value" for i in range(2000)])
    result = parser.parse(content)

    assert len(result.directives) == MAX_SECTIONS
    assert any("Max sections limit" in w for w in result.warnings)


def test_deep_recursion_merge_stress():
    """Tests recursion limit when merging deep levels of nesting."""
    resolver = CommerceTXTResolver()

    def create_nested_result(depth):
        curr = {"VALUE": "base"}
        for i in range(depth):
            curr = {f"LEVEL_{i}": curr}
        return ParseResult(directives={"OFFER": curr})

    root = create_nested_result(100)
    child = create_nested_result(100)

    # Must merge 100 levels without RecursionError
    merged = resolver.merge(root, child)
    assert "LEVEL_99" in merged.directives["OFFER"]


def test_concurrency_safety():
    """Tests if the parser is thread-safe during parallel execution."""
    parser = CommerceTXTParser()
    massive_data = generate_massive_content(500)

    def run_parse():
        res = parser.parse(massive_data)
        return len(res.directives)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_parse) for _ in range(10)]
        results = [f.result() for f in futures]

    assert all(r > 0 for r in results)


def test_malformed_input_bomb():
    """Tests resilience against chaotic text."""
    parser = CommerceTXTParser(strict=False)
    garbage = "\n".join(
        ["".join(random.choices(string.printable, k=100)) for _ in range(1000)]
    )

    result = parser.parse(garbage)
    assert len(result.warnings) > 0
    assert len(result.errors) == 0


def test_validator_logic_exhaustion():
    """Tests validator with extreme values and ensures Tier 1 data is present."""
    validator = CommerceTXTValidator()

    huge_data = ParseResult(
        directives={
            # Must include Identity to pass initial validation tiers
            "IDENTITY": {"Name": "Stress Test Store", "Currency": "USD"},
            "OFFER": {"Price": "1e100", "Availability": "InStock"},
            "REVIEWS": {
                "RatingScale": "5",
                "Count": "999999999",
                "Toptags": '"' + "A" * 200 + '", "B"',
            },
            "IMAGES": {
                "items": [{"name": "Main", "path": "/img.jpg", "Alt": "X" * 5000}]
            },
        }
    )

    validator.validate(huge_data)
    assert any("too long" in w for w in huge_data.warnings)


def test_locale_lookup_scaling():
    """Tests locale lookup speed with many definitions."""
    resolver = CommerceTXTResolver()
    locales = {f"BG-{i}": f"/path/{i}.txt" for i in range(1000)}
    locales["FR"] = "/fr/commerce.txt"

    root = ParseResult(directives={"LOCALES": locales})

    start = time.perf_counter()
    path = resolver.resolve_locales(root, "fr-CA")
    end = time.perf_counter()

    assert path == "/fr/commerce.txt"
    assert (end - start) < 0.1


def test_max_indentation_depth():
    """Verify that the parser enforces MAX_NESTING_DEPTH limit."""
    parser = CommerceTXTParser()
    total_levels_attempted = MAX_NESTING_DEPTH + 10

    lines = ["# @DEEP_SECTION"]
    for i in range(total_levels_attempted):
        indent = "  " * i
        lines.append(f"{indent}- level_{i}")

    content = "\n".join(lines)
    result = parser.parse(content)

    assert any("Max nesting depth" in w for w in result.warnings)
    section = result.directives.get("DEEP_SECTION")

    # Count actual depth achieved
    current_item = section["items"][0]
    depth_count = 1
    while "children" in current_item and current_item["children"]:
        current_item = current_item["children"][0]
        depth_count += 1

    assert depth_count == MAX_NESTING_DEPTH


def test_repeated_key_overwrite_performance():
    """Tests performance when overwriting the same key 50,000 times."""
    parser = CommerceTXTParser()
    lines = ["# @OVERWRITE_TEST"]
    for i in range(50000):
        lines.append(f"Price: {i}")

    content = "\n".join(lines)
    start_time = time.time()
    result = parser.parse(content)
    end_time = time.time()

    # Use a generous limit for different hardware/environments
    assert (end_time - start_time) < 5.0
    assert result.directives["OVERWRITE_TEST"]["Price"] == "49999"


def test_large_file_performance():
    """Generates a large file (10,000 variants) and checks speed."""
    lines = [
        "# @IDENTITY",
        "Name: Stress Test Store",
        "Currency: USD",
        "# @INVENTORY",
        "LastUpdated: 2023-10-01T12:00:00Z",
        "StockStatus: InStock",
        "# @OFFER",
        "Price: 100.00",
        "Availability: InStock",
        "# @VARIANTS",
        "Options:",
    ]

    for i in range(10000):
        lines.append(f"  - Size {i}: {10.00 + i}")

    content = "\n".join(lines)

    start_time = time.time()
    parser = CommerceTXTParser()
    result = parser.parse(content)
    parse_duration = time.time() - start_time

    validator = CommerceTXTValidator()
    start_time = time.time()
    validator.validate(result)
    validate_duration = time.time() - start_time

    assert parse_duration < 2.0
    assert validate_duration < 2.0


@pytest.mark.asyncio
async def test_async_bulk_parse():
    """Verify concurrent parsing of multiple items."""
    contents = [
        "# @ID\nName: Store 1\nCurrency: USD",
        "# @ID\nName: Store 2\nCurrency: USD",
        "# @ID\nName: Store 3\nCurrency: USD",
    ]
    async_parser = AsyncCommerceTXTParser()
    results = await async_parser.parse_many(contents)

    assert len(results) == 3
    assert "ID" in results[0].directives
    assert "ID" in results[2].directives


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
