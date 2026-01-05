"""
Caching layer for CommerceTXT results.
Fast lookup. Zero redundant work.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import ParseResult

from .parser import CommerceTXTParser


@lru_cache(maxsize=1000)
def parse_cached(content: str) -> "ParseResult":
    """
    Parse content with internal caching.
    The first call is slow. The rest are instant.
    """

    parser = CommerceTXTParser()
    return parser.parse(content)
