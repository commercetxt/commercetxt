"""
Async support for bulk parsing.
Speed through concurrency.
"""

import asyncio
from typing import List
from .model import ParseResult


class AsyncCommerceTXTParser:
    """Non-blocking engine for high-volume data."""

    def __init__(self, parser_instance=None):
        from .parser import CommerceTXTParser

        self.parser = parser_instance or CommerceTXTParser()

    async def parse_many(self, contents: List[str]) -> List[ParseResult]:
        """
        Parse a list of files concurrently.
        Failures in one do not stop the others.
        """
        loop = asyncio.get_running_loop()
        # Use executor for CPU-bound parsing work.
        tasks = [loop.run_in_executor(None, self.parser.parse, c) for c in contents]

        # return_exceptions=True prevents one crash from failing the whole batch.
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter and return only successful results.
        return [r for r in results if isinstance(r, ParseResult)]
