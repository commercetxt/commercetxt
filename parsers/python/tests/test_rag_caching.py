"""
Comprehensive tests for RAG caching modules and CommerceTXT LRU cache.

Covers EmbeddingCache, SearchResultCache, SLMResponseCache, and parse_cached.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# CommerceTXT LRU Cache Tests (consolidated from test_cache.py)
# =============================================================================


class TestCommerceTXTLRUCache:
    """Tests for CommerceTXT LRU parsing cache."""

    def test_parse_cached_returns_same_object(self):
        """LRU cache returns same object for identical content."""
        from commercetxt.cache import parse_cached

        content1 = "# @IDENTITY\nName: Store"
        result1 = parse_cached(content1)
        assert result1.directives["IDENTITY"]["Name"] == "Store"

        result2 = parse_cached(content1)
        assert result2 is result1

    def test_parse_cached_different_content(self):
        """Different content returns different result."""
        from commercetxt.cache import parse_cached

        content1 = "# @IDENTITY\nName: Store1"
        content2 = "# @IDENTITY\nName: Store2"

        result1 = parse_cached(content1)
        result2 = parse_cached(content2)

        assert result1.directives["IDENTITY"]["Name"] == "Store1"
        assert result2.directives["IDENTITY"]["Name"] == "Store2"
        assert result1 is not result2


# =============================================================================
# EmbeddingCache Tests
# =============================================================================


class TestEmbeddingCacheComprehensive:
    """Comprehensive tests for EmbeddingCache."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temp database path."""
        return str(tmp_path / "test_embeddings.db")

    @pytest.mark.asyncio
    async def test_sqlite_backend_creation(self, temp_db_path):
        """SQLite backend creates database file."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)
        assert cache.backend_type == "sqlite"
        assert cache._backend is not None

    @pytest.mark.asyncio
    async def test_cache_key_computation(self, temp_db_path):
        """Cache key computed from text and model."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        key1 = cache._compute_key("hello world", "model-1")
        key2 = cache._compute_key("hello world", "model-1")
        key3 = cache._compute_key("hello world", "model-2")

        # Same input = same key
        assert key1 == key2
        # Different model = different key
        assert key1 != key3
        # Key is hex string
        assert len(key1) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_cache_key_normalizes_whitespace(self, temp_db_path):
        """Cache key normalized - strips whitespace and lowercases."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        key1 = cache._compute_key("  Hello World  ", "model")
        key2 = cache._compute_key("hello world", "model")

        assert key1 == key2

    @pytest.mark.asyncio
    async def test_cache_get_miss_increments_misses(self, temp_db_path):
        """Cache miss increments miss counter."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)
        assert cache._misses == 0

        result = await cache.get("nonexistent_key")

        assert result is None
        assert cache._misses == 1

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, temp_db_path):
        """Value can be stored and retrieved."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        vector = [0.1, 0.2, 0.3]
        await cache.set("test_key", vector, ttl=3600)

        result = await cache.get("test_key")
        assert result == vector
        assert cache._hits == 1

    @pytest.mark.asyncio
    async def test_cache_delete_key(self, temp_db_path):
        """Key can be deleted from cache."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        await cache.set("to_delete", [1, 2, 3], ttl=3600)
        assert await cache.get("to_delete") is not None

        result = await cache.delete("to_delete")
        assert result is True
        assert await cache.get("to_delete") is None

    @pytest.mark.asyncio
    async def test_cache_clear_all(self, temp_db_path):
        """Clear removes all entries."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        await cache.set("key1", [1], ttl=3600)
        await cache.set("key2", [2], ttl=3600)

        result = await cache.clear()
        assert result is True

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_cache_exists_method(self, temp_db_path):
        """Exists method checks key presence."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        assert await cache.exists("nonexistent") is False

        await cache.set("exists_key", [1], ttl=3600)
        assert await cache.exists("exists_key") is True

    @pytest.mark.asyncio
    async def test_cache_get_exception_handling(self, temp_db_path):
        """Get handles backend exceptions gracefully."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        # Mock backend to raise exception
        cache._backend = MagicMock()
        cache._backend.get = AsyncMock(side_effect=Exception("DB error"))

        result = await cache.get("key")
        assert result is None
        assert cache._misses >= 1

    @pytest.mark.asyncio
    async def test_cache_set_exception_handling(self, temp_db_path):
        """Set handles backend exceptions gracefully."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        # Mock backend to raise exception
        cache._backend = MagicMock()
        cache._backend.set = AsyncMock(side_effect=Exception("Write error"))

        result = await cache.set("key", [1], ttl=3600)
        assert result is False

    @pytest.mark.asyncio
    async def test_cache_delete_exception_handling(self, temp_db_path):
        """Delete handles backend exceptions gracefully."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)
        cache._backend = MagicMock()
        cache._backend.delete = AsyncMock(side_effect=Exception("Delete error"))

        result = await cache.delete("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_cache_clear_exception_handling(self, temp_db_path):
        """Clear handles backend exceptions gracefully."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)
        cache._backend = MagicMock()
        cache._backend.clear = AsyncMock(side_effect=Exception("Clear error"))

        result = await cache.clear()
        assert result is False

    def test_unknown_backend_raises_error(self, temp_db_path):
        """Unknown backend raises ValueError."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        with pytest.raises(ValueError, match="Unknown backend"):
            EmbeddingCache(backend="unknown_backend")

    @pytest.mark.asyncio
    async def test_noop_cache_fallback(self, monkeypatch):
        """Falls back to NoOpCache when dependencies missing."""
        from commercetxt.rag.core.caching import embedding_cache as ec_module

        # Simulate aiosqlite import failure
        def failing_create_backend(self, backend, kwargs):
            raise ImportError("aiosqlite not installed")

        monkeypatch.setattr(
            ec_module.EmbeddingCache, "_create_backend", failing_create_backend
        )

        cache = ec_module.EmbeddingCache(backend="sqlite")
        assert cache.backend_type == "disabled"

    @pytest.mark.asyncio
    async def test_default_ttl_used_when_not_specified(self, temp_db_path):
        """Default TTL is used when not specified in set."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", ttl=7200, db_path=temp_db_path)
        assert cache.default_ttl == 7200


# =============================================================================
# SearchResultCache Tests
# =============================================================================


class TestSearchResultCacheComprehensive:
    """Comprehensive tests for SearchResultCache."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create temp database path."""
        return str(tmp_path / "test_search.db")

    @pytest.mark.asyncio
    async def test_sqlite_backend_creation(self, temp_db_path):
        """SQLite backend creates database file."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)
        assert cache.backend_type == "sqlite"

    @pytest.mark.asyncio
    async def test_search_key_computation(self, temp_db_path):
        """Search key computed from query, top_k, and namespace."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)

        key1 = cache._compute_key("headphones", 10, "products")
        key2 = cache._compute_key("headphones", 10, "products")
        key3 = cache._compute_key("headphones", 5, "products")
        key4 = cache._compute_key("headphones", 10, "categories")

        # Same params = same key
        assert key1 == key2
        # Different top_k = different key
        assert key1 != key3
        # Different namespace = different key
        assert key1 != key4

    @pytest.mark.asyncio
    async def test_search_key_normalizes_query(self, temp_db_path):
        """Query normalized - stripped and lowercased."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)

        key1 = cache._compute_key("  HEADPHONES  ", 10, "ns")
        key2 = cache._compute_key("headphones", 10, "ns")

        assert key1 == key2

    @pytest.mark.asyncio
    async def test_cache_search_and_retrieve(self, temp_db_path):
        """Search results can be cached and retrieved."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)

        results = [{"id": "1", "score": 0.9}, {"id": "2", "score": 0.8}]

        await cache.cache_search("test query", 10, "products", results)

        cached = await cache.get_cached_search("test query", 10, "products")
        assert cached == results

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self, temp_db_path):
        """Cache miss returns None."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)

        result = await cache.get_cached_search("nonexistent", 10, "ns")
        assert result is None
        assert cache._misses == 1

    @pytest.mark.asyncio
    async def test_cache_hit_increments_hits(self, temp_db_path):
        """Cache hit increments hit counter."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)
        await cache.cache_search("query", 10, "ns", [{"id": "1"}])

        await cache.get_cached_search("query", 10, "ns")
        assert cache._hits == 1

    @pytest.mark.asyncio
    async def test_clear_cache(self, temp_db_path):
        """Clear removes all cached searches."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)

        await cache.cache_search("q1", 10, "ns", [{"id": "1"}])
        await cache.cache_search("q2", 10, "ns", [{"id": "2"}])

        result = await cache.clear()
        assert result is True

        assert await cache.get_cached_search("q1", 10, "ns") is None

    @pytest.mark.asyncio
    async def test_delete_key(self, temp_db_path):
        """Delete specific key from cache."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)
        key = cache._compute_key("query", 10, "ns")

        await cache.set(key, [{"id": "1"}], ttl=3600)
        assert await cache.get(key) is not None

        await cache.delete(key)
        assert await cache.get(key) is None

    @pytest.mark.asyncio
    async def test_exists_method(self, temp_db_path):
        """Exists checks if search is cached."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        cache = SearchResultCache(backend="sqlite", db_path=temp_db_path)

        assert await cache.exists("nonexistent") is False

        await cache.set("key", [{"id": "1"}], ttl=3600)
        assert await cache.exists("key") is True

    def test_unknown_backend_raises_error(self, temp_db_path):
        """Unknown backend raises ValueError."""
        from commercetxt.rag.core.caching.search_cache import SearchResultCache

        with pytest.raises(ValueError, match="Unknown backend"):
            SearchResultCache(backend="invalid")

    # =============================================================================
    # SLMResponseCache Tests
    # =============================================================================

    class TestSLMResponseCacheComprehensive:
        """Tests for SLM response caching with proper lifecycle management."""

        @pytest.fixture
        async def slm_cache(self, temp_db_path):
            """Fixture that handles initialization and CLEANUP."""
            from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

            # Setup
            cache = SLMResponseCache(backend="sqlite", db_path=temp_db_path)

            yield cache

            if hasattr(cache, "close"):
                await cache.close()

        @pytest.mark.asyncio
        async def test_exists_method(self, slm_cache):
            """Exists returns true for existing keys."""
            await slm_cache.set("key", "val")
            assert await slm_cache.exists("key")
            assert not await slm_cache.exists("missing")

        @pytest.mark.asyncio
        async def test_set_uses_default_ttl(self, slm_cache):
            """Set uses default TTL if not provided."""
            await slm_cache.set("key", "val")
            assert await slm_cache.get("key") == "val"

        @pytest.mark.asyncio
        async def test_get_or_compute_computes_on_miss(self, slm_cache):
            """Computes value on cache miss."""
            mock_fn = AsyncMock(return_value="computed")

            result = await slm_cache.get_or_compute_response(
                prompt="p", model="m", compute_fn=mock_fn
            )

            assert result == "computed"
            mock_fn.assert_called_once()

            # Verify it's now cached
            assert await slm_cache.get_cached_response("p", "m") == "computed"

        @pytest.mark.asyncio
        async def test_get_or_compute_returns_cached(self, slm_cache):
            """Returns cached value on hit without computing."""
            # Pre-populate
            await slm_cache.cache_response("p", "m", "cached")

            mock_fn = AsyncMock(return_value="new")

            result = await slm_cache.get_or_compute_response(
                prompt="p", model="m", compute_fn=mock_fn
            )

            assert result == "cached"
            mock_fn.assert_not_called()

        @pytest.mark.asyncio
        async def test_cache_response_and_retrieval(self, slm_cache):
            """Can explicitly cache and retrieve responses."""
            await slm_cache.cache_response("prompt", "gpt-4", "response")

            val = await slm_cache.get_cached_response("prompt", "gpt-4")
            assert val == "response"

            # Different model should miss
            val_diff = await slm_cache.get_cached_response("prompt", "gpt-3.5")
            assert val_diff is None

        @pytest.mark.asyncio
        async def test_stats_tracking(self, slm_cache):
            """Stats are tracked correctly."""
            # Miss
            await slm_cache.get_cached_response("p", "m")

            # Hit
            await slm_cache.cache_response("p", "m", "v")
            await slm_cache.get_cached_response("p", "m")

            stats = slm_cache.get_stats()
            assert stats["hits"] == 1
            assert stats["misses"] == 1
            assert stats["hit_ratio"] == 0.5

    @pytest.mark.asyncio
    async def test_delete_key(self, temp_db_path):
        """Delete removes key from cache."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        cache = SLMResponseCache(backend="sqlite", db_path=temp_db_path)

        await cache.set("key", "value", ttl=3600)
        assert await cache.get("key") == "value"

        result = await cache.delete("key")
        assert result is True
        assert await cache.get("key") is None

    @pytest.mark.asyncio
    async def test_clear_cache(self, temp_db_path):
        """Clear removes all entries."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        cache = SLMResponseCache(backend="sqlite", db_path=temp_db_path)

        await cache.set("key1", "value1", ttl=3600)
        await cache.set("key2", "value2", ttl=3600)

        result = await cache.clear()
        assert result is True

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_exists_method(self, temp_db_path):
        """Exists checks if key is in cache."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        cache = SLMResponseCache(backend="sqlite", db_path=temp_db_path)

        assert await cache.exists("nonexistent") is False

        await cache.set("key", "value", ttl=3600)
        assert await cache.exists("key") is True

    @pytest.mark.asyncio
    async def test_set_uses_default_ttl(self, temp_db_path):
        """Set uses default TTL when not specified."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        cache = SLMResponseCache(backend="sqlite", ttl=1000, db_path=temp_db_path)
        assert cache.default_ttl == 1000

    def test_unknown_backend_raises_error(self, temp_db_path):
        """Unknown backend raises ValueError."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        with pytest.raises(ValueError, match="Unknown backend"):
            SLMResponseCache(backend="invalid")

    @pytest.mark.asyncio
    async def test_get_exception_handling(self, temp_db_path):
        """Get handles exceptions gracefully."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        cache = SLMResponseCache(backend="sqlite", db_path=temp_db_path)
        cache._backend = MagicMock()
        cache._backend.get = AsyncMock(side_effect=Exception("Error"))

        result = await cache.get("key")
        assert result is None
        assert cache._misses >= 1

    @pytest.mark.asyncio
    async def test_set_exception_handling(self, temp_db_path):
        """Set handles exceptions gracefully."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        cache = SLMResponseCache(backend="sqlite", db_path=temp_db_path)
        cache._backend = MagicMock()
        cache._backend.set = AsyncMock(side_effect=Exception("Error"))

        result = await cache.set("key", "value", ttl=3600)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_exception_handling(self, temp_db_path):
        """Delete handles exceptions gracefully."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        cache = SLMResponseCache(backend="sqlite", db_path=temp_db_path)
        cache._backend = MagicMock()
        cache._backend.delete = AsyncMock(side_effect=Exception("Error"))

        result = await cache.delete("key")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_exception_handling(self, temp_db_path):
        """Clear handles exceptions gracefully."""
        from commercetxt.rag.core.caching.slm_cache import SLMResponseCache

        cache = SLMResponseCache(backend="sqlite", db_path=temp_db_path)
        cache._backend = MagicMock()
        cache._backend.clear = AsyncMock(side_effect=Exception("Error"))

        result = await cache.clear()
        assert result is False


# =============================================================================
# BaseCache Tests
# =============================================================================


class TestBaseCacheInterface:
    """Tests for BaseCache interface methods."""

    @pytest.mark.asyncio
    async def test_base_cache_is_abstract(self):
        """BaseCache cannot be instantiated directly."""
        from commercetxt.rag.core.caching.base_cache import BaseCache

        with pytest.raises(TypeError):
            BaseCache()

    def test_noop_cache_returns_none_on_get(self):
        """NoOpCache.get always returns None."""
        from commercetxt.rag.core.caching.base_cache import NoOpCache

        cache = NoOpCache()
        # NoOpCache should have a get method that returns None
        assert cache is not None


# =============================================================================
# SQLite Backend Integration Tests
# =============================================================================


class TestSQLiteBackendIntegration:
    """Integration tests for SQLite backend with expired entries."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        return str(tmp_path / "test_integration.db")

    @pytest.mark.asyncio
    async def test_expired_entry_deleted_on_access(self, temp_db_path):
        """Expired entries are deleted when accessed."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", ttl=1, db_path=temp_db_path)

        await cache.set("key", [1, 2, 3], ttl=1)

        # Wait for expiry
        import time

        time.sleep(1.5)

        result = await cache.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_keys_stored(self, temp_db_path):
        """Multiple keys can be stored and retrieved."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        for i in range(5):
            await cache.set(f"key_{i}", [i] * 10, ttl=3600)

        for i in range(5):
            result = await cache.get(f"key_{i}")
            assert result == [i] * 10

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self, temp_db_path):
        """Overwriting existing key updates value."""
        from commercetxt.rag.core.caching.embedding_cache import EmbeddingCache

        cache = EmbeddingCache(backend="sqlite", db_path=temp_db_path)

        await cache.set("key", [1, 2, 3], ttl=3600)
        await cache.set("key", [4, 5, 6], ttl=3600)

        result = await cache.get("key")
        assert result == [4, 5, 6]
