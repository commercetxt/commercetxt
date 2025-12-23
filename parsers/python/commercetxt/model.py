"""
The CommerceTXT data model.
Data stays here. Truth stays here.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParseResult:
    """
    The result of a parse.
    It holds directives, errors, and trust signals.
    """

    # Parsed sections. Maps names to data.
    directives: Dict[str, Any] = field(default_factory=dict)

    # Critical failures. Fix these first.
    errors: List[str] = field(default_factory=list)

    # Minor issues. Good to know.
    warnings: List[str] = field(default_factory=list)

    # Trust markers. They signal data quality.
    trust_flags: List[str] = field(default_factory=list)

    # The spec version used.
    version: Optional[str] = None

    # When the data last changed.
    last_updated: Optional[str] = None
