"""
Base cache interface.

Defines the contract for all cache implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class BaseCache(ABC):
    """
    Abstract base for cache implementations.

    Provides get/set interface with TTL support.
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """
        Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to store
            ttl: Time-to-live in seconds (None = default TTL)

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """
        Clear all cache entries.

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        pass

    async def get_or_compute(
        self, key: str, compute_fn: Callable[[], Any], ttl: int | None = None
    ) -> Any:
        """
        Get value from cache or compute if missing.

        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached
            ttl: Time-to-live for computed value

        Returns:
            Cached or computed value
        """
        # Try cache first
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        value = await compute_fn() if callable(compute_fn) else compute_fn

        # Store in cache
        await self.set(key, value, ttl=ttl)

        return value


class NoOpCache(BaseCache):
    """
    No-operation cache for when dependencies are missing.

    Always returns cache miss but doesn't fail.
    Useful for graceful degradation when optional cache dependencies
    (like redis, aiosqlite) are not installed.
    """

    async def get(self, key: str) -> None:
        """Always return None (cache miss)."""
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Pretend to cache (but actually do nothing)."""
        return True

    async def delete(self, key: str) -> bool:
        """Pretend to delete."""
        return True

    async def clear(self) -> bool:
        """Pretend to clear."""
        return True

    async def exists(self, key: str) -> bool:
        """Always return False (nothing cached)."""
        return False
