"""
Performance tracking for CommerceTXT.
Measure the speed. Count the events.
"""

import time
from collections import defaultdict
from typing import Any, Dict


class Metrics:
    """A single place for all data points."""

    _instance = None

    def __new__(cls):
        """Ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(Metrics, cls).__new__(cls)
            cls._instance.reset()
        return cls._instance

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

    def get_stats(self) -> Dict[str, Any]:
        """Return all metrics as a dictionary."""
        return {
            "timers": self.timers,
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
        }


def get_metrics() -> Metrics:
    """Access the metrics instance."""
    return Metrics()
