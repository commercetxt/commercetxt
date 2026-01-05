"""
Thread-safe rate limiter for API calls.

Implements token bucket algorithm for smooth rate limiting.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Any


class RateLimiter:
    """
    Thread-safe rate limiter using token bucket algorithm.

    Example:
        limiter = RateLimiter(calls_per_second=3.0)

        @limiter.limit
        def api_call():
            return expensive_api_request()
    """

    def __init__(self, calls_per_second: float, burst: int | None = None):
        """
        Initialize rate limiter.

        Args:
            calls_per_second: Maximum calls per second (can be fractional,
                e.g., 0.5 = 1 call per 2 seconds)
            burst: Maximum burst size (default: 2x calls_per_second)
        """
        self.rate = calls_per_second
        self.min_interval = 1.0 / calls_per_second if calls_per_second > 0 else 0
        self.max_tokens = burst or max(int(calls_per_second * 2), 1)

        self._tokens = float(self.max_tokens)
        self._last_update = time.time()
        self._lock = threading.RLock()

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.rate
        self._tokens = min(self._tokens + tokens_to_add, self.max_tokens)
        self._last_update = now

    def acquire(
        self, tokens: int = 1, blocking: bool = True, timeout: float | None = None
    ) -> bool:
        """
        Acquire token(s) for rate limiting.

        Args:
            tokens: Number of tokens to acquire
            blocking: If True, wait until tokens are available
            timeout: Maximum wait time in seconds (None = infinite)

        Returns:
            True if tokens acquired, False if not available (non-blocking mode)
        """
        deadline = None if timeout is None else time.time() + timeout

        while True:
            with self._lock:
                self._refill_tokens()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

                if not blocking:
                    return False

                # Calculate wait time
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate

                # Check timeout
                if deadline is not None:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        return False
                    wait_time = min(wait_time, remaining)

            # Sleep outside the lock
            time.sleep(
                min(wait_time, 0.1)
            )  # Sleep in small increments to check frequently

    def limit(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """
        Decorator to rate limit a function.

        Example:
            limiter = RateLimiter(calls_per_second=3)

            @limiter.limit
            def api_call():
                return make_request()
        """

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.acquire()
            return func(*args, **kwargs)

        return wrapper

    def __repr__(self) -> str:
        return (
            f"RateLimiter(rate={self.rate} calls/sec, "
            f"tokens={self._tokens:.2f}/{self.max_tokens})"
        )


def rate_limit(
    calls_per_second: float, burst: int | None = None
) -> Callable[[Callable], Callable]:
    """
    Convenience decorator for rate limiting.

    Example:
        @rate_limit(calls_per_second=3.0)
        def api_call():
            return expensive_request()
    """
    limiter = RateLimiter(calls_per_second=calls_per_second, burst=burst)
    return limiter.limit
