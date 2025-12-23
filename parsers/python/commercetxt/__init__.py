"""
CommerceTXT Reference Parser.
Simple. Secure. Reliable.
"""

from .parser import CommerceTXTParser
from .validator import CommerceTXTValidator
from .model import ParseResult
from .security import is_safe_url
from .resolver import CommerceTXTResolver
from .metrics import get_metrics
from .limits import MAX_FILE_SIZE, MAX_LINE_LENGTH

# Public API of the package.
# Use these to parse and validate files.
__all__ = [
    "CommerceTXTParser",
    "CommerceTXTValidator",
    "CommerceTXTResolver",
    "ParseResult",
    "is_safe_url",
    "get_metrics",
    "MAX_FILE_SIZE",
    "MAX_LINE_LENGTH",
]
