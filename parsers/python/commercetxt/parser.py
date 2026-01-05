"""
Reference parser for CommerceTXT v1.0.3.
Read the file. Extract the data. Stay safe.

Universal BOM handling for UTF-8/UTF-16/UTF-32.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from .limits import MAX_FILE_SIZE, MAX_LINE_LENGTH, MAX_NESTING_DEPTH, MAX_SECTIONS
from .logging_config import get_logger
from .metrics import get_metrics
from .model import ParseResult

_SECTION_RE = re.compile(r"^#\s*@(\w+)\s*$")
_DIRECTIVE_START_RE = re.compile(r"^#\s*@")
_KV_RE = re.compile(r"^([\w-]+):\s*(.*)$")
_LIST_RE = re.compile(r"^(\s*)-\s*(.*)$")

# Constants for indent detection
MAX_REASONABLE_INDENT = 8


# ============================================================================
# UTF-16/32 Helper Functions
# ============================================================================


def _try_read_with_encoding(file_path: Path, encoding: str) -> tuple[str, str] | None:
    """
    Try to read file with specific encoding.

    Args:
        file_path: Path to the file
        encoding: Encoding to try

    Returns:
        Tuple of (content, encoding) if successful, None if failed
    """
    try:
        with open(file_path, encoding=encoding) as f:
            content = f.read()
            return content, encoding
    except (UnicodeDecodeError, UnicodeError):
        return None


def read_commerce_file(
    file_path: str | Path, encoding: str | None = None
) -> tuple[str, str]:
    """
    Read a CommerceTXT file with automatic encoding detection.

    This helper function handles UTF-8, UTF-16 (LE/BE), and UTF-32 (LE/BE)
    encoded files automatically. Useful for reading Excel exports which often
    use UTF-16.

    Args:
        file_path: Path to the commerce.txt file
        encoding: Specific encoding to use (optional). If None, auto-detects.

    Returns:
        Tuple of (content: str, detected_encoding: str)

    Raises:
        FileNotFoundError: If file doesn't exist
        UnicodeDecodeError: If file cannot be decoded with any supported encoding

    Example:
        >>> content, encoding = read_commerce_file("commerce.txt")
        >>> parser = CommerceTXTParser()
        >>> result = parser.parse(content)
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # If specific encoding requested, use it
    if encoding is not None:
        result = _try_read_with_encoding(file_path, encoding)
        if result is not None:
            return result
        raise UnicodeDecodeError(
            encoding, b"", 0, 0, f"Could not decode file with encoding: {encoding}"
        )

    # Auto-detect encoding by trying common ones
    from .constants import SUPPORTED_ENCODINGS

    for enc in SUPPORTED_ENCODINGS:
        result = _try_read_with_encoding(file_path, enc)
        if result is not None:
            return result

    # If all encodings failed, raise descriptive error
    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        0,
        f"Could not decode file with any supported encoding: {SUPPORTED_ENCODINGS}",
    )


def parse_file(
    file_path: str | Path,
    encoding: str | None = None,
    strict: bool = False,
    auto_detect_indent: bool = True,
) -> ParseResult:
    """
    Convenience function to parse a CommerceTXT file directly.

    Combines file reading (with encoding detection) and parsing in one step.

    Args:
        file_path: Path to the commerce.txt file
        encoding: Specific encoding to use (optional, auto-detects if None)
        strict: Enable strict parsing mode (raises ValueError on issues)
        auto_detect_indent: Auto-detect indentation width

    Returns:
        ParseResult with parsed data

    Example:
        >>> # Parse with auto-detection
        >>> result = parse_file("commerce.txt")
        >>>
        >>> # Parse UTF-16 Excel export explicitly
        >>> result = parse_file("excel_export.txt", encoding="utf-16")
        >>>
        >>> # Strict mode
        >>> result = parse_file("commerce.txt", strict=True)
    """
    content, detected_encoding = read_commerce_file(file_path, encoding)

    logger = get_logger(__name__)
    logger.debug(f"Detected encoding: {detected_encoding} for {file_path}")

    parser = CommerceTXTParser(strict=strict, auto_detect_indent=auto_detect_indent)
    result = parser.parse(content)

    # Store metadata about the file
    result.source_file = str(file_path)
    result.encoding = detected_encoding
    result._source_path = str(file_path)  # For resolver circular dependency tracking

    return result


# ============================================================================


class CommerceTXTParser:
    """The main engine for reading CommerceTXT files."""

    def __init__(
        self,
        strict: bool = False,
        nested: bool = True,
        indent_width: int = 2,
        auto_detect_indent: bool = True,
        **kwargs,
    ):
        self.strict = strict
        self.nested = nested
        self.indent_width = indent_width
        self.auto_detect_indent = auto_detect_indent
        self.logger = kwargs.get("logger") or get_logger(__name__)
        self.metrics = kwargs.get("metrics") or get_metrics()

    def parse(self, content: str) -> ParseResult:
        """Parse raw text into a data object."""
        self.metrics.start_timer("parse")
        start_time = time.perf_counter()
        result = ParseResult()

        # Auto-detect indent width if enabled
        if self.auto_detect_indent:
            detected_width = self._detect_indent_width(content)
            if detected_width != self.indent_width:
                self.logger.debug(
                    f"Auto-detected indent width: {detected_width} "
                    f"(default was {self.indent_width})"
                )
                self.indent_width = detected_width

        # ===================================================================
        # BOM (Byte Order Mark) Removal
        # ===================================================================
        # Remove UTF-8 BOM (U+FEFF) if present at start of string.
        #
        # Note: parse() expects a str (already decoded).
        # For automatic encoding detection (UTF-8/16/32), use parse_file()
        # which handles BOM-based detection before calling parse().
        # ===================================================================
        if content.startswith("\ufeff"):
            content = content[1:]
            self.logger.debug("Removed UTF-8 BOM")
        # ===================================================================

        if not self._check_file_size(content, result):
            self.metrics.stop_timer("parse")
            return result

        self.logger.debug(f"Starting parse of {len(content)} chars")
        state: dict[str, Any] = {"current_section": None, "indent_stack": []}
        sections_count = 0

        for line_no, raw_line in enumerate(content.splitlines(), 1):
            sections_count = self._process_line(
                raw_line, line_no, result, state, sections_count
            )

        duration = time.perf_counter() - start_time
        self.logger.info(
            f"Parsed successfully: {len(result.directives)} sections, "
            f"{len(result.warnings)} warnings in {duration:.4f}s"
        )

        self.metrics.stop_timer("parse")
        self.metrics.gauge("parse_sections", len(result.directives))

        # Detect file level
        # Note: Directives are stored WITHOUT @ prefix (e.g., "CATALOG" not "@CATALOG")
        if "CATALOG" in result.directives:
            result.level = "root"
        elif "ITEMS" in result.directives or "FILTERS" in result.directives:
            result.level = "category"
        elif "PRODUCT" in result.directives:
            result.level = "product"

        return result

    def _check_file_size(self, content: str, result: ParseResult) -> bool:
        if len(content) > MAX_FILE_SIZE:
            self.logger.error(f"File too large: {len(content)} chars")
            result.errors.append(
                f"Security: File too large ({len(content)} chars). "
                f"Max allowed: {MAX_FILE_SIZE}"
            )
            return False
        return True

    def _process_line(
        self,
        raw_line: str,
        line_no: int,
        result: ParseResult,
        state: dict,
        sections_count: int,
    ) -> int:
        """Handles logic for a single line."""
        if len(raw_line) > MAX_LINE_LENGTH:
            self._warn(
                f"Line {line_no}: Exceeds max length ({len(raw_line)} chars), "
                f"truncating to {MAX_LINE_LENGTH}",
                result,
            )
            raw_line = raw_line[:MAX_LINE_LENGTH]

        line = raw_line.strip()
        if not line:
            return sections_count

        indent = len(raw_line) - len(raw_line.lstrip())
        if indent % self.indent_width != 0 and indent > 0:
            msg = (
                f"Line {line_no}: Inconsistent indentation ({indent} spaces) "
                f"for indent_width={self.indent_width}"
            )
            if self.strict:
                raise ValueError(msg)
            self._warn(msg, result)

        if line.startswith("#"):
            # Check if it's a directive (@SECTION) or a comment
            if line.startswith("# @") or line.startswith("#@"):
                # It's a directive/section
                return self._handle_section(
                    line, line_no, result, state, sections_count
                )
            else:
                # It's a comment - preserve it
                comment_text = line[1:].strip()  # Remove leading #
                if comment_text:  # Only store non-empty comments
                    result.comments[line_no] = comment_text
                return sections_count

        list_match = _LIST_RE.match(raw_line)
        if list_match:
            self._handle_list(list_match, indent, line_no, result, state)
            return sections_count

        kv_match = _KV_RE.match(line)
        if kv_match:
            self._handle_kv(kv_match, indent, line_no, result, state)
            return sections_count

        self._warn(f"Line {line_no}: Unknown syntax: {line[:50]}", result)
        return sections_count

    def _handle_section(
        self, line: str, line_no: int, result: ParseResult, state: dict, count: int
    ) -> int:
        section_match = _SECTION_RE.match(line)
        if section_match:
            if count >= MAX_SECTIONS:
                self._warn(
                    f"Line {line_no}: Max sections limit ({MAX_SECTIONS}) reached.",
                    result,
                )
                return count

            new_count = count + 1
            section_name = section_match.group(1).upper()
            state["current_section"] = section_name
            result.directives.setdefault(section_name, {})
            state["indent_stack"] = []

            # Clear last_empty_key when starting new section
            if "last_empty_key" in state:
                del state["last_empty_key"]

            # Track source location for this directive
            result.source_map[section_name] = line_no

            return new_count

        # Malformed section header detection (Spec Section 9.3)
        if "@" in line and _DIRECTIVE_START_RE.match(line):
            self._warn(
                f"Line {line_no}: Unknown syntax - "
                f"Malformed section header '{line}'",
                result,
            )

        return count

    def _handle_kv(self, match, indent, line_no, result, state) -> bool:
        """
        Handle key-value pairs.

        Spec: Keys are case-insensitive (for duplicate detection),
        but we preserve the original case for storage.
        """
        key_original = match.group(1).strip()
        key_lower = key_original.lower()
        value = match.group(2).strip()

        if not state["current_section"]:
            # Global keys (Version, LastUpdated)
            if key_lower == "version":
                result.version = value
                result.source_map["version"] = line_no
            elif key_lower == "lastupdated":
                result.last_updated = value
                result.source_map["lastupdated"] = line_no
            return True

        current_section = state["current_section"]
        section_data = result.directives[current_section]

        # Clear last_empty_key when we encounter a new key
        # (list items for previous empty key are done)
        if "last_empty_key" in state and state["last_empty_key"] != key_original:
            del state["last_empty_key"]

        # Case-insensitive duplicate detection:
        # If a lowercase variant exists, remove it before adding new key
        existing_key = self._find_case_insensitive_key(section_data, key_original)

        if existing_key and existing_key != key_original:
            del section_data[existing_key]

        # Parse value - handle multi-value (pipe-separated) or simple value
        if "|" in value:
            parsed_val = self._parse_multi_value(value)
            # Unwrap single "value" or "url" to maintain string primitives
            if isinstance(parsed_val, dict) and len(parsed_val) == 1:
                if "value" in parsed_val:
                    section_data[key_original] = parsed_val["value"]
                elif "url" in parsed_val:
                    section_data[key_original] = parsed_val["url"]
                else:
                    section_data[key_original] = parsed_val
            else:
                section_data[key_original] = parsed_val
        elif value:  # Only store non-empty values
            section_data[key_original] = value
        else:
            # Empty value - remember this key for list handling
            # The next list items will populate this key
            state["last_empty_key"] = key_original

        # Track source location: "SECTION.Key" format
        source_key = f"{current_section}.{key_original}"
        result.source_map[source_key] = line_no

        return True

    def _find_case_insensitive_key(self, data: dict, key: str) -> str | None:
        """Find a key in dict using case-insensitive comparison."""
        key_lower = key.lower()
        for existing_key in data:
            if str(existing_key).lower() == key_lower:
                return str(existing_key)
        return None

    def _handle_list(self, match, indent, line_no, result, state) -> bool:
        if not state["current_section"]:
            return False

        if len(state["indent_stack"]) >= MAX_NESTING_DEPTH:
            self._warn(
                f"Line {line_no}: Max nesting depth ({MAX_NESTING_DEPTH}) exceeded",
                result,
            )
            return False

        current_level = indent // self.indent_width
        entry = self._parse_list_item_content(match.group(2).strip())
        section_data = result.directives[state["current_section"]]

        if not self.nested:
            section_data.setdefault("items", []).append(entry)
            return True

        stack = state["indent_stack"]
        while stack and current_level <= stack[-1][0]:
            stack.pop()

        if not stack:
            # Use last_empty_key if available (e.g., "Options:" followed by list)
            # Otherwise use default "items" key
            list_key = state.get("last_empty_key", "items")
            target_container = section_data.setdefault(list_key, [])
            # Don't clear last_empty_key here - it persists for all list items
        else:
            _, parent_ref = stack[-1]
            if isinstance(parent_ref, list):
                target_container = parent_ref
            else:
                if "children" not in parent_ref:
                    parent_ref["children"] = []
                target_container = parent_ref["children"]

        target_container.append(entry)
        if isinstance(entry, dict):
            stack.append((current_level, entry))
        return True

    def _parse_list_item_content(self, item: str) -> dict[str, Any]:
        if self._is_url_start(item, 0):
            if "|" in item:
                val_part, rest = item.split("|", 1)
                entry: dict[str, Any] = {"value": val_part.strip()}
                entry.update(self._parse_multi_value(rest))
                return entry
            return {"value": item.strip()}

        if ":" in item:
            name, rest = item.split(":", 1)
            # Check if it's a URL scheme
            if self._is_url_scheme(name) and rest.strip().startswith("//"):
                if "|" not in item:
                    return {"value": item.strip()}

            # Named entry - preserve original case but aware of duplicates
            # Note: Duplicate detection for list items happens at a higher level
            # (validator or merge logic), so we just preserve the name here
            named_entry: dict[str, Any] = {"name": name.strip()}
            rest = rest.strip()

            if "|" in rest:
                val_part, meta_part = rest.split("|", 1)
                named_entry["path"] = val_part.strip() or None
                named_entry.update(self._parse_multi_value(meta_part))
            else:
                named_entry["path"] = rest or None

            return named_entry

        return {"value": item.strip()}

    def _smart_split_by_pipe(self, text: str) -> list[str]:
        """
        Split text by pipe (|) but avoid breaking URLs with query params.

        Examples:
            "Note: Test | URL: http://ex.com" -> ["Note: Test", "URL: http://ex.com"]
            "http://ex.com?a=1|b=2 | Note: X" -> ["http://ex.com?a=1|b=2", "Note: X"]

        Strategy: Track if we're inside a URL context (after http://, https://, etc.)
        """
        parts = []
        current: list[str] = []
        i = 0
        in_url = False

        while i < len(text):
            char = text[i]

            # Check if starting a URL
            if not in_url:
                if self._is_url_start(text, i):
                    in_url = True
                elif text[i : i + 2] == "//" and (
                    not current or current[-1] in (" ", ":")
                ):
                    in_url = True

            # Pipe handling
            if char == "|":
                current_str = "".join(current)
                if in_url and "?" in current_str:
                    current.append(char)  # Query param pipe
                else:
                    in_url = False
                    if current:
                        parts.append(current_str.strip())
                        current = []
            else:
                current.append(char)
                if in_url and char == " ":
                    in_url = False  # Exit URL on whitespace

            i += 1

        if current:
            parts.append("".join(current).strip())

        # Filter out empty parts while maintaining order
        return [p for p in parts if p]

    def _parse_multi_value(self, value: str) -> dict[str, Any]:
        """
        Parse pipe-separated values into a dictionary.

        Handles URLs carefully to avoid incorrect splitting.
        Preserves original case for keys, but handles duplicates case-insensitively.
        Example: "https://example.com | Note: test" -> {"url": "...", "Note": "test"}

        Smart splitting: Avoids breaking URLs with query params (e.g., url?a=1|b=2)
        """
        res: dict[str, Any] = {}
        parts = self._smart_split_by_pipe(value)
        unnamed = []

        for part in parts:
            if not part:
                continue

            # Check if this looks like a URL (starts with http:// or https://)
            if self._is_url_start(part, 0):
                if "url" not in res:
                    res["url"] = part
                else:
                    unnamed.append(part)
                continue

            # Check for key:value pairs
            if ":" in part:
                k, v = part.split(":", 1)
                k_original = k.strip()
                v_stripped = v.strip()

                # Double-check it's not a URL that got split
                if k_original.lower() in ("http", "https") and v_stripped.startswith(
                    "//"
                ):
                    if "url" not in res:
                        res["url"] = part
                    else:
                        unnamed.append(part)
                else:
                    # Case-insensitive duplicate check
                    existing_key = self._find_case_insensitive_key(res, k_original)
                    if existing_key and existing_key != k_original:
                        del res[existing_key]
                    res[k_original] = v_stripped
            else:
                unnamed.append(part)

        if unnamed:
            if len(unnamed) == 1:
                if not res:
                    res["value"] = unnamed[0]
                elif "value" not in res:
                    res["value"] = unnamed[0]
                else:
                    # Collision? Add anyway or ignore
                    pass
            else:
                res["values"] = unnamed
                if "value" not in res:
                    res["value"] = unnamed[0]

        return res

    def _is_url_start(self, text: str, pos: int) -> bool:
        """Check if position starts a URL scheme."""
        if pos >= len(text) - 7:
            return False
        chunk = text[pos : pos + 8].lower()
        schemes = ("http://", "https://", "ftp://", "ws://", "wss://")
        return chunk.startswith(schemes)

    def _is_url_scheme(self, text: str) -> bool:
        """Check if text is a known URL scheme (without ://)."""
        return text.lower() in (
            "http",
            "https",
            "ftp",
            "ftps",
            "ws",
            "wss",
            "file",
            "data",
            "blob",
        )

    def _detect_indent_width(self, content: str) -> int:
        """
        Auto-detect indent width from first indented lines.

        Uses frequency-based detection (most common indent) rather than GCD,
        which is more robust against typos and mixed indentation.

        Also handles tabs by converting them to spaces.

        Returns:
            Detected indent width (typically 2, 4, or 8)
        """
        indent_widths = []

        for line in content.splitlines()[:100]:  # Check first 100 lines
            if not line or line[0] not in (" ", "\t"):
                continue

            # Convert tabs to 4 spaces (common convention)
            line_expanded = line.expandtabs(4)

            # Count leading spaces
            spaces = len(line_expanded) - len(line_expanded.lstrip(" "))
            if spaces > 0:
                indent_widths.append(spaces)

        if not indent_widths:
            return 2  # Default fallback

        # Frequency-based detection: find most common indent
        from collections import Counter

        counts = Counter(indent_widths)

        # Get most common indents
        most_common = counts.most_common(5)  # Top 5

        # Prefer standard values (2, 4, 8) if they appear
        for indent, count in most_common:
            if indent in (2, 4, 8) and count > 1:
                return indent

        # If no standard value, use the most frequent one
        if most_common:
            most_frequent = most_common[0][0]

            # Sanity check: reasonable indent size
            if most_frequent <= MAX_REASONABLE_INDENT:
                return most_frequent
            else:
                # Too large, likely tab-based or unusual - cap at 8
                return MAX_REASONABLE_INDENT

        return 2  # Final fallback

    def _warn(self, message: str, result: ParseResult):
        result.warnings.append(message)
        self.logger.warning(message)
        if self.strict:
            raise ValueError(message)
