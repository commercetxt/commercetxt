"""
Logic for Multi-File Fractal Inheritance and Locale Resolution.
Find the file. Merge the data. Stay secure.

FIX: Robust Windows drive letter detection to prevent false positives.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .model import ParseResult
from .security import is_safe_url


class CommerceTXTResolver:
    """
    Handles data inheritance.
    It combines parent and child files. The child is the final word.

    Enhancement: Tracks visited paths to detect circular dependencies.
    """

    def __init__(self) -> None:
        """Initialize resolver with circular dependency tracking."""
        self._visited_paths: set[str] = set()

    def reset_tracking(self):
        """Reset circular dependency tracking (useful for tests)."""
        self._visited_paths.clear()

    def resolve_locales(self, root_result: ParseResult, target_locale: str) -> str:
        """Find the path for a locale. It falls back if it must."""
        locales = root_result.directives.get("LOCALES", {})
        locales_lower = {k.lower(): v for k, v in locales.items()}
        target_lower = target_locale.lower()

        if target_lower in locales_lower:
            return self._extract_path(locales_lower[target_lower])

        if "-" in target_lower:
            lang_code = target_lower.split("-")[0]
            if lang_code in locales_lower:
                return self._extract_path(locales_lower[lang_code])

        return "/"

    def _extract_path(self, value: str) -> str:
        """
        Extract path from locale value, handling:
        - Pipe metadata: "path | Note: ..."
        - Trailing annotations: "path (Current)"
        - Whitespace in paths: should preserve if quoted
        """
        path_part = value.split("|", 1)[0].strip()

        # Remove trailing annotations like "(Current)"
        path_part = re.sub(r"\s*\([^)]+\)$", "", path_part)

        # Extract first non-whitespace token
        # (Assumption: paths don't contain spaces - per CommerceTXT spec)
        path_match = re.match(r"^([^\s]+)", path_part)
        return path_match.group(1) if path_match else path_part

    def merge(self, parent: ParseResult, child: ParseResult) -> ParseResult:
        """
        Two results become one. The child overwrites the parent.

        Enhancement: Detects circular dependencies by tracking file paths.
        """

        parent_path = getattr(parent, "_source_path", None) or getattr(
            parent, "source_file", None
        )
        if parent_path:
            self._visited_paths.add(parent_path)

        child_path = getattr(child, "_source_path", None) or getattr(
            child, "source_file", None
        )
        if child_path:
            if child_path in self._visited_paths:
                chain = " -> ".join(sorted(self._visited_paths))
                raise ValueError(
                    "Circular dependency detected: "
                    f"'{child_path}' is included multiple times in the inheritance chain."  # noqa: E501
                    f" Previously visited paths: {chain}"
                )
            self._visited_paths.add(child_path)

        merged = ParseResult()
        merged.directives = self._deep_merge(parent.directives, child.directives)
        merged.version = child.version or parent.version
        merged.last_updated = child.last_updated or parent.last_updated
        merged.errors = list(set(parent.errors + child.errors))
        merged.warnings = list(set(parent.warnings + child.warnings))
        merged.trust_flags = list(set(parent.trust_flags + child.trust_flags))

        # Preserve source path tracking
        if child_path:
            merged._source_path = child_path

        return merged

    def _deep_merge(
        self, parent: dict[str, Any], child: dict[str, Any]
    ) -> dict[str, Any]:
        """Recursive merge for nested dictionaries."""
        result = parent.copy()
        for key, child_val in child.items():
            if key not in result:
                result[key] = child_val
            else:
                parent_val = result[key]
                if isinstance(parent_val, dict) and isinstance(child_val, dict):
                    result[key] = self._deep_merge(parent_val, child_val)
                else:
                    result[key] = child_val
        return result


# =============================================================================
# FIX #3: Robust Windows Drive Letter Detection
# =============================================================================
# Problem: Original code was too simple: len(path) > 1 and path[1] == ":"
# Issues:
#   - "file:C:\path" would incorrectly match as Windows drive
#   - "http://example.com" would match if length check failed
#   - Didn't validate slash after colon
#
# Solution: Use regex to ensure proper format: [A-Z]:[/\] at start of string
# =============================================================================

_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:[/\\]")


def _is_windows_absolute_path(path: str) -> bool:
    r"""
    Validates Windows absolute paths like C:\path or C:/path.

    Requirements:
    1. Single letter (A-Z, case insensitive)
    2. Colon (:)
    3. Forward slash (/) or backslash (\)
    4. Must be at start of string

    Excludes:
    - URL schemes (http:, file:, ftp:)
    - Relative paths (file.txt, ../path)
    - UNC paths (\\server\share) - handled separately

    Examples:
        Valid: C:\Users\file.txt
        Valid: D:/data/commerce.txt
        Valid: c:\temp\test.txt (case insensitive)
        Invalid: file:C:\path (URL scheme)
        Invalid: http://example.com (URL)
        Invalid: relative.txt (relative path)
        Invalid: \\server\share (UNC path)
    """
    return bool(_WINDOWS_DRIVE_PATTERN.match(path))


def resolve_path(path: str, loader: Callable[[str], str]) -> ParseResult:
    """
    Load and parse a file. Check security first.
    A brave man does not open dangerous doors.
    """
    result = ParseResult()

    # =======================================================================
    # SECURITY VALIDATION (Multi-Stage)
    # =======================================================================

    # Stage 1: Protocol Check (SSRF Prevention)
    # -----------------------------------------
    # Allow: Windows absolute paths (C:\, D:/)
    # Allow: Relative paths (/path/to/file, ./file, ../file)
    # Block: Dangerous URL schemes (file:, ftp:, gopher:, data:)
    # Allow: http/https (validated separately by is_safe_url)

    is_win_absolute = _is_windows_absolute_path(path)

    # Check for colon that's NOT part of Windows drive letter
    has_scheme_colon = ":" in path and not is_win_absolute

    if has_scheme_colon:
        # It's a URL-like path - validate with is_safe_url
        if not is_safe_url(path):
            result.errors.append(f"Security: Blocked unsafe URL scheme in '{path}'")
            return result

    # Stage 2: Path Traversal Prevention
    # -----------------------------------
    # Block: .. (parent directory traversal)
    # Block: Absolute system paths (/etc, /root, /var, ~)
    # Block: Windows UNC paths (\\server\share)
    # Block: Windows System32
    # Allow: Relative paths and temp directories

    is_traversal = ".." in path

    # Dangerous Unix system paths
    unix_system_paths = ("/etc", "/root", "/var", "~")
    is_unix_system = any(path.startswith(prefix) for prefix in unix_system_paths)

    # Windows-specific checks
    is_unc_path = path.startswith("\\\\")
    is_windows_system = "Windows\\System32" in path or "Windows/System32" in path

    # Combined system path check
    is_system_path = is_unix_system or is_unc_path or is_windows_system

    if is_traversal or is_system_path:
        result.errors.append(f"Security: Path traversal attempt '{path}'")
        return result

    # =======================================================================
    # SAFE TO LOAD
    # =======================================================================

    try:
        content = loader(path)
        from .parser import CommerceTXTParser

        parser = CommerceTXTParser()
        return parser.parse(content)

    except FileNotFoundError:
        result.errors.append(f"404: File not found '{path}'")
    except Exception as e:
        result.errors.append(f"Failed to load {path}: {e!s}")

    return result
