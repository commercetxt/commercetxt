"""
Logic for Multi-File Fractal Inheritance and Locale Resolution.
Find the file. Merge the data. Stay secure.
"""

from typing import Any, Callable, Dict
from .model import ParseResult
from .security import is_safe_url


class CommerceTXTResolver:
    """
    Handles data inheritance.
    It combines parent and child files. The child is the final word.
    """

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
        """Get the path from the string. Remove the noise."""
        return value.split()[0].strip()

    def merge(self, parent: ParseResult, child: ParseResult) -> ParseResult:
        """Two results become one. The child overwrites the parent."""
        merged = ParseResult()
        merged.directives = self._deep_merge(parent.directives, child.directives)
        merged.version = child.version or parent.version
        merged.last_updated = child.last_updated or parent.last_updated
        merged.errors = list(set(parent.errors + child.errors))
        merged.warnings = list(set(parent.warnings + child.warnings))
        merged.trust_flags = list(set(parent.trust_flags + child.trust_flags))
        return merged

    def _deep_merge(
        self, parent: Dict[str, Any], child: Dict[str, Any]
    ) -> Dict[str, Any]:
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


def resolve_path(path: str, loader: Callable[[str], str]) -> ParseResult:
    """
    Load and parse a file. Check security first.
    A brave man does not open dangerous doors.
    """
    result = ParseResult()

    # 1. SSRF & Protocol Check
    # We ignore Windows drive letters (A-Z:) but block other colon protocols.
    is_win_drive = len(path) > 1 and path[0].isalpha() and path[1] == ":"
    if ":" in path and not is_win_drive:
        if not is_safe_url(path):
            result.errors.append(f"Security: Blocked unsafe path '{path}'")
            return result

    # 2. Path Traversal & System Path Protection
    # The tests expect exactly 'Security: Path traversal' for these.
    is_traversal = ".." in path

    # We block dangerous Unix roots and Windows UNC/System paths.
    # Relative paths and temp paths on Windows should pass.
    is_system = (
        path.startswith(("/etc", "/root", "/var", "~"))
        or path.startswith("\\\\")
        or "Windows\\System32" in path
    )

    if is_traversal or is_system:
        result.errors.append(f"Security: Path traversal attempt '{path}'")
        return result

    # 3. Load Content
    try:
        content = loader(path)
        from .parser import CommerceTXTParser

        parser = CommerceTXTParser()
        return parser.parse(content)

    except FileNotFoundError:
        result.errors.append(f"404: File not found '{path}'")
    except Exception as e:
        result.errors.append(f"Failed to load {path}: {str(e)}")

    return result
