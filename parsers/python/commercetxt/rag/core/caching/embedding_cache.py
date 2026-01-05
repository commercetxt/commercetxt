"""
Embedding cache for storing text→vector mappings.

Reduces API calls and speeds up repeated embeddings.
"""

from __future__ import annotations

import hashlib
import logging
import pickle
from pathlib import Path
from typing import Any

from .base_cache import BaseCache, NoOpCache

logger = logging.getLogger(__name__)


class EmbeddingCache(BaseCache):
    """
    Cache for text embeddings.

    Stores text→vector mappings with TTL support.
    Supports both Redis (distributed) and SQLite (local) backends.

    Features:
    - Content-based hashing (same text = same cache key)
    - Efficient vector serialization (pickle)
    - TTL management
    - Hit/miss metrics
    - Graceful fallback if dependencies missing

    Example:
        cache = EmbeddingCache(backend="redis", host="localhost")

        # Get or compute embedding
        vector = await cache.get_or_compute(
            "wireless headphones",
            lambda: embedder.embed_text("wireless headphones"),
            ttl=86400
        )
    """

    DEFAULT_TTL = 86400  # 24 hours

    def __init__(
        self,
        backend: str = "sqlite",
        ttl: int = DEFAULT_TTL,
        **backend_kwargs: Any,
    ):
        """
        Initialize EmbeddingCache.

        Args:
            backend: "redis" or "sqlite"
            ttl: Default time-to-live in seconds
            **backend_kwargs: Backend-specific options
        """
        self.backend_type = backend
        self.default_ttl = ttl

        try:
            self._backend = self._create_backend(backend, backend_kwargs)
        except ImportError as e:
            logger.warning(
                f"Cache backend '{backend}' unavailable: {e}. "
                f"Caching disabled - install required dependencies to enable."
            )
            # Fallback to no-op cache (graceful degradation)
            self._backend = NoOpCache()
            self.backend_type = "disabled"

        self._hits = 0
        self._misses = 0

    def _create_backend(self, backend: str, kwargs: dict):
        """Create appropriate backend instance."""
        if backend == "redis":
            return self._create_redis_backend(kwargs)
        elif backend == "sqlite":
            return self._create_sqlite_backend(kwargs)
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def _create_redis_backend(self, kwargs: dict):
        """Create Redis backend."""
        try:
            from ...drivers.async_redis_storage import AsyncRedisStorage
        except ImportError:
            raise ImportError(
                "Redis backend requires: pip install redis[asyncio]\n"
                "Or use backend='sqlite' for local caching."
            ) from None

        return AsyncRedisStorage(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 6379),
            db=kwargs.get("db", 1),  # Use separate DB for cache
            key_prefix=kwargs.get("key_prefix", "embed_cache"),
            **kwargs,
        )

    def _create_sqlite_backend(self, kwargs: dict):
        """Create SQLite backend."""
        try:
            import aiosqlite
        except ImportError:
            raise ImportError(
                "SQLite backend requires: pip install aiosqlite\n"
                "This is needed for local caching."
            ) from None

        class SQLiteBackend:
            def __init__(self, db_path: str = ".rag/cache/embeddings.db"):
                self.db_path = Path(db_path)
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = None

            async def _get_conn(self):
                if self._conn is None:
                    self._conn = await aiosqlite.connect(str(self.db_path))
                    await self._conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS embeddings (
                            key TEXT PRIMARY KEY,
                            value BLOB NOT NULL,
                            expires_at INTEGER NOT NULL
                        )
                        """
                    )
                    await self._conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_expires ON "
                        "embeddings(expires_at)"
                    )
                    await self._conn.commit()
                return self._conn

            async def get(self, key: str):
                import time

                conn = await self._get_conn()
                async with conn.execute(
                    "SELECT value, expires_at FROM embeddings WHERE key = ?", (key,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        value_blob, expires_at = row
                        if expires_at > time.time():
                            # S301: Safe - only deserializing internally cached data
                            return pickle.loads(value_blob)  # noqa: S301
                        else:
                            # Expired - delete
                            await conn.execute(
                                "DELETE FROM embeddings WHERE key = ?", (key,)
                            )
                            await conn.commit()
                return None

            async def set(self, key: str, value: Any, ttl: int):
                import time

                conn = await self._get_conn()
                value_blob = pickle.dumps(value)
                expires_at = int(time.time() + ttl)

                await conn.execute(
                    """
                    INSERT OR REPLACE INTO embeddings (key, value, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, value_blob, expires_at),
                )
                await conn.commit()

            async def delete(self, key: str):
                conn = await self._get_conn()
                await conn.execute("DELETE FROM embeddings WHERE key = ?", (key,))
                await conn.commit()

            async def clear(self):
                conn = await self._get_conn()
                await conn.execute("DELETE FROM embeddings")
                await conn.commit()

        return SQLiteBackend(kwargs.get("db_path", ".rag/cache/embeddings.db"))

    def _compute_key(self, text: str, model: str = "default") -> str:
        """
        Compute cache key from text content.

        Uses SHA256 hash of normalized text + model name.

        Args:
            text: Input text
            model: Model identifier

        Returns:
            Cache key (hex string)
        """
        # Normalize text
        normalized = text.strip().lower()

        # Hash text + model
        content = f"{model}:{normalized}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def get(self, key: str) -> Any | None:
        """Get embedding from cache."""
        try:
            value = await self._backend.get(key)
            if value is not None:
                self._hits += 1
                logger.debug(f"Cache hit for key: {key[:16]}...")
            else:
                self._misses += 1
            return value
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Store embedding in cache."""
        try:
            ttl = ttl or self.default_ttl
            await self._backend.set(key, value, ttl)
            logger.debug(f"Cached embedding: {key[:16]}...")
            return True
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete embedding from cache."""
        try:
            await self._backend.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all embeddings from cache."""
        try:
            await self._backend.clear()
            logger.info("Cleared embedding cache")
            return True
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if embedding exists in cache."""
        value = await self.get(key)
        return value is not None

    async def cache_text(
        self,
        text: str,
        vector: list[float],
        model: str = "default",
        ttl: int | None = None,
    ) -> bool:
        """
        Cache an embedding with text-based key.

        Args:
            text: Original text
            vector: Embedding vector
            model: Model identifier
            ttl: Time-to-live (optional)

        Returns:
            True if cached
        """
        key = self._compute_key(text, model)
        return await self.set(key, vector, ttl=ttl)

    async def get_cached_text(
        self, text: str, model: str = "default"
    ) -> list[float] | None:
        """
        Retrieve cached embedding by text.

        Args:
            text: Original text
            model: Model identifier

        Returns:
            Cached vector or None
        """
        key = self._compute_key(text, model)
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
