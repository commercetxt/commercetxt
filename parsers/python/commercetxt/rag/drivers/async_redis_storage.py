"""
Async Redis storage driver for realtime data lookup.

Provides high-performance async operations with connection pooling.
Uses redis.asyncio for native async support.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any

from ..interfaces.async_storage import AsyncBaseStorage

logger = logging.getLogger(__name__)


class AsyncRedisStorage(AsyncBaseStorage):
    """
    Async Redis-backed realtime storage for fast price/stock lookups.

    Features:
    - Native async operations (no thread blocking)
    - Connection pooling
    - Pipeline batching for bulk operations
    - Automatic TTL management
    - JSON serialization for complex values

    Key structure: commercetxt:{product_id}:{field}
    Example: commercetxt:pixel-9-pro:price -> "999.00"

    Example:
        storage = AsyncRedisStorage(host="localhost", port=6379)

        # Set data
        await storage.set_live_attributes("pixel-9-pro", {
            "price": 999.00,
            "availability": "InStock",
            "currency": "USD"
        })

        # Get data (batch)
        data = await storage.get_live_attributes(
            ["pixel-9-pro", "pixel-8a"],
            ["price", "availability"]
        )
    """

    DEFAULT_TTL = 3600  # 1 hour
    KEY_PREFIX = "commercetxt"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        key_prefix: str | None = None,
        default_ttl: int | None = None,
        max_connections: int = 50,
        **kwargs: Any,
    ):
        """
        Initialize AsyncRedisStorage.

        Args:
            host: Redis server host
            port: Redis server port
            db: Redis database number
            password: Redis password (optional)
            key_prefix: Prefix for all keys (default: "commercetxt")
            default_ttl: Default TTL in seconds (default: 3600)
            max_connections: Max connections in pool
            **kwargs: Additional redis connection options
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.key_prefix = key_prefix or self.KEY_PREFIX
        self.default_ttl = default_ttl or self.DEFAULT_TTL
        self.max_connections = max_connections
        self._extra_kwargs = kwargs
        self._redis = None
        self._pool = None

    async def _get_redis(self):
        """Get or create Redis connection with pooling."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                # Create connection pool
                self._pool = aioredis.ConnectionPool(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    max_connections=self.max_connections,
                    decode_responses=True,
                    **self._extra_kwargs,
                )

                self._redis = aioredis.Redis(connection_pool=self._pool)

                # Test connection
                await self._redis.ping()
                logger.info(f"Connected to Redis at {self.host}:{self.port}")

            except ImportError:
                raise ImportError(
                    "Missing dependency. Run: pip install redis[asyncio]"
                ) from None
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

        return self._redis

    def _make_key(self, product_id: str, field: str | None = None) -> str:
        """Generate Redis key for product/field."""
        if field:
            return f"{self.key_prefix}:{product_id}:{field}"
        return f"{self.key_prefix}:{product_id}"

    async def get_live_attributes(
        self, product_ids: list[str], fields: Sequence[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch specific fields for a list of product IDs asynchronously.

        Uses Redis pipelining for efficient batch retrieval.

        Args:
            product_ids: List of product identifiers
            fields: List of field names to retrieve

        Returns:
            Dictionary mapping product_id -> {field: value}
        """
        if not product_ids or not fields:
            return {}

        redis = await self._get_redis()
        results: dict[str, dict[str, Any]] = {}

        # Use pipeline for batch operations
        async with redis.pipeline(transaction=False) as pipe:
            # Queue all GET commands
            key_map: list[tuple[str, str, str]] = []  # (product_id, field, key)
            for pid in product_ids:
                for field in fields:
                    key = self._make_key(pid, field)
                    pipe.get(key)
                    key_map.append((pid, field, key))

            # Execute pipeline
            responses = await pipe.execute()

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

    async def set_live_attributes(
        self, product_id: str, attributes: dict[str, Any]
    ) -> bool:
        """
        Update product attributes asynchronously.

        Args:
            product_id: Product identifier
            attributes: Dictionary of attributes to update

        Returns:
            True if successful
        """
        if not attributes:
            return True

        redis = await self._get_redis()

        try:
            # Use pipeline for batch SET operations
            async with redis.pipeline(transaction=False) as pipe:
                for field, value in attributes.items():
                    key = self._make_key(product_id, field)

                    # Serialize complex values to JSON
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)
                    else:
                        value = str(value)

                    # Set with TTL
                    pipe.setex(key, self.default_ttl, value)

                await pipe.execute()

            return True

        except Exception as e:
            logger.error(f"Failed to set attributes for {product_id}: {e}")
            return False

    async def delete_product(self, product_id: str) -> bool:
        """
        Delete all attributes for a product.

        Args:
            product_id: Product identifier

        Returns:
            True if successful
        """
        redis = await self._get_redis()

        try:
            # Find all keys for this product
            pattern = self._make_key(product_id, "*")
            keys = []

            async for key in redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await redis.delete(*keys)

            return True

        except Exception as e:
            logger.error(f"Failed to delete product {product_id}: {e}")
            return False

    async def health_check(self) -> dict[str, Any]:
        """
        Check Redis health asynchronously.

        Returns:
            Health status dictionary
        """
        try:
            redis = await self._get_redis()

            # Ping check
            ping_result = await redis.ping()

            # Get info
            info = await redis.info()

            return {
                "status": "healthy" if ping_result else "unhealthy",
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def close(self) -> None:
        """Close Redis connection and cleanup."""
        if self._redis:
            await self._redis.close()
            self._redis = None

        if self._pool:
            await self._pool.disconnect()
            self._pool = None

    async def __aenter__(self):
        """Context manager entry."""
        await self._get_redis()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup."""
        await self.close()
