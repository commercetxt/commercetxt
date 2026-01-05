"""
CommerceTXT Reference Parser.
Simple. Secure. Reliable.
"""

from .limits import MAX_FILE_SIZE, MAX_LINE_LENGTH
from .metrics import get_metrics
from .model import ParseResult
from .parser import CommerceTXTParser, parse_file, read_commerce_file
from .rag import RAGGenerator
from .resolver import CommerceTXTResolver
from .security import is_safe_url
from .validator import CommerceTXTValidator

__version__ = "1.0.3"

__all__ = [
    "MAX_FILE_SIZE",
    "MAX_LINE_LENGTH",
    "CommerceTXTParser",
    "CommerceTXTResolver",
    "CommerceTXTValidator",
    "ParseResult",
    "RAGGenerator",
    "get_metrics",
    "is_safe_url",
    "parse_file",
    "read_commerce_file",
]
