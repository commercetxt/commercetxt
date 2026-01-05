"""
Tests for normalizer performance optimization (pre-sorted units cache).
Consolidated version - reduced from 16 to 8 tests while maintaining coverage.
"""

import builtins
import sys
import time

import pytest

from commercetxt.rag.tools.normalizer import SemanticNormalizer


class TestNormalizerCache:
    """Consolidated tests for normalizer caching behavior."""

    @pytest.fixture
    def normalizer(self):
        return SemanticNormalizer()

    def test_units_presorted_and_immutable(self, normalizer):
        """Test units are pre-sorted during init and remain immutable."""
        # Verify structure
        assert hasattr(normalizer, "_sorted_units")
        assert isinstance(normalizer._sorted_units, list)
        assert set(normalizer._sorted_units) == set(normalizer.registry.keys())

        # Verify sorted by length (descending)
        lengths = [len(unit) for unit in normalizer._sorted_units]
        assert lengths == sorted(lengths, reverse=True)

        # Verify immutability after use
        initial_sorted = normalizer._sorted_units.copy()
        cache_id = id(normalizer._sorted_units)

        normalizer.normalize_value("10 kg")
        normalizer.normalize_value("5 lbs")

        assert normalizer._sorted_units == initial_sorted
        assert id(normalizer._sorted_units) == cache_id

    def test_multi_word_units_priority(self, normalizer):
        """Test multi-word units matched before single-word units."""
        # "uk pint" (7 chars) should come before "pint" (4 chars)
        uk_pint_index = normalizer._sorted_units.index("uk pint")
        pint_index = normalizer._sorted_units.index("pint")
        assert uk_pint_index < pint_index

        # Verify correct recognition
        result = normalizer.normalize_value("1 uk pint")
        assert "l" in result

    def test_instance_independence(self):
        """Test normalizer instances have independent but equal caches."""
        n1 = SemanticNormalizer(target_weight="kg")
        n2 = SemanticNormalizer(target_weight="g")

        # Separate objects, same content
        assert n1._sorted_units is not n2._sorted_units
        assert n1._sorted_units == n2._sorted_units
        assert n1.target_units != n2.target_units

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("", ""),
            ("42", "42"),
            ("hello world", "hello world"),
            (None, None),
        ],
        ids=["empty", "number", "text", "none"],
    )
    def test_edge_cases(self, normalizer, value, expected):
        """Test edge cases don't cause issues with cached sorting."""
        result = normalizer.normalize_value(value)
        assert result == expected

    def test_case_insensitive_matching(self, normalizer):
        """Test cached sorting doesn't break case-insensitive matching."""
        results = [
            normalizer.normalize_value("10 KG"),
            normalizer.normalize_value("10 kg"),
            normalizer.normalize_value("10 Kg"),
        ]
        assert len(set(results)) == 1  # All should be identical
        assert "kg" in results[0]


class TestNormalizerPerformance:
    """Consolidated performance tests."""

    def test_no_sorting_per_call(self):
        """Test normalize_value doesn't sort on every call."""
        normalizer = SemanticNormalizer()
        sort_call_count = {"count": 0}
        original_sorted = sorted

        def counting_sorted(*args, **kwargs):
            sort_call_count["count"] += 1
            return original_sorted(*args, **kwargs)

        builtins.sorted = counting_sorted

        try:
            for _ in range(10):
                normalizer.normalize_value("10 kg")
                normalizer.normalize_value("5 lbs")
            assert sort_call_count["count"] == 0
        finally:
            builtins.sorted = original_sorted

    def test_performance_benchmark(self):
        """Benchmark performance and verify acceptable throughput."""
        normalizer = SemanticNormalizer()
        test_values = [
            "10 kg",
            "5 lbs",
            "100 ml",
            "2 uk pints",
            "5 fluid ounces",
            "1000 g",
            "10 oz",
            "2.5 l",
        ]

        iterations = 1000
        start_time = time.perf_counter()

        for _ in range(iterations):
            for value in test_values:
                normalizer.normalize_value(value)

        elapsed = time.perf_counter() - start_time
        total_ops = iterations * len(test_values)
        ops_per_sec = total_ops / elapsed

        assert elapsed < 10.0, f"Performance regression: {elapsed:.3f}s"
        assert ops_per_sec > 1000, f"Throughput too low: {ops_per_sec:.0f} ops/sec"

    def test_init_and_memory_efficiency(self):
        """Test initialization speed and memory efficiency."""
        # Init speed
        start_time = time.perf_counter()
        for _ in range(100):
            SemanticNormalizer()
        elapsed = time.perf_counter() - start_time
        assert elapsed < 0.1, f"Initialization too slow: {elapsed:.3f}s"

        # Memory efficiency
        normalizer = SemanticNormalizer()
        cache_size = sys.getsizeof(normalizer._sorted_units)
        assert cache_size < 10000, f"Cache too large: {cache_size} bytes"
