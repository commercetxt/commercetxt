"""
Performance tracking for CommerceTXT.
Measure the speed. Count the events.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class Metrics:
    """A single place for all data points."""

    _default_instance: Metrics | None = None

    def __init__(self):
        """Initialize a new metrics instance."""
        self.reset()

    def reset(self):
        """Clear all stored data."""
        self.timers = {}
        self.counters = defaultdict(int)
        self.gauges = defaultdict(int)
        self._starts = {}

    def start_timer(self, name: str):
        """Mark the beginning of an operation."""
        self._starts[name] = time.perf_counter()

    def stop_timer(self, name: str):
        """Calculate and store elapsed time."""
        start = self._starts.pop(name, None)
        if start:
            duration = time.perf_counter() - start
            # Save results like 'parse_duration' or 'validation_duration'.
            self.timers[f"{name}_duration"] = duration

    def increment(self, name: str, value: int = 1):
        """Add to a counter."""
        self.counters[name] += value

    def gauge(self, name: str, value: Any):
        """Record a current value."""
        self.gauges[name] = value

    def set_gauge(self, name: str, value: Any):
        """Alias for gauge."""
        self.gauges[name] = value

    def get_stats(self) -> dict[str, Any]:
        """Return all metrics as a dictionary."""
        return {
            "timers": self.timers,
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
        }

    @classmethod
    def get_default(cls) -> Metrics:
        """
        Get the default singleton instance.
        This is the application-level singleton for production use.
        """
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    @classmethod
    def reset_default(cls):
        """
        Reset the default singleton instance.
        Useful for test isolation.
        """
        if cls._default_instance is not None:
            cls._default_instance.reset()

    @classmethod
    def clear_default(cls):
        """
        Clear the default singleton instance entirely.
        Creates a fresh instance on next get_default() call.
        """
        cls._default_instance = None


def get_metrics() -> Metrics:
    """
    Access the default metrics instance.

    For production code: Always returns the same singleton.
    For tests: Use metrics parameter in constructors for isolation.

    Example:
        # Production:
        metrics = get_metrics()

        # Tests (isolated):
        test_metrics = Metrics()  # Fresh instance
        parser = CommerceTXTParser(metrics=test_metrics)
    """
    return Metrics.get_default()
