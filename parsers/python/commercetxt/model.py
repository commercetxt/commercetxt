"""
The CommerceTXT data model.
Data stays here. Truth stays here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParseResult:
    """
    The result of a parse.
    It holds directives, errors, and trust signals.
    """

    # Parsed sections. Maps names to data.
    directives: dict[str, Any] = field(default_factory=dict)

    # Critical failures. Fix these first.
    errors: list[str] = field(default_factory=list)

    # Minor issues. Good to know.
    warnings: list[str] = field(default_factory=list)

    # Trust markers. They signal data quality.
    trust_flags: list[str] = field(default_factory=list)

    # The spec version used.
    version: str | None = None

    # When the data last changed.
    last_updated: str | None = None

    # Track file hierarchy level
    level: str | None = None

    # File metadata (populated by parse_file helper)
    source_file: str | None = None
    encoding: str | None = None

    # Internal: Used by resolver for circular dependency detection
    _source_path: str | None = None

    # Source mapping: Track line numbers for directives and keys
    # Format: {"IDENTITY": 5, "IDENTITY.Name": 6, "PRODUCT": 10, ...}
    source_map: dict[str, int] = field(default_factory=dict)

    # Preserved comments: Track comments for debugging/reference
    # Format: {line_number: "comment text", ...}
    comments: dict[int, str] = field(default_factory=dict)
