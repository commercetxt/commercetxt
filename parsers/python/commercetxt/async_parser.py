"""
Async support for bulk parsing.
Speed through concurrency.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Literal

from .constants import VALID_EXECUTOR_TYPES
from .model import ParseResult
from .parser import CommerceTXTParser


class AsyncCommerceTXTParser:
    """Non-blocking engine for high-volume data."""

    def __init__(
        self,
        parser_instance=None,
        executor_type: Literal["thread", "process"] = "thread",
        max_workers: int | None = None,
    ):
        """
        Initialize async parser.

        Args:
            parser_instance: Parser instance to use (default: CommerceTXTParser())
            executor_type: "thread" for I/O-bound or "process" for CPU-bound work
            max_workers: Number of workers
                (default: CPU count for process, 5*CPU for thread)

        Raises:
            ValueError: If executor_type is not 'thread' or 'process'
            ValueError: If max_workers is negative
        """
        # Explicit validation for executor_type
        if executor_type not in VALID_EXECUTOR_TYPES:
            raise ValueError(
                f"Invalid executor_type: {executor_type!r}. "
                f"Must be one of: {VALID_EXECUTOR_TYPES}"
            )

        # Explicit validation for max_workers
        if max_workers is not None and max_workers < 0:
            raise ValueError(f"max_workers must be non-negative, got: {max_workers}")

        # Explicit None check instead of 'or'
        if parser_instance is None:
            self.parser = CommerceTXTParser()
        else:
            self.parser = parser_instance

        self.executor_type = executor_type
        self.max_workers = max_workers
        self._executor = None

    def _get_executor(self):
        """Get or create the appropriate executor."""
        if self._executor is None:
            if self.executor_type == "process":
                # ProcessPoolExecutor for true parallelism (CPU-bound work)
                self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
            # else: use default thread pool (None = ThreadPoolExecutor)
        return self._executor

    async def parse_many(self, contents: list[str]) -> list[ParseResult]:
        """
        Parse a list of files concurrently.
        Failures in one do not stop the others.

        Performance:
        - executor_type="thread": Good for I/O-bound (default, backward compatible)
        - executor_type="process": Better for CPU-bound parsing (true parallelism)

        Example:
            # For CPU-intensive parsing (recommended for large batches):
            parser = AsyncCommerceTXTParser(executor_type="process")
            results = await parser.parse_many(contents)
        """
        loop = asyncio.get_running_loop()
        executor = self._get_executor()

        # Use executor for CPU-bound parsing work
        # ProcessPoolExecutor bypasses GIL for true parallelism
        tasks = [loop.run_in_executor(executor, self.parser.parse, c) for c in contents]

        # return_exceptions=True prevents one crash from failing the whole batch
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter and return only successful results
        return [r for r in results if isinstance(r, ParseResult)]

    def __del__(self):
        """Cleanup executor if not properly closed."""
        if hasattr(self, "_executor") and self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None

    async def __aenter__(self):
        """Context manager support."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup executor on exit."""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
        return False
