"""
Tests for CommerceTXT Metrics.
Measure everything. Leave no doubt.
"""

from commercetxt.metrics import get_metrics


def test_metrics_full_api():
    """Test all metric types. Ensure stats are recorded and reset works."""
    m = get_metrics()
    m.reset()

    # Test counters.
    m.increment("test_counter", 1)
    m.increment("test_counter", 5)

    # Test gauges.
    m.set_gauge("test_gauge", 100)

    # Test timers (already used in parser, but checking retrieval here).
    m.start_timer("test_op")
    m.stop_timer("test_op")

    stats = m.get_stats()

    assert stats["counters"]["test_counter"] == 6
    assert stats["gauges"]["test_gauge"] == 100
    assert "test_op_duration" in stats["timers"]


def test_metrics_singleton():
    """Ensure get_metrics always returns the same instance."""
    m1 = get_metrics()
    m2 = get_metrics()
    assert m1 is m2
