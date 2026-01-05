"""
CommerceTXT Metrics Tests.

Tests singleton, isolation, dependency injection, and thread safety.
"""

import threading
from unittest.mock import patch

import pytest

from commercetxt.metrics import Metrics, get_metrics
from commercetxt.parser import CommerceTXTParser


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset metrics before each test for isolation."""
    Metrics.reset_default()
    yield
    Metrics.reset_default()


def test_stop_timer_without_start():
    """Stop timer without start does not crash."""
    m = Metrics()
    m.stop_timer("never_started")
    assert "never_started_duration" not in m.timers


class TestMetricsBasic:
    """Basic metrics functionality tests."""

    def test_full_api(self):
        """All metric types work correctly."""
        m = get_metrics()
        m.reset()

        m.increment("counter", 1)
        m.increment("counter", 5)
        m.set_gauge("gauge", 100)
        m.start_timer("op")
        m.stop_timer("op")

        stats = m.get_stats()
        assert stats["counters"]["counter"] == 6
        assert stats["gauges"]["gauge"] == 100
        assert "op_duration" in stats["timers"]

        assert get_metrics() is Metrics.get_default()

    def test_metrics_singleton_construction_killer(self):
        """Singleton returns existing instance without calling constructor."""
        Metrics.clear_default()
        m1 = Metrics.get_default()

        with patch(
            "commercetxt.metrics.Metrics.__init__",
            side_effect=RuntimeError("Constructor called!"),
        ):
            m2 = Metrics.get_default()
            assert m1 is m2


class TestMetricsIsolation:
    """Tests for metrics isolation and dependency injection."""

    def test_independent_instances(self):
        """Metrics instances are independent."""
        m1, m2 = Metrics(), Metrics()
        assert m1 is not m2

        m1.increment("test", 1)
        m2.increment("test", 2)

        assert m1.get_stats()["counters"]["test"] == 1
        assert m2.get_stats()["counters"]["test"] == 2

    def test_reset_and_clear(self):
        """reset_default and clear_default work correctly."""
        m = Metrics.get_default()
        m.increment("test", 42)

        Metrics.reset_default()
        assert m.get_stats()["counters"].get("test", 0) == 0

        m.increment("test", 1)
        Metrics.clear_default()
        m2 = Metrics.get_default()
        assert m is not m2

    def test_dependency_injection(self):
        """Metrics can be injected into parser."""
        custom_metrics = Metrics()
        parser = CommerceTXTParser(metrics=custom_metrics)

        assert parser.metrics is custom_metrics
        parser.parse("# @IDENTITY\nName: Test")
        assert "parse_duration" in custom_metrics.get_stats()["timers"]

    def test_thread_safety(self):
        """Concurrent access does not crash."""
        m = get_metrics()
        errors = []

        def worker():
            try:
                for _i in range(100):
                    m.increment("concurrent", 1)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert m.get_stats()["counters"]["concurrent"] == 500
