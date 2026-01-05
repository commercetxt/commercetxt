"""
Local storage driver for realtime data lookup.

Reads CommerceTXT files directly or from a JSON cache for fast hot-lookup.
Optimized version with caching, batch operations, and proper error handling.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from ..interfaces.base_storage import BaseRealtimeStorage

# Constants
MIN_VECTOR_ID_PARTS = 3  # Minimum parts in vector store ID (product_index_timestamp)

# Setup logging
logger = logging.getLogger(__name__)


class LocalStorage(BaseRealtimeStorage):
    """
    Reads directly from the source of truth (CommerceTXT files or JSON cache).
    Implements the 'Hot-Lookup' strategy with optimizations.

    Supports three modes:
    1. File-based: Reads .txt files from root_path on each request (slow but fresh)
    2. Cache-based: Reads from a pre-built JSON index (fast, needs periodic refresh)
    3. Hybrid: Uses cache with file fallback for cache misses

    Features:
    - TTL-based cache expiration
    - Batch file parsing for efficiency
    - Smart ID normalization
    - Comprehensive error handling
    - Performance metrics

    Example usage:
        # Cache-based with TTL (production)
        storage = LocalStorage(
            root_path="./products/",
            cache_file="./cache/products.json",
            cache_ttl=3600  # 1 hour
        )

        # Get live data
        data = storage.get_live_attributes(
            ["pixel-9-pro", "pixel-8a"], ["price", "availability"]
        )
    """

    # Field mappings from CommerceTXT directives to normalized keys
    FIELD_MAPPINGS: dict[str, list[str]] = {
        "price": ["PRICE", "Price"],
        "availability": ["AVAILABILITY", "Availability", "STOCK_STATUS"],
        "currency": ["CURRENCY", "Currency"],
        "stock": ["STOCK", "Stock", "QUANTITY"],
        "sku": ["SKU", "Sku"],
    }

    def __init__(
        self,
        root_path: str,
        cache_file: str | None = None,
        auto_refresh: bool = False,
        file_pattern: str = "*.txt",
        cache_ttl: int = 3600,  # 1 hour default
        enable_logging: bool = True,
    ):
        """
        Initialize LocalStorage.

        Args:
            root_path: Root directory containing CommerceTXT files
            cache_file: Optional JSON cache file for faster lookups
            auto_refresh: If True, rebuild cache on initialization
            file_pattern: Glob pattern for finding product files (default: *.txt)
            cache_ttl: Cache time-to-live in seconds (0 = no expiration)
            enable_logging: Enable logging output
        """
        self.root_path = Path(root_path)
        self.cache_file = Path(cache_file) if cache_file else None
        self.file_pattern = file_pattern
        self.cache_ttl = cache_ttl

        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_timestamps: dict[str, float] = {}
        self._file_index: dict[str, Path] = {}
        self._id_normalization_cache: dict[str, str] = {}

        # Performance metrics
        self._metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "file_reads": 0,
            "parse_errors": 0,
        }

        if enable_logging:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )

        # Build file index for fast lookups
        self._build_file_index()

        # Load or build cache
        if self.cache_file and self.cache_file.exists() and not auto_refresh:
            self._load_cache()
        elif auto_refresh:
            self.rebuild_cache()

    def _build_file_index(self) -> None:
        """Build an index mapping product IDs to file paths."""
        if not self.root_path.exists():
            logger.warning(f"Root path does not exist: {self.root_path}")
            return

        # Clear existing index and normalization cache when rebuilding
        self._file_index.clear()
        self._id_normalization_cache.clear()

        count = 0
        # Search recursively for product files
        for file_path in self.root_path.rglob(self.file_pattern):
            # Use filename (without extension) as the product ID
            product_id = file_path.stem.lower()
            # Also create slug version (e.g., "pixel-9-pro" from "Pixel 9 Pro")
            slug = re.sub(r"[^\w]+", "-", product_id).strip("-").lower()

            self._file_index[product_id] = file_path
            if slug != product_id:
                self._file_index[slug] = file_path
            count += 1

        logger.info(f"Indexed {count} product files")

    def _load_cache(self) -> None:
        """Load cache from JSON file with error handling."""
        if self.cache_file and self.cache_file.exists():
            try:
                with open(self.cache_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Support both old and new cache formats
                if isinstance(data, dict) and "cache" in data:
                    # New format with metadata
                    self._cache = data.get("cache", {})
                    self._cache_timestamps = data.get("timestamps", {})
                else:
                    # Old format (plain dict)
                    self._cache = data
                    self._cache_timestamps = {}

                logger.info(f"Loaded cache with {len(self._cache)} entries")
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load cache: {e}")
                self._cache = {}
                self._cache_timestamps = {}

    def _save_cache(self) -> None:
        """Save cache to JSON file with metadata."""
        if self.cache_file:
            try:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)

                # Save with timestamps for TTL support
                cache_data = {
                    "cache": self._cache,
                    "timestamps": self._cache_timestamps,
                    "metadata": {
                        "created_at": time.time(),
                        "entry_count": len(self._cache),
                    },
                }

                with open(self.cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache_data, f, indent=2, ensure_ascii=False)

                logger.info(f"Saved cache with {len(self._cache)} entries")
            except OSError as e:
                logger.error(f"Failed to save cache: {e}")

    def rebuild_cache(self) -> int:
        """
        Rebuild the entire cache efficiently with batch processing.

        Returns:
            Number of products successfully cached
        """
        self._cache = {}
        self._cache_timestamps = {}

        # Get unique file paths
        unique_paths = set(self._file_index.values())
        path_to_data_map = {}

        logger.info(f"Rebuilding cache for {len(unique_paths)} files...")

        # Batch parse files
        success_count = 0
        error_count = 0

        for file_path in unique_paths:
            try:
                data = self._parse_file(file_path)
                if data:
                    path_to_data_map[file_path] = data
                    success_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.warning(f"Error parsing {file_path}: {e}")
                error_count += 1
                continue

        # Map product IDs to parsed data
        count = 0
        current_time = time.time()

        for product_id, file_path in self._file_index.items():
            if file_path in path_to_data_map:
                self._cache[product_id] = path_to_data_map[file_path]
                self._cache_timestamps[product_id] = current_time
                count += 1

        if self.cache_file:
            self._save_cache()

        logger.info(
            f"Cache rebuilt: {success_count} successful, {error_count} errors, "
            f"{count} total entries"
        )
        return count

    def _parse_file(self, file_path: Path) -> dict[str, Any] | None:
        """
        Parse a CommerceTXT file and extract volatile fields.

        Args:
            file_path: Path to the CommerceTXT file

        Returns:
            Dictionary with extracted fields or None if parsing fails
        """
        try:
            # Import parser here to avoid circular imports
            from ...parser import parse_file

            result = parse_file(file_path)

            if result.errors:
                logger.debug(f"Parse errors in {file_path}: {result.errors}")
                return None

            directives = result.directives
            data: dict[str, Any] = {}

            # Helper function to search across sections
            def find_value(aliases: list[str]) -> Any | None:
                for section_name in ["OFFER", "INVENTORY", "PRODUCT", "IDENTITY"]:
                    section = directives.get(section_name)
                    if isinstance(section, dict):
                        for alias in aliases:
                            if alias in section:
                                return section[alias]
                return None

            # Extract mapped fields
            for field, aliases in self.FIELD_MAPPINGS.items():
                val = find_value(aliases)
                if val is not None:
                    data[field] = val

            # Extract special fields
            inventory = directives.get("INVENTORY", {})
            if isinstance(inventory, dict) and "LastUpdated" in inventory:
                data["last_updated"] = inventory["LastUpdated"]

            # Add source file path
            if data:
                data["source_file"] = str(file_path)

            return data if data else None

        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            self._metrics["parse_errors"] += 1
            return None

    def _normalize_product_id(self, product_id: str) -> str:
        """
        Normalize a product ID for lookup with caching.

        Handles various ID formats from vector stores:
        - "pixel-9-pro" -> "pixel-9-pro"
        - "pixel-9-pro:subject:0" -> "pixel-9-pro"
        - "pixel_subject_0_1234567890" -> "pixel_subject" or "pixel"
        """
        if not product_id:
            return ""

        # Check cache first
        if product_id in self._id_normalization_cache:
            return self._id_normalization_cache[product_id]

        normalized = product_id.lower().strip()
        result = normalized

        # Handle FAISS shard keys like "pixel-9-pro:subject:0"
        if ":" in normalized:
            head = normalized.split(":", 1)[0]
            if head in self._file_index or head in self._cache:
                result = head
            else:
                result = head

        # Handle vector store ID patterns (attr_type_index_timestamp)
        elif "_" in normalized:
            parts = normalized.split("_")
            # If it looks like a vector store ID (ends with digits), try reconstruction
            if len(parts) >= MIN_VECTOR_ID_PARTS:
                # Check if last two parts are digits (index_timestamp pattern)
                is_timestamp_pattern = parts[-1].isdigit() and parts[-2].isdigit()

                if is_timestamp_pattern:
                    # Try reconstructing without the timestamp/index suffix
                    # e.g., "pixel_subject_0_1234567890" -> "pixel_subject"
                    potential_id = "_".join(parts[:-2])
                    if potential_id in self._file_index or potential_id in self._cache:
                        result = potential_id
                    # Try just the first part as fallback
                    elif parts[0] in self._file_index or parts[0] in self._cache:
                        result = parts[0]
                    else:
                        # Use the reconstructed version even if not in index yet
                        result = potential_id

        # Cache the result
        self._id_normalization_cache[product_id] = result
        return result

    def _is_cache_expired(self, product_id: str) -> bool:
        """Check if cache entry has expired based on TTL."""
        if self.cache_ttl == 0:
            return False

        if product_id not in self._cache_timestamps:
            return True

        age = time.time() - self._cache_timestamps[product_id]
        return age > self.cache_ttl

    def get_live_attributes(
        self, product_ids: list[str], fields: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch specific fields for a list of Product IDs with optimized lookups.

        Args:
            product_ids: List of product identifiers
            fields: List of field names to retrieve (e.g., ["price", "availability"])

        Returns:
            Dictionary mapping product IDs to their field values
            Example: {"pixel-9-pro": {"price": 799.00, "availability": "InStock"}}
        """
        results: dict[str, dict[str, Any]] = {}
        files_to_parse: dict[str, list[str]] = {}  # file_path -> [product_ids]

        # First pass: check cache
        self._check_cache_for_products(product_ids, fields, results, files_to_parse)

        # Second pass: batch parse files
        if files_to_parse:
            self._batch_parse_files(files_to_parse, fields, results)

        return results

    def _check_cache_for_products(
        self,
        product_ids: list[str],
        fields: list[str],
        results: dict[str, dict[str, Any]],
        files_to_parse: dict[str, list[str]],
    ) -> None:
        """Check cache for products and queue files for parsing if needed."""
        for pid in product_ids:
            clean_id = self._normalize_product_id(pid)

            # Try cache first if not expired
            if clean_id in self._cache and not self._is_cache_expired(clean_id):
                item_data = self._cache[clean_id]
                results[pid] = {k: v for k, v in item_data.items() if k in fields}
                self._metrics["cache_hits"] += 1
                continue

            # Cache miss - need to read file
            self._metrics["cache_misses"] += 1

            if clean_id in self._file_index:
                file_path = str(self._file_index[clean_id])
                if file_path not in files_to_parse:
                    files_to_parse[file_path] = []
                files_to_parse[file_path].append(pid)
            else:
                results[pid] = {}

    def _batch_parse_files(
        self,
        files_to_parse: dict[str, list[str]],
        fields: list[str],
        results: dict[str, dict[str, Any]],
    ) -> None:
        """Batch parse files and update cache."""
        current_time = time.time()

        for file_path_str, pids in files_to_parse.items():
            file_p: Path = Path(file_path_str)

            try:
                parsed_data: dict[str, Any] | None = self._parse_file(file_p)
                self._metrics["file_reads"] += 1

                if parsed_data:
                    # Update cache for all product IDs pointing to this file
                    for pid in pids:
                        clean_id = self._normalize_product_id(pid)
                        self._cache[clean_id] = parsed_data
                        self._cache_timestamps[clean_id] = current_time
                        results[pid] = {
                            k: v for k, v in parsed_data.items() if k in fields
                        }
                else:
                    for pid in pids:
                        results[pid] = {}

            except Exception as e:
                logger.warning(f"Error reading {file_path_str}: {e}")
                for pid in pids:
                    results[pid] = {}

    def refresh_product(self, product_id: str) -> bool:
        """
        Refresh cache for a specific product by re-parsing its file.

        Args:
            product_id: The product ID to refresh

        Returns:
            True if refresh succeeded, False otherwise
        """
        clean_id = self._normalize_product_id(product_id)

        if clean_id in self._file_index:
            file_path = self._file_index[clean_id]
            try:
                item_data = self._parse_file(file_path)
                if item_data:
                    self._cache[clean_id] = item_data
                    self._cache_timestamps[clean_id] = time.time()
                    logger.info(f"Refreshed cache for '{product_id}'")
                    return True
            except Exception as e:
                logger.error(f"Failed to refresh '{product_id}': {e}")

        return False

    def batch_refresh(self, product_ids: list[str]) -> int:
        """
        Refresh cache for multiple products efficiently.

        Args:
            product_ids: List of product IDs to refresh

        Returns:
            Number of products successfully refreshed
        """
        success_count = 0
        current_time = time.time()

        # Group by file path to avoid duplicate parsing
        path_to_ids: dict[Path, list[str]] = {}

        for pid in product_ids:
            clean_id = self._normalize_product_id(pid)
            if clean_id in self._file_index:
                file_path = self._file_index[clean_id]
                if file_path not in path_to_ids:
                    path_to_ids[file_path] = []
                path_to_ids[file_path].append(clean_id)

        # Parse each file once
        for file_path, clean_ids in path_to_ids.items():
            try:
                item_data = self._parse_file(file_path)
                if item_data:
                    for clean_id in clean_ids:
                        self._cache[clean_id] = item_data
                        self._cache_timestamps[clean_id] = current_time
                        success_count += 1
            except Exception as e:
                logger.warning(f"Error refreshing {file_path}: {e}")

        logger.info(f"Batch refreshed {success_count}/{len(product_ids)} products")
        return success_count

    def get_cached_product_count(self) -> int:
        """Return the number of products currently in cache."""
        return len(self._cache)

    def get_indexed_file_count(self) -> int:
        """Return the number of indexed product files."""
        return len(set(self._file_index.values()))

    def get_metrics(self) -> dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Dictionary with cache hits, misses, etc.
        """
        total_requests = self._metrics["cache_hits"] + self._metrics["cache_misses"]
        hit_rate = (
            self._metrics["cache_hits"] / total_requests if total_requests > 0 else 0
        )

        return {
            **self._metrics,
            "cache_hit_rate": round(hit_rate, 3),
            "cached_products": len(self._cache),
            "indexed_files": self.get_indexed_file_count(),
        }

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._cache_timestamps.clear()
        self._id_normalization_cache.clear()
        logger.info("Cache cleared")

    def clear_normalization_cache(self) -> None:
        """Clear only the ID normalization cache."""
        self._id_normalization_cache.clear()
        logger.debug("Normalization cache cleared")

    def prune_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        if self.cache_ttl == 0:
            return 0

        current_time = time.time()
        expired: list[str] = []

        for product_id, timestamp in self._cache_timestamps.items():
            age = current_time - timestamp
            if age > self.cache_ttl:
                expired.append(product_id)

        for product_id in expired:
            self._cache.pop(product_id, None)
            self._cache_timestamps.pop(product_id, None)

        if expired:
            logger.info(f"Pruned {len(expired)} expired cache entries")

        return len(expired)
