"""
SLM response cache for storing LLM outputs.

Caches deterministic LLM responses for repeated prompts.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from .base_cache import BaseCache

# Constants
MIN_BACKEND_PARAMS = 3  # Minimum params for basic backend: key, value, ttl

logger = logging.getLogger(__name__)


class SLMResponseCache(BaseCache):
    """
    Cache for SLM/LLM responses.

    Stores prompt→response mappings with long TTL (responses are stable).
    Uses content-based hashing for cache keys.

    Features:
    - Long TTL (7 days default)
    - Prompt normalization
    - Model-aware caching
    - Hit/miss metrics

    Example:
        cache = SLMResponseCache()

        # Get or compute response
        response = await cache.get_or_compute(
            prompt="Analyze product: ...",
            compute_fn=lambda: slm.generate(prompt),
            model="gpt-4o-mini"
        )
    """

    DEFAULT_TTL = 604800  # 7 days

    def __init__(
        self,
        backend: str = "sqlite",
        ttl: int = DEFAULT_TTL,
        **backend_kwargs: Any,
    ):
        """
        Initialize SLMResponseCache.

        Args:
            backend: "sqlite" (local) or "redis" (distributed)
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
        if backend == "sqlite":
            return self._create_sqlite_backend(kwargs)
        elif backend == "redis":
            from ...drivers.async_redis_storage import AsyncRedisStorage

            return AsyncRedisStorage(
                host=kwargs.get("host", "localhost"),
                port=kwargs.get("port", 6379),
                db=kwargs.get("db", 3),  # Separate DB for SLM cache
                key_prefix=kwargs.get("key_prefix", "slm_cache"),
                **kwargs,
            )
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def _create_sqlite_backend(self, kwargs: dict):
        """Create SQLite backend for SLM cache."""
        import aiosqlite

        class SQLiteSLMCache:
            def __init__(self, db_path: str = ".rag/cache/slm.db"):
                self.db_path = Path(db_path)
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = None

            async def _get_conn(self):
                if self._conn is None:
                    self._conn = await aiosqlite.connect(str(self.db_path))
                    await self._conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS slm_cache (
                            key TEXT PRIMARY KEY,
                            prompt TEXT NOT NULL,
                            response TEXT NOT NULL,
                            model TEXT NOT NULL,
                            expires_at INTEGER NOT NULL
                        )
                        """
                    )
                    await self._conn.execute(
                        """CREATE INDEX IF NOT EXISTS idx_slm_expires
                        ON slm_cache(expires_at)"""
                    )
                    await self._conn.execute(
                        """CREATE INDEX IF NOT EXISTS idx_slm_model
                        ON slm_cache(model)"""
                    )
                    await self._conn.commit()
                return self._conn

            async def get(self, key: str):
                import time

                conn = await self._get_conn()
                async with conn.execute(
                    "SELECT response, expires_at FROM slm_cache WHERE key = ?", (key,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        response, expires_at = row
                        if expires_at > time.time():
                            return response
                        else:
                            await conn.execute(
                                "DELETE FROM slm_cache WHERE key = ?", (key,)
                            )
                            await conn.commit()
                return None

            async def set(
                self, key: str, value: Any, ttl: int, prompt: str = "", model: str = ""
            ):
                import time

                conn = await self._get_conn()
                expires_at = int(time.time() + ttl)

                await conn.execute(
                    """
                    INSERT OR REPLACE INTO slm_cache
                    (key, prompt, response, model, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key, prompt, value, model, expires_at),
                )
                await conn.commit()

            async def delete(self, key: str):
                conn = await self._get_conn()
                await conn.execute("DELETE FROM slm_cache WHERE key = ?", (key,))
                await conn.commit()

            async def clear(self):
                conn = await self._get_conn()
                await conn.execute("DELETE FROM slm_cache")
                await conn.commit()

        return SQLiteSLMCache(kwargs.get("db_path", ".rag/cache/slm.db"))

    async def get_or_compute_response(
        self,
        prompt: str,
        model: str,
        compute_fn: Any,
        ttl: int | None = None,
    ) -> str:
        """
        Get SLM response from cache or compute it.

        This is a convenience method that automatically generates
        the cache key from prompt and model.

        Args:
            prompt: Input prompt
            model: Model identifier
            compute_fn: Callable to compute response if not cached
            ttl: Time-to-live (optional)

        Returns:
            Cached or computed response
        """
        key = self._compute_key(prompt, model)
        result = await super().get_or_compute(key, compute_fn, ttl=ttl)

        return str(result)

    def _compute_key(self, prompt: str, model: str) -> str:
        """
        Compute cache key from prompt and model.

        Args:
            prompt: Input prompt
            model: Model identifier

        Returns:
            Cache key (hex string)
        """
        # Normalize prompt (strip whitespace)
        normalized = prompt.strip()

        # Hash prompt + model
        content = f"{model}:{normalized}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def get(self, key: str) -> Any | None:
        """Get SLM response from cache."""
        try:
            value = await self._backend.get(key)
            if value is not None:
                self._hits += 1
                logger.debug(f"SLM cache hit for key: {key[:16]}...")
            else:
                self._misses += 1
            return value
        except Exception as e:
            logger.warning(f"SLM cache get failed: {e}")
            self._misses += 1
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Store SLM response in cache."""
        try:
            ttl = ttl or self.default_ttl

            if hasattr(self._backend, "set") and callable(self._backend.set):
                # Check if backend supports extra args
                import inspect

                sig = inspect.signature(self._backend.set)
                # Check for extended backend signature (key, value, ttl, prompt, model)
                if len(sig.parameters) > MIN_BACKEND_PARAMS:
                    await self._backend.set(key, value, ttl, prompt="", model="")
                else:
                    await self._backend.set(key, value, ttl)
            else:
                await self._backend.set(key, value, ttl)

            logger.debug(f"Cached SLM response: {key[:16]}...")
            return True
        except Exception as e:
            logger.warning(f"SLM cache set failed: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete SLM response from cache."""
        try:
            await self._backend.delete(key)
            return True
        except Exception as e:
            logger.warning(f"SLM cache delete failed: {e}")
            return False

    async def clear(self) -> bool:
        """Clear all SLM responses from cache."""
        try:
            await self._backend.clear()
            logger.info("Cleared SLM cache")
            return True
        except Exception as e:
            logger.error(f"SLM cache clear failed: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if SLM response exists in cache."""
        value = await self.get(key)
        return value is not None

    async def cache_response(
        self,
        prompt: str,
        model: str,
        response: str,
        ttl: int | None = None,
    ) -> bool:
        """
        Cache SLM response with prompt-based key.

        Args:
            prompt: Input prompt
            model: Model identifier
            response: Generated response
            ttl: Time-to-live (optional)

        Returns:
            True if cached
        """
        key = self._compute_key(prompt, model)
        return await self.set(key, response, ttl=ttl)

    async def get_cached_response(self, prompt: str, model: str) -> str | None:
        """
        Retrieve cached SLM response by prompt.

        Args:
            prompt: Input prompt
            model: Model identifier

        Returns:
            Cached response or None
        """
        key = self._compute_key(prompt, model)
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

    async def close(self):
        """Close the underlying storage backend."""
        if hasattr(self, "storage") and hasattr(self.storage, "close"):
            await self.storage.close()
        elif hasattr(self, "db") and hasattr(self.db, "close"):
            await self.db.close()
