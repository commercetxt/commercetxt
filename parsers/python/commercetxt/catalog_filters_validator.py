"""
Catalog and Filters Validator.

Validates @CATALOG and @FILTERS sections per CommerceTXT Protocol.
"""

from typing import Any

from .constants import MAX_FILTER_OPTIONS, MAX_FILTER_VALUE_LENGTH
from .model import ParseResult


class CatalogFiltersValidator:
    """
    Validates @CATALOG and @FILTERS according to CommerceTXT Protocol.

    @CATALOG (Section 4.2):
    - Purpose: Maps category names to their context files
    - Location: Root file only
    - Syntax: List items with format: `- CategoryName: /path/to/file.txt`

    @FILTERS (Section 4.3):
    - Purpose: Defines available attributes for filtering products
    - Location: Category files
    - Syntax: Key-value pairs where values are list or range descriptions
    """

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_catalog(
        self, catalog_data: dict[str, Any], file_level: str = "root"
    ) -> bool:
        """
        Validates @CATALOG directive structure and semantics.

        Args:
            catalog_data: Parsed @CATALOG section
            file_level: "root" | "category" | "product"

        Returns:
            bool: True if valid, False otherwise
        """
        # Rule 1: @CATALOG only in root files
        if file_level != "root":
            self._error(
                f"@CATALOG directive only allowed in root files, "
                f"found in {file_level} file"
            )
            return False

        # Rule 2: Must have items
        items = catalog_data.get("items", [])
        if not items:
            self._error("@CATALOG is empty - must contain at least 1 category")
            return False

        # Rule 3: Validate each catalog entry
        valid_paths = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                self._warning(f"@CATALOG item {idx}: Expected dict, got {type(item)}")
                continue

            name = item.get("name")
            path = item.get("path") or item.get("value")

            # Check name
            if not name:
                self._error(f"@CATALOG item {idx}: Missing category name")
                continue

            # Check path
            if not path:
                self._error(f"@CATALOG item {idx} ({name}): Missing file path")
                continue

            # Validate path format
            path_valid, path_warning = self._validate_path_format(path)
            if path_warning:
                self._warning(f"@CATALOG item '{name}': {path_warning}")
            if not path_valid:
                self._error(
                    f"@CATALOG item '{name}': Invalid path '{path}' "
                    f"(must start with / and end with .txt)"
                )
                continue

            # Check for duplicates
            if path in valid_paths:
                self._warning(
                    f"@CATALOG: Duplicate path '{path}' " f"(category '{name}')"
                )
            else:
                valid_paths.append(path)

        return len(self.errors) == 0

    def validate_filters(
        self, filters_data: dict[str, Any], file_level: str = "category"
    ) -> bool:
        """
        Validates @FILTERS directive structure and semantics.

        Args:
            filters_data: Parsed @FILTERS section
            file_level: "root" | "category" | "product"

        Returns:
            bool: True if valid, False otherwise
        """
        # Rule 1: @FILTERS typically in category files
        if file_level == "product":
            self._warning(
                "@FILTERS in product file is unusual - "
                "typically belongs in category files"
            )

        # Rule 2: Must have at least one filter
        # Exclude 'items' key if it exists from parsing artifacts
        actual_filters = {k: v for k, v in filters_data.items() if k != "items"}

        if not actual_filters:
            self._warning("@FILTERS is empty - no filterable attributes defined")
            return True  # Warning only, not error

        # Rule 3: Validate common filter patterns
        for key, value in actual_filters.items():
            self._validate_filter_value(key, value)

        # Rule 4: Recommend standard filter names
        self._check_standard_filters(actual_filters)

        return len(self.errors) == 0

    def _validate_filter_value(self, key: str, value: Any) -> None:
        """Validates individual filter value formats."""
        value_str = str(value).strip()

        # Pattern 1: Comma-separated list (e.g., "Sony, Bose, Apple")
        if "," in value_str:
            items = [item.strip() for item in value_str.split(",")]
            if len(items) > MAX_FILTER_OPTIONS:
                self._warning(
                    f"@FILTERS '{key}': Too many options ({len(items)}). "
                    f"Consider grouping or using ranges."
                )
            return

        # Pattern 2: Range (e.g., "$50 - $500", "1-10")
        if "-" in value_str or "to" in value_str.lower():
            # Valid range format
            return

        # Pattern 3: Boolean-like (Yes/No, True/False)
        if value_str.lower() in ("yes", "no", "true", "false"):
            return

        # Pattern 4: Single value (acceptable but less useful)
        if len(value_str) < MAX_FILTER_VALUE_LENGTH:  # Reasonable length
            return

        # If we reach here, the value might be malformed
        self._warning(
            f"@FILTERS '{key}': Unusual value format '{value_str[:50]}...'. "
            f"Expected comma-separated list or range."
        )

    def _check_standard_filters(self, filters: dict[str, Any]) -> None:
        """Recommends standard filter names for better AI understanding."""
        standard_filters = {
            "Brands": "Brand",
            "PriceRange": "Price",
            "Type": "ProductType",
            "Features": "Feature",
            "Colors": "Color",
            "Sizes": "Size",
            "Materials": "Material",
            "Categories": "Category",
        }

        filter_keys_lower = {k.lower(): k for k in filters.keys()}

        for standard, alternative in standard_filters.items():
            if (
                standard.lower() not in filter_keys_lower
                and alternative.lower() not in filter_keys_lower
            ):
                continue

            # If found with different casing, suggest standard
            actual_key = filter_keys_lower.get(
                standard.lower()
            ) or filter_keys_lower.get(alternative.lower())

            if actual_key and actual_key != standard:
                # This is just informational, not a warning
                pass

    def _validate_path_format(self, path: str) -> tuple[bool, str | None]:
        """
        Validates path format according to spec.

        Returns:
            tuple: (is_valid, warning_message)
                - is_valid: True if path is valid
                - warning_message: Optional warning about path format issues

        Spec: Section 4.2 - Paths must start with / and end with .txt
        """
        warning = None

        # Check for Windows-style separators (common mistake)
        if "\\" in path:
            warning = (
                f"Path '{path}' uses Windows-style separators (\\). "
                f"Use forward slashes (/) per spec Section 4.2."
            )
            return False, warning

        # Must start with / (absolute path)
        if not path.startswith("/"):
            return False, None

        # Must end with .txt
        if not path.endswith(".txt"):
            return False, None

        # Check for path traversal attempts
        if ".." in path:
            return False, None

        return True, None

    def _is_valid_path(self, path: str) -> bool:
        """Legacy compatibility wrapper for _validate_path_format."""
        valid, _ = self._validate_path_format(path)
        return valid

    def _validate_items(self, result: ParseResult) -> None:
        """
        Validates @ITEMS (Spec Section 4.4).

        Checks that product paths follow the same format as catalog paths:
        - Must start with /
        - Must end with .txt
        - No path traversal (..)
        """
        items = result.directives.get("ITEMS", {}).get("items", [])
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                self._warning(f"@ITEMS item {idx}: Expected dict, got {type(item)}")
                continue

            path = item.get("path") or item.get("value")
            if path:
                valid, warning = self._validate_path_format(path)
                if warning:
                    self._warning(f"@ITEMS item {idx}: {warning}")
                if not valid:
                    name = item.get("name", f"item {idx}")
                    self._error(
                        f"@ITEMS '{name}': Invalid path '{path}' "
                        f"(must start with / and end with .txt)"
                    )

    def _error(self, message: str) -> None:
        """Records an error."""
        self.errors.append(message)
        if self.strict:
            raise ValueError(message)

    def _warning(self, message: str) -> None:
        """Records a warning."""
        self.warnings.append(message)

    def get_report(self) -> dict[str, Any]:
        """Returns validation report."""
        return {
            "valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
        }
