"""
Comprehensive tests for async RAG interfaces, drivers, and parser.

Covers AsyncFaissStore, AsyncOpenAIEmbedder, async interfaces, and AsyncCommerceTXTParser.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# AsyncCommerceTXTParser Tests (consolidated from test_async_parser.py)
# =============================================================================


class TestAsyncCommerceTXTParser:
    """Async parser tests for concurrent parsing."""

    @pytest.mark.asyncio
    async def test_async_parse_many(self):
        """Multiple contents parsed concurrently."""
        from commercetxt.async_parser import AsyncCommerceTXTParser

        contents = ["# @S1\nK: V1", "# @S2\nK: V2", "Invalid line without section"]
        async_parser = AsyncCommerceTXTParser()
        results = await async_parser.parse_many(contents)

        assert len(results) == 3
        assert results[0].directives["S1"]["K"] == "V1"
        assert len(results[2].warnings) > 0

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Context manager shuts down executor on exit."""
        from commercetxt.async_parser import AsyncCommerceTXTParser

        async with AsyncCommerceTXTParser(executor_type="thread") as p:
            results = await p.parse_many(["# @S\nK: V"])
            assert len(results) == 1

    def test_async_parser_invalid_executor(self):
        """Invalid executor type raises ValueError."""
        from commercetxt.async_parser import AsyncCommerceTXTParser

        with pytest.raises(ValueError, match="Invalid executor_type"):
            AsyncCommerceTXTParser(executor_type="invalid")

    def test_async_parser_negative_workers(self):
        """Negative workers raises ValueError."""
        from commercetxt.async_parser import AsyncCommerceTXTParser

        with pytest.raises(ValueError, match="max_workers must be non-negative"):
            AsyncCommerceTXTParser(max_workers=-1)

    def test_async_parser_zero_workers_valid(self):
        """Zero workers is valid. System chooses default."""
        from commercetxt.async_parser import AsyncCommerceTXTParser

        parser = AsyncCommerceTXTParser(max_workers=0)
        assert parser.max_workers == 0

    @pytest.mark.asyncio
    async def test_async_process_executor(self):
        """Process executor created and cleaned up."""
        from commercetxt.async_parser import AsyncCommerceTXTParser

        p = AsyncCommerceTXTParser(executor_type="process", max_workers=2)
        assert p._executor is None
        p._get_executor()
        assert p.executor_type == "process"
        if p._executor:
            p._executor.shutdown()

    @pytest.mark.asyncio
    async def test_async_parse_with_exception_handling(self):
        """Exceptions in parser are caught. Empty results returned."""
        from commercetxt.async_parser import AsyncCommerceTXTParser

        class BrokenParser:
            def parse(self, text):
                raise RuntimeError("Boom")

        p = AsyncCommerceTXTParser(parser_instance=BrokenParser())
        results = await p.parse_many(["some content"])
        assert len(results) == 0


# =============================================================================
# AsyncBaseEmbedder Tests
# =============================================================================


class TestAsyncBaseEmbedderInterface:
    """Tests for AsyncBaseEmbedder abstract interface."""

    def test_async_embedder_is_abstract(self):
        """AsyncBaseEmbedder cannot be instantiated directly."""
        from commercetxt.rag.interfaces.async_embedder import AsyncBaseEmbedder

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AsyncBaseEmbedder()

    def test_async_embedder_requires_embed_text(self):
        """Subclass must implement embed_text."""
        from commercetxt.rag.interfaces.async_embedder import AsyncBaseEmbedder

        class IncompleteEmbedder(AsyncBaseEmbedder):
            async def embed_texts(self, texts):
                return []

            async def embed_shards(self, shards):
                return []

        with pytest.raises(TypeError):
            IncompleteEmbedder()

    def test_async_embedder_requires_embed_texts(self):
        """Subclass must implement embed_texts."""
        from commercetxt.rag.interfaces.async_embedder import AsyncBaseEmbedder

        class IncompleteEmbedder(AsyncBaseEmbedder):
            async def embed_text(self, text):
                return []

            async def embed_shards(self, shards):
                return []

        with pytest.raises(TypeError):
            IncompleteEmbedder()

    def test_async_embedder_requires_embed_shards(self):
        """Subclass must implement embed_shards."""
        from commercetxt.rag.interfaces.async_embedder import AsyncBaseEmbedder

        class IncompleteEmbedder(AsyncBaseEmbedder):
            async def embed_text(self, text):
                return []

            async def embed_texts(self, texts):
                return []

        with pytest.raises(TypeError):
            IncompleteEmbedder()

    def test_async_embedder_complete_implementation(self):
        """Complete implementation can be instantiated."""
        from commercetxt.rag.interfaces.async_embedder import AsyncBaseEmbedder

        class CompleteEmbedder(AsyncBaseEmbedder):
            async def embed_text(self, text):
                return [0.1] * 384

            async def embed_texts(self, texts):
                return [[0.1] * 384 for _ in texts]

            async def embed_shards(self, shards):
                for s in shards:
                    s["values"] = [0.1] * 384
                return shards

        embedder = CompleteEmbedder()
        assert embedder is not None


# =============================================================================
# AsyncBaseVectorStore Tests
# =============================================================================


class TestAsyncBaseVectorStoreInterface:
    """Tests for AsyncBaseVectorStore abstract interface."""

    def test_async_vector_store_is_abstract(self):
        """AsyncBaseVectorStore cannot be instantiated directly."""
        from commercetxt.rag.interfaces.async_vector_store import AsyncBaseVectorStore

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AsyncBaseVectorStore()

    def test_async_vector_store_requires_connect(self):
        """Subclass must implement connect."""
        from commercetxt.rag.interfaces.async_vector_store import AsyncBaseVectorStore

        class IncompleteStore(AsyncBaseVectorStore):
            async def upsert(self, shards, namespace):
                return 0

            async def search(self, vector, top_k, namespace):
                return []

            async def delete(self, ids, namespace, delete_all):
                return True

            async def health_check(self):
                return {}

        with pytest.raises(TypeError):
            IncompleteStore()

    def test_async_vector_store_requires_upsert(self):
        """Subclass must implement upsert."""
        from commercetxt.rag.interfaces.async_vector_store import AsyncBaseVectorStore

        class IncompleteStore(AsyncBaseVectorStore):
            async def connect(self):
                return True

            async def search(self, vector, top_k, namespace):
                return []

            async def delete(self, ids, namespace, delete_all):
                return True

            async def health_check(self):
                return {}

        with pytest.raises(TypeError):
            IncompleteStore()

    def test_async_vector_store_requires_search(self):
        """Subclass must implement search."""
        from commercetxt.rag.interfaces.async_vector_store import AsyncBaseVectorStore

        class IncompleteStore(AsyncBaseVectorStore):
            async def connect(self):
                return True

            async def upsert(self, shards, namespace):
                return 0

            async def delete(self, ids, namespace, delete_all):
                return True

            async def health_check(self):
                return {}

        with pytest.raises(TypeError):
            IncompleteStore()

    def test_async_vector_store_complete_implementation(self):
        """Complete implementation can be instantiated."""
        from commercetxt.rag.interfaces.async_vector_store import AsyncBaseVectorStore

        class CompleteStore(AsyncBaseVectorStore):
            async def connect(self):
                return True

            async def upsert(self, shards, namespace):
                return len(shards)

            async def search(self, vector, top_k=5, namespace=None):
                return []

            async def delete(self, ids=None, namespace=None, delete_all=False):
                return True

            async def health_check(self):
                return {"status": "ok"}

        store = CompleteStore()
        assert store is not None


# =============================================================================
# AsyncFaissStore Tests (Mocked)
# =============================================================================


class TestAsyncFaissStoreMocked:
    """Tests for AsyncFaissStore with mocked Faiss."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        return str(tmp_path / "faiss_store")

    @pytest.mark.asyncio
    async def test_connect_creates_directory(self, temp_dir):
        """Connect creates root directory."""
        from commercetxt.rag.drivers.async_faiss_store import AsyncFaissStore

        store = AsyncFaissStore(root_dir=temp_dir, dimension=384)

        result = await store.connect()

        assert result is True
        assert store._connected is True

    @pytest.mark.asyncio
    async def test_connect_failure_handling(self, temp_dir, monkeypatch):
        """Connect handles errors gracefully."""
        from commercetxt.rag.drivers.async_faiss_store import AsyncFaissStore

        store = AsyncFaissStore(root_dir=temp_dir, dimension=384)

        # Mock mkdir to fail
        async def failing_mkdir(*args, **kwargs):
            raise PermissionError("Cannot create directory")

        monkeypatch.setattr(asyncio, "to_thread", failing_mkdir)

        result = await store.connect()
        assert result is False

    def test_namespace_path_construction(self, temp_dir):
        """Namespace path constructed correctly."""
        from pathlib import Path

        from commercetxt.rag.drivers.async_faiss_store import AsyncFaissStore

        store = AsyncFaissStore(root_dir=temp_dir, dimension=384)

        path = store._get_namespace_path("products")
        assert path == Path(temp_dir) / "products"

    def test_index_path_construction(self, temp_dir):
        """Index path constructed correctly."""
        from pathlib import Path

        from commercetxt.rag.drivers.async_faiss_store import AsyncFaissStore

        store = AsyncFaissStore(root_dir=temp_dir, dimension=384)

        path = store._get_index_path("products")
        assert path == Path(temp_dir) / "products" / "index.faiss"

    def test_metadata_path_construction(self, temp_dir):
        """Metadata path constructed correctly."""
        from pathlib import Path

        from commercetxt.rag.drivers.async_faiss_store import AsyncFaissStore

        store = AsyncFaissStore(root_dir=temp_dir, dimension=384)

        path = store._get_metadata_path("products")
        assert path == Path(temp_dir) / "products" / "metadata.json"

    def test_db_path_construction(self, temp_dir):
        """DB path constructed correctly."""
        from pathlib import Path

        from commercetxt.rag.drivers.async_faiss_store import AsyncFaissStore

        store = AsyncFaissStore(root_dir=temp_dir, dimension=384)

        path = store._get_db_path("products")
        assert path == Path(temp_dir) / "products" / "idmap.db"

    def test_ensure_namespace_lock(self, temp_dir):
        """Lock created for namespace."""
        from commercetxt.rag.drivers.async_faiss_store import AsyncFaissStore

        store = AsyncFaissStore(root_dir=temp_dir, dimension=384)

        lock1 = store._ensure_namespace_lock("products")
        lock2 = store._ensure_namespace_lock("products")

        assert lock1 is lock2  # Same lock returned

    def test_initialization_params(self, temp_dir):
        """Initialization stores parameters."""
        from commercetxt.rag.drivers.async_faiss_store import AsyncFaissStore

        store = AsyncFaissStore(root_dir=temp_dir, dimension=512, nlist=256, nprobe=16)

        assert store.dimension == 512
        assert store.nlist == 256
        assert store.nprobe == 16

    def test_l2_normalize_function(self):
        """L2 normalization works correctly."""
        import numpy as np

        from commercetxt.rag.drivers.async_faiss_store import _l2_normalize

        vectors = np.array([[3.0, 4.0], [1.0, 0.0]], dtype=np.float32)
        normalized = _l2_normalize(vectors)

        # Check unit length
        norms = np.linalg.norm(normalized, axis=1)
        np.testing.assert_array_almost_equal(norms, [1.0, 1.0], decimal=5)


# =============================================================================
# AsyncOpenAIEmbedder Tests (Mocked)
# =============================================================================


class TestAsyncOpenAIEmbedderMocked:
    """Tests for AsyncOpenAIEmbedder with mocked API."""

    def test_missing_api_key_raises_error(self, monkeypatch):
        """Missing API key raises ValueError."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        with pytest.raises(ValueError, match="API key required"):
            AsyncOpenAIEmbedder(api_key=None)

    def test_api_key_from_env(self, monkeypatch):
        """API key read from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        embedder = AsyncOpenAIEmbedder()
        assert embedder.api_key == "sk-test-key"

    def test_initialization_params(self, monkeypatch):
        """Initialization stores parameters."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        embedder = AsyncOpenAIEmbedder(
            model="text-embedding-ada-002",
            requests_per_second=5.0,
            timeout=60.0,
        )

        assert embedder.model == "text-embedding-ada-002"
        assert embedder.timeout == 60.0

    @pytest.mark.asyncio
    async def test_context_manager(self, monkeypatch):
        """Context manager creates and closes client."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        # Mock httpx
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()

        with patch(
            "commercetxt.rag.drivers.async_openai_embedder.AsyncOpenAIEmbedder._get_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            from commercetxt.rag.drivers.async_openai_embedder import (
                AsyncOpenAIEmbedder,
            )

            async with AsyncOpenAIEmbedder():
                pass

    @pytest.mark.asyncio
    async def test_embed_text_calls_api(self, monkeypatch):
        """embed_text calls API correctly."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        embedder = AsyncOpenAIEmbedder()

        # Mock _call_api
        embedder._call_api = AsyncMock(return_value=[[0.1] * 384])

        result = await embedder.embed_text("test text")

        assert result == [0.1] * 384
        embedder._call_api.assert_called_once_with(["test text"])

    @pytest.mark.asyncio
    async def test_embed_texts_empty_list(self, monkeypatch):
        """embed_texts handles empty list."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        embedder = AsyncOpenAIEmbedder()

        result = await embedder.embed_texts([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_texts_batching(self, monkeypatch):
        """embed_texts batches large requests."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        embedder = AsyncOpenAIEmbedder()

        # Create 150 texts (batch size is 100)
        texts = [f"text_{i}" for i in range(150)]

        # Mock _call_api
        embedder._call_api = AsyncMock(
            side_effect=[
                [[0.1] * 384] * 100,  # First batch
                [[0.2] * 384] * 50,  # Second batch
            ]
        )

        result = await embedder.embed_texts(texts)

        assert len(result) == 150
        assert embedder._call_api.call_count == 2

    @pytest.mark.asyncio
    async def test_embed_shards_empty_list(self, monkeypatch):
        """embed_shards handles empty list."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        embedder = AsyncOpenAIEmbedder()

        result = await embedder.embed_shards([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_shards_adds_values(self, monkeypatch):
        """embed_shards adds values to each shard."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        embedder = AsyncOpenAIEmbedder()

        shards = [
            {"text": "product 1", "metadata": {}},
            {"text": "product 2", "metadata": {}},
        ]

        # Mock embed_texts
        embedder.embed_texts = AsyncMock(return_value=[[0.1] * 384, [0.2] * 384])

        result = await embedder.embed_shards(shards)

        assert len(result) == 2
        assert "values" in result[0]
        assert "model" in result[0]

    @pytest.mark.asyncio
    async def test_close_client(self, monkeypatch):
        """close() closes HTTP client."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from commercetxt.rag.drivers.async_openai_embedder import AsyncOpenAIEmbedder

        embedder = AsyncOpenAIEmbedder()
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        embedder._client = mock_client

        await embedder.close()

        mock_client.aclose.assert_called_once()
        assert embedder._client is None


# =============================================================================
# AsyncRedisStorage Tests (Mocked)
# =============================================================================


class TestAsyncRedisStorageMocked:
    """Tests for AsyncRedisStorage with mocked Redis."""

    @pytest.mark.asyncio
    async def test_initialization_params(self):
        """Initialization stores parameters."""
        from commercetxt.rag.drivers.async_redis_storage import AsyncRedisStorage

        storage = AsyncRedisStorage(
            host="redis.example.com",
            port=6380,
            db=5,
            key_prefix="test_prefix",
        )

        assert storage.host == "redis.example.com"
        assert storage.port == 6380
        assert storage.db == 5
        assert storage.key_prefix == "test_prefix"

    @pytest.mark.asyncio
    async def test_default_key_prefix(self):
        """Default key prefix is commercetxt."""
        from commercetxt.rag.drivers.async_redis_storage import AsyncRedisStorage

        storage = AsyncRedisStorage()

        assert storage.key_prefix == "commercetxt"

    @pytest.mark.asyncio
    async def test_default_ttl(self):
        """Default TTL is 3600."""
        from commercetxt.rag.drivers.async_redis_storage import AsyncRedisStorage

        storage = AsyncRedisStorage()

        assert storage.default_ttl == 3600

    @pytest.mark.asyncio
    async def test_custom_ttl(self):
        """Custom TTL is stored."""
        from commercetxt.rag.drivers.async_redis_storage import AsyncRedisStorage

        storage = AsyncRedisStorage(default_ttl=7200)

        assert storage.default_ttl == 7200


# =============================================================================
# Async Storage Interface Tests
# =============================================================================


class TestAsyncStorageInterface:
    """Tests for async storage interface."""

    def test_async_storage_is_abstract(self):
        """AsyncBaseStorage cannot be instantiated directly."""
        from commercetxt.rag.interfaces.async_storage import AsyncBaseStorage

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            AsyncBaseStorage()

    def test_complete_async_storage_implementation(self):
        """Complete implementation can be instantiated."""
        from commercetxt.rag.interfaces.async_storage import AsyncBaseStorage

        class CompleteStorage(AsyncBaseStorage):
            async def get_live_attributes(self, product_ids, fields):
                return {}

            async def set_live_attributes(self, product_id, attributes):
                return True

            async def health_check(self):
                return {"status": "healthy"}

        storage = CompleteStorage()
        assert storage is not None
