"""
Search result cache for storing query→results mappings.

Reduces redundant vector searches and speeds up repeated queries.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from .base_cache import BaseCache

logger = logging.getLogger(__name__)


class SearchResultCache(BaseCache):
    """
    Cache for search results.

    Stores query→results mappings with TTL support.
    Includes semantic deduplication (similar queries can share cache).

    Features:
    - Query normalization (lowercase, strip)
    - Parameter-aware caching (top_k, namespace)
    - TTL management (default 1 hour)
    - Hit/miss metrics

    Example:
        cache = SearchResultCache(backend="redis")

        # Check cache
        results = await cache.get_cached_search(
            query="wireless headphones",
            top_k=10,
            namespace="products"
        )

        if not results:
            # Cache miss - do search
            results = await vector_store.search(...)
            await cache.cache_search(query, top_k, namespace, results)
    """

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(
        self,
        backend: str = "redis",
        ttl: int = DEFAULT_TTL,
        **backend_kwargs: Any,
    ):
        """
        Initialize SearchResultCache.

        Args:
            backend: "redis" or "sqlite"
            ttl: Default time-to-live in seconds
            **backend_kwargs: Backend-specific options
        """
        self.backend_type = backend
        self.default_ttl = ttl
        self._backend = self._create_backend(backend, backend_kwargs)
        self._hits = 0
        self._misses = 0

    def _create_backend(self, backend: str, kwargs: dict):
        """Create appropriate backend instance."""
        if backend == "redis":
            from ...drivers.async_redis_storage import AsyncRedisStorage

            return AsyncRedisStorage(
                host=kwargs.get("host", "localhost"),
                port=kwargs.get("port", 6379),
                db=kwargs.get("db", 2),  # Separate DB for search cache
                key_prefix=kwargs.get("key_prefix", "search_cache"),
                **kwargs,
            )
        elif backend == "sqlite":
            return self._create_sqlite_backend(kwargs)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def _create_sqlite_backend(self, kwargs: dict):
        """Create SQLite backend for search cache."""
        from pathlib import Path

        import aiosqlite

        class SQLiteSearchCache:
            def __init__(self, db_path: str = ".rag/cache/search.db"):
                self.db_path = Path(db_path)
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = None

            async def _get_conn(self):
                if self._conn is None:
                    self._conn = await aiosqlite.connect(str(self.db_path))
                    await self._conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS search_cache (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            expires_at INTEGER NOT NULL
                        )
                        """
                    )
                    await self._conn.execute(
                        """CREATE INDEX IF NOT EXISTS idx_search_expires
                        ON search_cache(expires_at)"""
                    )
                    await self._conn.commit()
                return self._conn

            async def get(self, key: str):
                import time

                conn = await self._get_conn()
                async with conn.execute(
                    "SELECT value, expires_at FROM search_cache WHERE key = ?", (key,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        value_json, expires_at = row
                        if expires_at > time.time():
                            return json.loads(value_json)
                        else:
                            await conn.execute(
                                "DELETE FROM search_cache WHERE key = ?", (key,)
                            )
                            await conn.commit()
                return None

            async def set(self, key: str, value: Any, ttl: int):
                import time

                conn = await self._get_conn()
                value_json = json.dumps(value)
                expires_at = int(time.time() + ttl)

                await conn.execute(
                    """
                    INSERT OR REPLACE INTO search_cache (key, value, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, value_json, expires_at),
                )
                await conn.commit()

            async def delete(self, key: str):
                conn = await self._get_conn()
                await conn.execute("DELETE FROM search_cache WHERE key = ?", (key,))
                await conn.commit()

            async def clear(self):
                conn = await self._get_conn()
                await conn.execute("DELETE FROM search_cache")
                await conn.commit()

        return SQLiteSearchCache(kwargs.get("db_path", ".rag/cache/search.db"))

    def _compute_key(self, query: str, top_k: int, namespace: str) -> str:
        """
        Compute cache key from query parameters.

        Normalizes query (lowercase, strip) for better cache hits.

        Args:
            query: Search query
            top_k: Number of results
            namespace: Search namespace

        Returns:
            Cache key (hex string)
        """
        # Normalize query
        normalized = query.strip().lower()

        # Hash query + parameters
        content = f"{normalized}:{top_k}:{namespace}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def get(self, key: str) -> Any | None:
        """Get search results from cache."""
        try:
            value = await self._backend.get(key)
            if value is not None:
                self._hits += 1
                logger.debug(f"Search cache hit for key: {key[:16]}...")
            else:
                self._misses += 1
            return value
        except Exception as e:
            logger.warning(f"Search cache get failed: {e}")
            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Store search results in cache."""
        try:
            ttl = ttl or self.default_ttl
            await self._backend.set(key, value, ttl)
            logger.debug(f"Cached search results: {key[:16]}...")
            return True
        except Exception as e:
            logger.warning(f"Search cache set failed: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete search results from cache."""
        try:
            await self._backend.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Search cache delete failed: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all search results from cache."""
        try:
            await self._backend.clear()
            logger.info("Cleared search cache")
            return True
        except Exception as e:
            logger.error(f"Search cache clear failed: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if search results exist in cache."""
        value = await self.get(key)
        return value is not None

    async def cache_search(
        self,
        query: str,
        top_k: int,
        namespace: str,
        results: list[dict[str, Any]],
        ttl: int | None = None,
    ) -> bool:
        """
        Cache search results with query-based key.

        Args:
            query: Original query
            top_k: Number of results
            namespace: Search namespace
            results: Search results to cache
            ttl: Time-to-live (optional)

        Returns:
            True if cached
        """
        key = self._compute_key(query, top_k, namespace)
        return await self.set(key, results, ttl=ttl)

    async def get_cached_search(
        self, query: str, top_k: int, namespace: str
    ) -> list[dict[str, Any]] | None:
        """
        Retrieve cached search results by query.

        Args:
            query: Original query
            top_k: Number of results
            namespace: Search namespace

        Returns:
            Cached results or None
        """
        key = self._compute_key(query, top_k, namespace)
        return await self.get(key)

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hits, misses, and hit ratio
        """
        total = self._hits + self._misses
        hit_ratio = self._hits / total if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_requests": total,
            "hit_ratio": hit_ratio,
            "backend": self.backend_type,
        }
