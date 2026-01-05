"""
Redis storage driver for realtime data lookup.

Provides high-performance hot-lookup for volatile data (price, stock, availability).
Designed for production workloads with sub-millisecond latency.
"""

from __future__ import annotations

import json
from typing import Any

from ..interfaces.base_storage import BaseRealtimeStorage


class RedisStorage(BaseRealtimeStorage):
    """
    Redis-backed realtime storage for fast price/stock lookups.

    Features:
    - Sub-millisecond latency for hot data
    - Automatic key expiration (TTL)
    - Batch operations with pipelining
    - JSON serialization for complex values

    Key structure: commercetxt:{product_id}:{field}
    Example: commercetxt:pixel-9-pro:price -> "999.00"

    Example usage:
        storage = RedisStorage(host="localhost", port=6379)

        # Set product data
        storage.set_product_data("pixel-9-pro", {
            "price": 999.00,
            "availability": "InStock",
            "currency": "USD"
        })

        # Get live attributes (implements BaseRealtimeStorage)
        data = storage.get_live_attributes(["pixel-9-pro"], ["price", "availability"])
    """

    DEFAULT_TTL = 3600  # 1 hour default TTL
    KEY_PREFIX = "commercetxt"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        key_prefix: str | None = None,
        default_ttl: int | None = None,
        decode_responses: bool = True,
        **kwargs: Any,
    ):
        """
        Initialize RedisStorage.

        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (optional)
            key_prefix: Prefix for all keys (default: "commercetxt")
            default_ttl: Default TTL in seconds (default: 3600)
            decode_responses: Decode Redis responses to strings
            **kwargs: Additional redis-py connection options
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.key_prefix = key_prefix or self.KEY_PREFIX
        self.default_ttl = default_ttl or self.DEFAULT_TTL
        self.decode_responses = decode_responses
        self._extra_kwargs = kwargs
        self._client = None

    def _get_client(self):
        """Get or create Redis client (lazy initialization)."""
        if self._client is None:
            try:
                import redis

                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    decode_responses=self.decode_responses,
                    **self._extra_kwargs,
                )
                # Test connection
                self._client.ping()
            except ImportError:
                raise ImportError(
                    "Missing dependency. Run: pip install redis"
                ) from None
        return self._client

    def _make_key(self, product_id: str, field: str | None = None) -> str:
        """Generate Redis key for product/field."""
        if field:
            return f"{self.key_prefix}:{product_id}:{field}"
        return f"{self.key_prefix}:{product_id}"

    def get_live_attributes(
        self, product_ids: list[str], fields: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch specific fields for a list of Product IDs.

        Uses Redis pipelining for efficient batch retrieval.

        Args:
            product_ids: List of product identifiers
            fields: List of field names to retrieve

        Returns:
            Dictionary mapping product IDs to their field values
        """
        if not product_ids or not fields:
            return {}

        client = self._get_client()
        results: dict[str, dict[str, Any]] = {}

        # Use pipeline for batch operations
        pipe = client.pipeline()

        # Queue all GET commands
        key_map: list[tuple[str, str, str]] = []  # (product_id, field, key)
        for pid in product_ids:
            for field in fields:
                key = self._make_key(pid, field)
                pipe.get(key)
                key_map.append((pid, field, key))

        # Execute pipeline
        responses = pipe.execute()

        # Process responses
        for (pid, field, _), value in zip(key_map, responses, strict=False):
            if pid not in results:
                results[pid] = {}

            if value is not None:
                # Try to parse JSON for complex values
                try:
                    results[pid][field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    results[pid][field] = value

        return results

    def set_product_data(
        self,
        product_id: str,
        data: dict[str, Any],
        ttl: int | None = None,
    ) -> bool:
        """
        Set multiple fields for a product.

        Args:
            product_id: Product identifier
            data: Dictionary of field -> value
            ttl: Time-to-live in seconds (uses default if None)

        Returns:
            True if all fields were set successfully
        """
        if not data:
            return False

        client = self._get_client()
        ttl = ttl if ttl is not None else self.default_ttl

        pipe = client.pipeline()

        for field, value in data.items():
            key = self._make_key(product_id, field)

            # Serialize complex values to JSON
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            else:
                value = str(value)

            pipe.setex(key, ttl, value)

        results = pipe.execute()
        return all(results)

    def set_field(
        self,
        product_id: str,
        field: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a single field for a product.

        Args:
            product_id: Product identifier
            field: Field name
            value: Field value
            ttl: Time-to-live in seconds

        Returns:
            True if field was set successfully
        """
        client = self._get_client()
        key = self._make_key(product_id, field)
        ttl = ttl if ttl is not None else self.default_ttl

        # Serialize complex values
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        else:
            value = str(value)

        return bool(client.setex(key, ttl, value))

    def delete_product(self, product_id: str, fields: list[str] | None = None) -> int:
        """
        Delete product data from Redis.

        Args:
            product_id: Product identifier
            fields: Specific fields to delete (deletes all if None)

        Returns:
            Number of keys deleted
        """
        client = self._get_client()

        if fields:
            keys = [self._make_key(product_id, f) for f in fields]
        else:
            # Find all keys for this product using SCAN
            pattern = self._make_key(product_id, "*")
            keys = list(client.scan_iter(match=pattern))

        if keys:
            deleted_count = client.delete(*keys)
            return int(deleted_count) if deleted_count is not None else 0
        return 0

    def bulk_import(
        self,
        products: dict[str, dict[str, Any]],
        ttl: int | None = None,
    ) -> int:
        """
        Bulk import product data.

        Args:
            products: Dictionary of product_id -> {field: value}
            ttl: Time-to-live in seconds

        Returns:
            Number of products imported
        """
        client = self._get_client()
        ttl = ttl if ttl is not None else self.default_ttl

        pipe = client.pipeline()
        count = 0

        for product_id, data in products.items():
            for field, value in data.items():
                key = self._make_key(product_id, field)

                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                else:
                    value = str(value)

                pipe.setex(key, ttl, value)

            count += 1

            # Execute in batches to avoid memory issues
            if count % 1000 == 0:
                pipe.execute()
                pipe = client.pipeline()

        # Execute remaining commands
        pipe.execute()
        return count

    def health_check(self) -> dict[str, Any]:
        """
        Check Redis connection health.

        Returns:
            Health status dictionary
        """
        try:
            client = self._get_client()
            info = client.info("server")
            return {
                "status": "healthy",
                "redis_version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
