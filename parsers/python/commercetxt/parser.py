"""
Reference parser for CommerceTXT v1.0.1.
Read the file. Extract the data. Stay safe.
"""

import re
import time
from typing import Any, Dict
from .logging_config import get_logger
from .model import ParseResult
from .metrics import get_metrics
from .limits import MAX_FILE_SIZE, MAX_LINE_LENGTH, MAX_SECTIONS, MAX_NESTING_DEPTH

# Compile regex patterns once at module level for performance.
_SECTION_RE = re.compile(r"^#\s*@([A-Za-z0-9_]+)\s*$")
_DIRECTIVE_START_RE = re.compile(r"^#\s*@")
_KV_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
_LIST_RE = re.compile(r"^(\s*)-\s*(.*)$")


class CommerceTXTParser:
    """The main engine for reading CommerceTXT files."""

    def __init__(
        self,
        strict: bool = False,
        nested: bool = True,
        indent_width: int = 2,
        logger=None,
        metrics=None,
    ):
        self.strict = strict
        self.nested = nested
        self.indent_width = indent_width
        self.logger = logger or get_logger(__name__)
        self.metrics = metrics or get_metrics()

    def parse(self, content: str) -> ParseResult:
        """Parse raw text into a data object."""
        self.metrics.start_timer("parse")
        start_time = time.perf_counter()

        result = ParseResult()

        # Remove UTF-8 BOM if present. Fixes header detection on the first line.
        if content.startswith("\ufeff"):
            content = content.lstrip("\ufeff")

        # Check file size first. Do not waste time on huge files.
        if len(content) > MAX_FILE_SIZE:
            self.logger.error(f"File too large: {len(content)} bytes")
            result.errors.append(
                f"Security: File too large ({len(content)} bytes). Max allowed: {MAX_FILE_SIZE}"
            )
            self.metrics.stop_timer("parse")
            return result

        self.logger.debug(f"Starting parse of {len(content)} bytes")

        state: Dict[str, Any] = {"current_section": None, "indent_stack": []}
        sections_count = 0

        for line_no, raw_line in enumerate(content.splitlines(), 1):
            # Guard against long lines. Prevent ReDoS attacks.
            if len(raw_line) > MAX_LINE_LENGTH:
                self._warn(
                    f"Line {line_no}: Exceeds max length ({len(raw_line)} chars), truncating to {MAX_LINE_LENGTH}",
                    result,
                )
                raw_line = raw_line[:MAX_LINE_LENGTH]

            line = raw_line.strip()
            if not line:
                continue

            # Calculate indentation.
            indent = len(raw_line) - len(raw_line.lstrip())

            # Check indentation consistency.
            if indent % self.indent_width != 0 and indent > 0:
                self._warn(
                    f"Line {line_no}: Inconsistent indentation ({indent} spaces) "
                    f"for indent_width={self.indent_width}",
                    result,
                )

            # Look for section headers starting with # @.
            if line.startswith("#"):
                section_match = _SECTION_RE.match(line)
                if section_match:
                    # Enforce section limits.
                    if sections_count >= MAX_SECTIONS:
                        self._warn(
                            f"Line {line_no}: Max sections limit ({MAX_SECTIONS}) reached. Skipping.",
                            result,
                        )
                        continue

                    sections_count += 1
                    section_name = section_match.group(1).upper()
                    state["current_section"] = section_name
                    result.directives.setdefault(section_name, {})
                    state["indent_stack"] = []
                    continue

                    # If it looks like a directive but doesn't match the pattern, check if it's a comment.
                if _DIRECTIVE_START_RE.match(line):
                    pass
                else:
                    continue

            # Process list items starting with '-'.
            list_match = _LIST_RE.match(raw_line)
            if list_match:
                if self._handle_list(list_match, indent, line_no, result, state):
                    continue

            # Process key-value pairs.
            kv_match = _KV_RE.match(line)
            if kv_match:
                if self._handle_kv(kv_match, indent, line_no, result, state):
                    continue

            # If no pattern matches, the line has unknown syntax.
            self._warn(f"Line {line_no}: Unknown syntax: {line[:50]}", result)

        duration = time.perf_counter() - start_time
        self.logger.info(
            f"Parsed successfully: {len(result.directives)} sections, "
            f"{len(result.warnings)} warnings in {duration:.4f}s"
        )

        self.metrics.stop_timer("parse")
        self.metrics.gauge("parse_sections", len(result.directives))

        return result

    def _handle_kv(self, match, indent, line_no, result, state) -> bool:
        """Process a single key-value line."""
        key = match.group(1).strip()
        value = match.group(2).strip()

        # Handle top-level metadata like Version and LastUpdated.
        if not state["current_section"]:
            key_l = key.lower()
            if key_l == "version":
                result.version = value
            elif key_l == "lastupdated":
                result.last_updated = value
            return True

        current_section = state["current_section"]
        section_data = result.directives[current_section]

        # If value is empty, it might be the start of a nested list.
        if not value:
            section_data[key] = []
            if self.nested:
                # Use -1 to represent the key-level as the parent of the list.
                state["indent_stack"] = [(-1, section_data[key])]
        else:
            # Parse multiple values if pipe is present.
            section_data[key] = (
                self._parse_multi_value(value) if "|" in value else value
            )
            # Reset stack if we are back to root level.
            if self.nested and indent == 0:
                state["indent_stack"] = []
        return True

    def _handle_list(self, match, indent, line_no, result, state) -> bool:
        """Process an indented list item."""
        if not state["current_section"]:
            return False

        # Guard against recursive depth.
        if len(state["indent_stack"]) >= MAX_NESTING_DEPTH:
            self._warn(
                f"Line {line_no}: Max nesting depth ({MAX_NESTING_DEPTH}) exceeded",
                result,
            )
            return False

        current_level = indent // self.indent_width
        entry = self._parse_list_item_content(match.group(2).strip())
        current_section = state["current_section"]
        section_data = result.directives[current_section]

        if not self.nested:
            section_data.setdefault("items", []).append(entry)
            return True

        # Adjust the stack based on indentation level.
        stack = state["indent_stack"]
        while stack and current_level <= stack[-1][0]:
            stack.pop()

        if not stack:
            target_container = section_data.setdefault("items", [])
        else:
            _, parent_ref = stack[-1]
            if isinstance(parent_ref, list):
                target_container = parent_ref
            else:
                # If the parent is a dictionary, put children in a 'children' list.
                if "children" not in parent_ref:
                    parent_ref["children"] = []
                target_container = parent_ref["children"]

        target_container.append(entry)

        # If the entry is a dictionary, it can have children. Track it in the stack.
        if isinstance(entry, dict):
            stack.append((current_level, entry))
        return True

    def _parse_list_item_content(self, item: str) -> Dict[str, Any]:
        """Detect URLs or named paths in list items."""
        if self._is_url_start(item):
            if "|" in item:
                val_part, rest = item.split("|", 1)
                entry: Dict[str, Any] = {"value": val_part.strip()}
                entry.update(self._parse_multi_value(rest))
                return entry
            else:
                return {"value": item.strip()}

        if ":" in item:
            name, rest = item.split(":", 1)
            # Differentiate protocol (http:) from named path (CPU:).
            if name.lower() in ("http", "https") and rest.strip().startswith("//"):
                if "|" not in item:
                    return {"value": item.strip()}

            named_entry: Dict[str, Any] = {"name": name.strip()}
            rest = rest.strip()

            if "|" in rest:
                val_part, meta_part = rest.split("|", 1)
                named_entry["path"] = val_part.strip() or None
                named_entry.update(self._parse_multi_value(meta_part))
            else:
                named_entry["path"] = rest or None

            return named_entry

        return {"value": item.strip()}

    def _parse_multi_value(self, value: str) -> Dict[str, Any]:
        """Split pipes into a dictionary. Clean whitespace."""
        res = {}
        for part in map(str.strip, value.split("|")):
            if ":" in part:
                k, v = part.split(":", 1)
                # Handle URLs inside multi-value pipes.
                if k.lower() in ("http", "https") and v.strip().startswith("//"):
                    if "url" not in res:
                        res["url"] = part
                else:
                    res[k.strip()] = v.strip()
            elif "value" not in res:
                res["value"] = part
        return res

    def _is_url_start(self, text: str) -> bool:
        """Check if string looks like a URL."""
        return text.lower().startswith(("http://", "https://"))

    def _warn(self, message: str, result: ParseResult):
        """Log a warning. If strict, stop everything by raising ValueError."""
        result.warnings.append(message)
        self.logger.warning(message)
        if self.strict:
            raise ValueError(message)
