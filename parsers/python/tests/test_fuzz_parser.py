"""
Lightweight fuzz test for CommerceTXT parser.

Goal:
- Parser must never crash on arbitrary input
- Parser must always return a ParseResult
"""

import random
import string

from commercetxt.parser import CommerceTXTParser
from commercetxt.model import ParseResult


def random_text(max_len=5000):
    size = random.randint(0, max_len)
    return "".join(random.choice(string.printable) for _ in range(size))


def test_parser_fuzz_never_crashes():
    parser = CommerceTXTParser(strict=False)

    for _ in range(500):
        data = random_text()

        result = parser.parse(data)

        assert isinstance(result, ParseResult)
        assert hasattr(result, "directives")
        assert hasattr(result, "errors")
        assert hasattr(result, "warnings")
