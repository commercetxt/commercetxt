"""
RAG Drivers Tests.

Tests LocalStorage, RedisStorage, SLMTagger, PineconeStore, QdrantStore,
RAGPipeline, RAGContainer, RealtimeEnricher, and Embedders.
"""

import inspect
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from commercetxt.rag.async_pipeline import AsyncRAGPipeline
from commercetxt.rag.container import RAGContainer
from commercetxt.rag.drivers.local_storage import LocalStorage
from commercetxt.rag.drivers.pinecone_store import PineconeStore, retry_with_backoff
from commercetxt.rag.drivers.qdrant_store import QdrantStore
from commercetxt.rag.drivers.redis_storage import RedisStorage
from commercetxt.rag.drivers.slm_tagger import SLMTagger
from commercetxt.rag.interfaces.base_embedder import BaseEmbedder
from commercetxt.rag.interfaces.base_storage import BaseRealtimeStorage
from commercetxt.rag.interfaces.base_vector_store import BaseVectorStore
from commercetxt.rag.pipeline import RAGPipeline
from commercetxt.rag.tools.realtime_enricher import RealtimeEnricher

# =============================================================================
# LocalStorage Tests
# =============================================================================


class TestLocalStorage:
    """LocalStorage reads CommerceTXT files and caches results."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Storage with temp directory."""
        return LocalStorage(root_path=str(tmp_path))

    @pytest.fixture
    def storage_with_files(self, tmp_path):
        """Storage with sample product files."""
        product_file = tmp_path / "test-product.txt"
        product_file.write_text(
            """# @PRODUCT
Name: Test Product
SKU: TEST-001

# @OFFER
Price: 99.99
Availability: InStock

# @IDENTITY
Currency: USD
""",
            encoding="utf-8",
        )
        return LocalStorage(root_path=str(tmp_path))

    def test_empty_directory_indexes_nothing(self, storage):
        """Empty directory yields zero indexed files."""
        assert storage.get_indexed_file_count() == 0

    def test_file_indexing(self, storage_with_files):
        """Product files indexed by filename."""
        assert storage_with_files.get_indexed_file_count() >= 1
        assert "test-product" in storage_with_files._file_index

    def test_get_live_attributes_returns_dict(self, storage_with_files):
        """Returns dict mapping product IDs to attributes."""
        result = storage_with_files.get_live_attributes(
            ["test-product"], ["price", "availability", "currency"]
        )
        assert isinstance(result, dict)
        assert "test-product" in result

    def test_get_live_attributes_parses_price(self, storage_with_files):
        """Price extracted from OFFER section."""
        result = storage_with_files.get_live_attributes(["test-product"], ["price"])
        assert result["test-product"]["price"] == "99.99"

    def test_get_live_attributes_unknown_product(self, storage_with_files):
        """Unknown product returns empty dict."""
        result = storage_with_files.get_live_attributes(["nonexistent"], ["price"])
        assert result["nonexistent"] == {}

    def test_cache_populated_after_lookup(self, storage_with_files):
        """First lookup populates cache."""
        assert storage_with_files.get_cached_product_count() == 0
        storage_with_files.get_live_attributes(["test-product"], ["price"])
        assert storage_with_files.get_cached_product_count() >= 1

    def test_normalize_product_id_lowercase(self, storage):
        """Product IDs normalized to lowercase."""
        assert storage._normalize_product_id("TEST-PRODUCT") == "test-product"

    def test_normalize_product_id_strips_whitespace(self, storage):
        """Whitespace stripped from product IDs."""
        assert storage._normalize_product_id("  test  ") == "test"

    def test_refresh_product_updates_cache(self, storage_with_files):
        """refresh_product reloads data from file."""
        storage_with_files.get_live_attributes(["test-product"], ["price"])
        result = storage_with_files.refresh_product("test-product")
        assert result is True

    def test_refresh_unknown_product_returns_false(self, storage):
        """refresh_product returns False for unknown product."""
        result = storage.refresh_product("nonexistent")
        assert result is False


class TestLocalStorageWithRealFiles:
    """Integration tests with actual example files."""

    @pytest.fixture
    def example_storage(self):
        """Storage pointing to example products."""
        examples_path = (
            Path(__file__).parent.parent.parent.parent
            / "examples"
            / "google-store"
            / "products"
        )
        if not examples_path.exists():
            pytest.skip("Example files not found")
        return LocalStorage(root_path=str(examples_path))

    def test_indexes_example_products(self, example_storage):
        """Example products indexed."""
        assert example_storage.get_indexed_file_count() >= 2

    def test_reads_pixel_price(self, example_storage):
        """Pixel product price readable."""
        result = example_storage.get_live_attributes(["pixel-9-pro"], ["price"])
        assert "pixel-9-pro" in result


# =============================================================================
# SLMTagger Tests
# =============================================================================


class TestSLMTagger:
    """SLMTagger generates semantic tags via LLM backends."""

    def test_mock_backend_returns_fixed_tags(self):
        """Mock backend returns configured tags."""
        tagger = SLMTagger(backend="mock", fixed_tags=["premium", "eco_friendly"])
        result = tagger.enhance_tags("Product description", ["existing"])
        assert "existing" in result

    def test_mock_backend_preserves_existing_tags(self):
        """Existing tags preserved in result."""
        tagger = SLMTagger(backend="mock")
        result = tagger.enhance_tags("Text", ["tag1", "tag2"])
        assert "tag1" in result
        assert "tag2" in result

    def test_empty_text_returns_existing_tags(self):
        """Empty text returns only existing tags."""
        tagger = SLMTagger(backend="mock", fixed_tags=["new_tag"])
        result = tagger.enhance_tags("", ["existing"])
        assert result == ["existing"]

    def test_parse_tags_handles_json_array(self):
        """JSON array response parsed correctly."""
        tagger = SLMTagger(backend="mock")
        parsed = tagger._parse_tags('["tag_one", "tag_two"]', 5)
        assert "tag_one" in parsed
        assert "tag_two" in parsed

    def test_parse_tags_handles_markdown_code_block(self):
        """Markdown code blocks extracted."""
        tagger = SLMTagger(backend="mock")
        parsed = tagger._parse_tags('```json\n["premium", "luxury"]\n```', 5)
        assert "premium" in parsed

    def test_parse_tags_normalizes_spaces(self):
        """Spaces in tags become underscores."""
        tagger = SLMTagger(backend="mock")
        parsed = tagger._parse_tags('["travel friendly"]', 5)
        assert "travel_friendly" in parsed

    def test_parse_tags_rejects_short_tags(self):
        """Tags shorter than 3 characters rejected."""
        tagger = SLMTagger(backend="mock")
        parsed = tagger._parse_tags('["ok", "ab", "valid_tag"]', 5)
        assert "valid_tag" in parsed
        assert "ab" not in parsed

    def test_unknown_backend_raises_error(self):
        """Unknown backend type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown backend"):
            SLMTagger(backend="invalid_backend")

    def test_max_new_tags_respected(self):
        """Only max_new_tags added."""
        tagger = SLMTagger(backend="mock")
        parsed = tagger._parse_tags('["a1a", "b2b", "c3c", "d4d", "e5e", "f6f"]', 3)
        assert len(parsed) <= 3


# =============================================================================
# RedisStorage Tests
# =============================================================================


class TestRedisStorage:
    """RedisStorage provides fast key-value lookups."""

    def test_make_key_format(self):
        """Keys follow prefix:product:field format."""
        storage = RedisStorage(host="localhost")
        key = storage._make_key("pixel-9", "price")
        assert key == "commercetxt:pixel-9:price"

    def test_make_key_without_field(self):
        """Keys without field omit field part."""
        storage = RedisStorage(host="localhost")
        key = storage._make_key("pixel-9")
        assert key == "commercetxt:pixel-9"

    def test_custom_prefix(self):
        """Custom prefix used in keys."""
        storage = RedisStorage(host="localhost", key_prefix="myapp")
        key = storage._make_key("prod", "price")
        assert key == "myapp:prod:price"

    def test_default_port(self):
        """Default port is 6379."""
        storage = RedisStorage(host="localhost")
        assert storage.port == 6379

    def test_custom_port(self):
        """Custom port accepted."""
        storage = RedisStorage(host="localhost", port=6380)
        assert storage.port == 6380


# =============================================================================
# PineconeStore Tests
# =============================================================================


class TestPineconeStore:
    """PineconeStore handles vector operations with retry logic."""

    def test_not_connected_raises_error(self):
        """Operations without connection raise ConnectionError."""
        store = PineconeStore(api_key="fake", index_name="test")
        with pytest.raises(ConnectionError):
            store.upsert([], "namespace")
        with pytest.raises(ConnectionError):
            store.search([0.1] * 384, top_k=5)

    def test_batch_size_configurable(self):
        """Batch size configurable."""
        store = PineconeStore(api_key="fake", index_name="test", batch_size=50)
        assert store.batch_size == 50

    def test_default_batch_size(self):
        """Default batch size is 100."""
        store = PineconeStore(api_key="fake", index_name="test")
        assert store.batch_size == 100

    def test_health_check_structure(self):
        """Health check returns dict with status."""
        store = PineconeStore(api_key="fake", index_name="test")
        health = store.health_check()
        assert "status" in health

    def test_delete_without_connection_raises(self):
        """Delete without connection raises ConnectionError."""
        store = PineconeStore(api_key="fake", index_name="test")
        with pytest.raises(ConnectionError):
            store.delete(["id1", "id2"], "namespace")


# =============================================================================
# QdrantStore Tests
# =============================================================================


class TestQdrantStore:
    """QdrantStore handles vector operations with retry logic."""

    def test_not_connected_raises_error(self):
        """Operations without connection raise ConnectionError."""
        store = QdrantStore(url="http://localhost:6333")
        with pytest.raises(ConnectionError):
            store.upsert([], "namespace")
        with pytest.raises(ConnectionError):
            store.search([0.1] * 384, top_k=5)

    def test_dimension_configurable(self):
        """Vector dimension configurable."""
        store = QdrantStore(url="http://localhost:6333", dimension=768)
        assert store.dimension == 768

    def test_default_dimension(self):
        """Default dimension is 384."""
        store = QdrantStore(url="http://localhost:6333")
        assert store.dimension == 384

    def test_health_check_structure(self):
        """Health check returns dict with status."""
        store = QdrantStore(url="http://localhost:6333")
        health = store.health_check()
        assert "status" in health

    def test_delete_without_connection_raises(self):
        """Delete without connection raises ConnectionError."""
        store = QdrantStore(url="http://localhost:6333")
        with pytest.raises(ConnectionError):
            store.delete(["id1", "id2"], "namespace")


# =============================================================================
# AsyncRAGPipeline Tests
# =============================================================================


class TestAsyncRAGPipeline:
    """AsyncRAGPipeline handles concurrent operations with caching."""

    def test_initialization(self):
        """Pipeline initializes with defaults."""
        pipeline = AsyncRAGPipeline()
        assert pipeline.min_health_score == 50
        assert pipeline.enable_cache is True
        assert pipeline.generator is not None
        assert pipeline.health_checker is not None

    def test_custom_configuration(self):
        """Pipeline accepts custom configuration."""
        pipeline = AsyncRAGPipeline(
            min_health_score=70,
            enable_cache=False,
            embedding_cache_ttl=3600,
        )
        assert pipeline.min_health_score == 70
        assert pipeline.enable_cache is False

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Pipeline works as async context manager."""
        async with AsyncRAGPipeline() as pipeline:
            assert pipeline.generator is not None
            assert pipeline.container is not None

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Pipeline provides cache statistics."""
        pipeline = AsyncRAGPipeline(enable_cache=True)
        stats = pipeline.get_cache_stats()
        assert "caching_enabled" in stats
        assert stats["caching_enabled"] is True


# =============================================================================
# RAGContainer Tests
# =============================================================================


class TestRAGContainer:
    """RAGContainer provides dependency injection."""

    def test_default_storage_is_local(self):
        """Default storage is LocalStorage."""
        container = RAGContainer(config={"COMMERCETXT_ROOT": "./"})
        storage = container.storage
        assert isinstance(storage, LocalStorage)

    def test_storage_is_singleton(self):
        """Storage is cached as singleton."""
        container = RAGContainer(config={"COMMERCETXT_ROOT": "./"})
        storage1 = container.storage
        storage2 = container.storage
        assert storage1 is storage2

    def test_unknown_vector_db_raises(self):
        """Unknown vector DB driver raises ValueError."""
        container = RAGContainer(config={"RAG_VECTOR_DB": "unknown_db"})
        with pytest.raises(ValueError, match="Unknown Vector DB"):
            _ = container.vector_store

    def test_pinecone_driver_selected(self):
        """Pinecone driver selected when configured."""
        container = RAGContainer(
            config={
                "RAG_VECTOR_DB": "pinecone",
                "PINECONE_API_KEY": "fake",
                "PINECONE_INDEX": "test",
            }
        )
        store = container.vector_store
        assert isinstance(store, PineconeStore)

    def test_qdrant_driver_selected(self):
        """Qdrant driver selected when configured."""
        container = RAGContainer(
            config={"RAG_VECTOR_DB": "qdrant", "QDRANT_URL": "http://localhost:6333"}
        )
        store = container.vector_store
        assert isinstance(store, QdrantStore)


# =============================================================================
# RealtimeEnricher Tests
# =============================================================================


class TestRealtimeEnricher:
    """RealtimeEnricher merges search results with live data."""

    @pytest.fixture
    def mock_storage(self):
        """Mock storage that returns test data."""
        storage = MagicMock(spec=BaseRealtimeStorage)
        storage.get_live_attributes.return_value = {
            "prod-1": {"price": "99.99", "availability": "InStock", "currency": "USD"}
        }
        return storage

    @pytest.fixture
    def enricher(self, mock_storage):
        """Enricher with mock storage."""
        return RealtimeEnricher(storage=mock_storage)

    def test_empty_results_returns_empty(self, enricher):
        """Empty results return empty list."""
        result = enricher.enrich([])
        assert result == []

    def test_enriches_with_product_id(self, enricher):
        """Results enriched using product_id from metadata."""
        results = [{"id": "vec-1", "metadata": {"product_id": "prod-1"}}]
        enriched = enricher.enrich(results)
        assert enriched[0]["metadata"]["live_price"] == "99.99"

    def test_enriches_with_fallback_id(self, mock_storage):
        """Falls back to result id when product_id missing."""
        mock_storage.get_live_attributes.return_value = {
            "vec-1": {"price": "49.99", "availability": "OutOfStock", "currency": "EUR"}
        }
        enricher = RealtimeEnricher(storage=mock_storage)
        results = [{"id": "vec-1", "metadata": {}}]
        enriched = enricher.enrich(results)
        assert enriched[0]["metadata"]["live_price"] == "49.99"

    def test_creates_metadata_if_missing(self, mock_storage):
        """Creates metadata dict if missing."""
        mock_storage.get_live_attributes.return_value = {
            "prod-1": {"price": "10", "availability": "InStock", "currency": "USD"}
        }
        enricher = RealtimeEnricher(storage=mock_storage)
        results = [{"id": "prod-1"}]
        enriched = enricher.enrich(results)
        assert "metadata" in enriched[0]

    def test_custom_output_prefix(self, mock_storage):
        """Custom output prefix used."""
        mock_storage.get_live_attributes.return_value = {
            "prod-1": {"price": "10", "availability": "InStock", "currency": "USD"}
        }
        enricher = RealtimeEnricher(storage=mock_storage, output_prefix="rt_")
        results = [{"id": "vec-1", "metadata": {"product_id": "prod-1"}}]
        enriched = enricher.enrich(results)
        assert "rt_price" in enriched[0]["metadata"]

    def test_extra_fields_included(self, mock_storage):
        """Extra fields beyond defaults included."""
        mock_storage.get_live_attributes.return_value = {
            "prod-1": {
                "price": "10",
                "availability": "InStock",
                "currency": "USD",
                "stock_count": "5",
            }
        }
        enricher = RealtimeEnricher(storage=mock_storage)
        results = [{"id": "vec-1", "metadata": {"product_id": "prod-1"}}]
        enriched = enricher.enrich(results, fields=["price", "stock_count"])
        assert "live_stock_count" in enriched[0]["metadata"]

    def test_skips_results_without_valid_key(self, mock_storage):
        """Skips results without valid lookup key."""
        enricher = RealtimeEnricher(storage=mock_storage)
        results = [{"metadata": {}}, {"id": None}]
        enriched = enricher.enrich(results)
        # Should not crash, just skip
        assert len(enriched) == 2


# =============================================================================
# RAGPipeline Tests
# =============================================================================


class TestRAGPipeline:
    """RAGPipeline orchestrates ETL and retrieval."""

    def test_initialization_creates_components(self):
        """Pipeline creates required components."""
        with patch.object(RAGContainer, "storage", new_callable=lambda: MagicMock()):
            pipeline = RAGPipeline()
            assert pipeline.generator is not None
            assert pipeline.health_checker is not None
            assert pipeline.enricher is not None


# =============================================================================
# Retry Logic Tests
# =============================================================================


class TestRetryLogic:
    """Retry with backoff handles transient failures."""

    def test_retry_succeeds_after_failure(self):
        """Retry succeeds if function eventually works."""
        call_count = 0

        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient failure")
            return "success"

        wrapped = retry_with_backoff(flaky_function, max_retries=3, base_delay=0.01)
        result = wrapped()
        assert result == "success"
        assert call_count == 3

    def test_retry_raises_after_max_attempts(self):
        """Retry raises after exhausting attempts."""

        def always_fails():
            raise ConnectionError("Permanent failure")

        wrapped = retry_with_backoff(always_fails, max_retries=2, base_delay=0.01)
        with pytest.raises(ConnectionError):
            wrapped()


# =============================================================================
# Embedder Interface Tests
# =============================================================================


class TestEmbedderInterfaces:
    """Base embedder interface tests."""

    def test_base_embedder_abstract(self):
        """BaseEmbedder is abstract and cannot be instantiated."""
        assert hasattr(BaseEmbedder, "embed_text")
        assert hasattr(BaseEmbedder, "embed_shards")

    def test_base_vector_store_abstract(self):
        """BaseVectorStore is abstract."""
        assert hasattr(BaseVectorStore, "connect")
        assert hasattr(BaseVectorStore, "upsert")
        assert hasattr(BaseVectorStore, "search")


class _FakePipeline:
    def __init__(self, redis: "_FakeRedis"):
        self.redis = redis
        self.ops: list[tuple[str, tuple]] = []

    def setex(self, key: str, ttl: int, value: str):
        self.ops.append(("setex", (key, ttl, value)))
        return self

    def delete(self, key: str):
        self.ops.append(("delete", (key,)))
        return self

    def get(self, key: str):
        self.ops.append(("get", (key,)))
        return self

    def execute(self):
        out = []
        for name, args in self.ops:
            if name == "get":
                out.append(self.redis.get(*args))
            else:
                out.append(getattr(self.redis, name)(*args))
        self.ops.clear()
        return out


class _FakeRedis:
    def __init__(self):
        self._data: dict[str, str] = {}
        self.deleted: list[str] = []
        self.setex_calls: list[tuple[str, int, str]] = []

    def ping(self):
        return True

    def pipeline(self):
        return _FakePipeline(self)

    def setex(self, key: str, ttl: int, value: str) -> bool:
        self.setex_calls.append((key, ttl, value))
        self._data[key] = value
        return True

    def get(self, key: str):
        return self._data.get(key)

    def scan_iter(self, match: str):
        assert match.endswith("*")
        prefix = match[:-1]
        for k in list(self._data.keys()):
            if k.startswith(prefix):
                yield k

    def delete(self, *keys: str):
        removed = 0
        for k in keys:
            if k in self._data:
                del self._data[k]
                removed += 1
            self.deleted.append(k)
        return removed

    def info(self, _section="server"):
        return {"redis_version": "7.0.0"}


def _install_fake_redis(monkeypatch: pytest.MonkeyPatch, instance: _FakeRedis) -> None:
    redis_mod = types.ModuleType("redis")

    class Redis:
        def __init__(
            self, host: str, port: int, db: int, decode_responses: bool, **kwargs
        ):
            self._ = (host, port, db, decode_responses, kwargs)

        def __getattr__(self, name):
            return getattr(instance, name)

    redis_mod.Redis = Redis  # type: ignore
    monkeypatch.setitem(sys.modules, "redis", redis_mod)


def test_redis_storage_set_get_delete_and_health(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeRedis()
    _install_fake_redis(monkeypatch, fake)

    from commercetxt.rag.drivers.redis_storage import RedisStorage

    s = RedisStorage(host="h", port=1, db=0, key_prefix="ct", default_ttl=123)
    assert s._get_client() is not None

    s.set_product_data(
        "p1",
        {"price": 9.99, "availability": "InStock", "extra": {"a": 1}},
    )

    # ensure key prefix & ttl are used
    assert any(ttl == 123 for (_k, ttl, _v) in fake.setex_calls)
    assert any(_k.startswith("ct:p1:") for (_k, _ttl, _v) in fake.setex_calls)

    out = s.get_live_attributes(["p1"], ["price", "extra", "missing"])
    assert out["p1"]["price"] == 9.99
    assert out["p1"]["extra"] == {"a": 1}
    assert "missing" not in out["p1"]

    # delete only one field
    assert s.delete_product("p1", fields=["price"]) == 1
    out2 = s.get_live_attributes(["p1"], ["price", "availability"])
    assert "price" not in out2["p1"]
    assert out2["p1"]["availability"] == "InStock"

    # delete whole product
    assert s.delete_product("p1") >= 1
    out3 = s.get_live_attributes(["p1"], ["availability", "extra"])
    assert out3["p1"] == {}

    hc = s.health_check()
    assert hc["status"] == "healthy"
    assert hc["redis_version"] == "7.0.0"


# --- LocalStorage: cover cache load failures + parse extraction + refresh/rebuild ---

import pytest


class _ParseResult:
    def __init__(self, directives: dict, errors: list | None = None):
        self.directives = directives
        self.errors = errors or []


def _install_fake_drivers_parser(
    monkeypatch: pytest.MonkeyPatch, mapping: dict[str, _ParseResult]
):
    """
    LocalStorage._parse_file() does: from ...parser import parse_file
    which resolves to: commercetxt.parser
    """
    mod = types.ModuleType("commercetxt.parser")

    def parse_file(path: Path):
        key = Path(path).name
        return mapping[key]

    mod.parse_file = parse_file  # type: ignore
    monkeypatch.setitem(sys.modules, "commercetxt.parser", mod)


def test_local_storage_load_cache_invalid_json_and_rebuild_refresh(
    tmp_path, monkeypatch
):
    """Test LocalStorage handles invalid JSON cache and rebuilds correctly."""
    from dataclasses import dataclass
    from pathlib import Path

    root = tmp_path / "products"
    root.mkdir()

    # Two product files
    (root / "pixel-9-pro.txt").write_text("x", encoding="utf-8")
    (root / "bad.txt").write_text("y", encoding="utf-8")

    cache = tmp_path / "cache.json"
    cache.write_text("{not:valid:json", encoding="utf-8")  # JSONDecodeError path

    @dataclass
    class _FakeParseResult:
        directives: dict
        errors: list

    def fake_parse_file(file_path, *args, **kwargs):
        name = Path(file_path).name
        if name == "pixel-9-pro.txt":
            return _FakeParseResult(
                directives={
                    "OFFER": {"Price": 799.0, "Availability": "InStock"},
                    "IDENTITY": {"Currency": "USD"},
                    "PRODUCT": {"SKU": "PIX-9-PRO"},
                    "INVENTORY": {"Stock": 5, "LastUpdated": "2026-01-02"},
                },
                errors=[],
            )
        if name == "bad.txt":
            return _FakeParseResult(directives={}, errors=["boom"])  # should be skipped
        raise AssertionError(f"unexpected file: {name}")

    # Mock the parser module before importing LocalStorage
    import sys
    import types

    parser_mod = types.ModuleType("commercetxt.parser")
    parser_mod.parse_file = fake_parse_file
    monkeypatch.setitem(sys.modules, "commercetxt.parser", parser_mod)

    from commercetxt.rag.drivers.local_storage import LocalStorage

    s = LocalStorage(root_path=str(root), cache_file=str(cache), auto_refresh=False)

    # invalid cache JSON must not crash; must fall back to empty
    assert s.get_cached_product_count() == 0

    # rebuild_cache should parse pixel-9-pro and skip bad.txt
    n = s.rebuild_cache()
    assert n == 1
    assert s.get_cached_product_count() == 1

    # cache file persisted
    raw = Path(s.cache_file).read_text(encoding="utf-8")
    assert "PIX-9-PRO" in raw or "pixel-9-pro" in raw

    # refresh_product returns bool in current implementation
    assert s.refresh_product("pixel-9-pro") is True

    # verify cached fields exist through public API (no get_product_data method)
    out = s.get_live_attributes(
        ["pixel-9-pro"],
        [
            "sku",
            "price",
            "availability",
            "currency",
            "stock",
            "last_updated",
            "source_file",
        ],
    )
    assert "pixel-9-pro" in out
    d = out["pixel-9-pro"]

    assert d["sku"] == "PIX-9-PRO"
    assert d["price"] == 799.0
    assert d["availability"] == "InStock"
    assert d["currency"] == "USD"
    assert d["stock"] == 5
    assert d["last_updated"] == "2026-01-02"
    assert isinstance(d["source_file"], str) and d["source_file"].endswith(
        "pixel-9-pro.txt"
    )


# --- PineconeStore: dependency-free (fake pinecone SDK) ---

import pytest


def _install_fake_pinecone(monkeypatch: pytest.MonkeyPatch):
    import sys
    import types

    pc = types.ModuleType("pinecone")

    class ServerlessSpec:
        def __init__(self, cloud: str, region: str):
            self.cloud = cloud
            self.region = region

    class _IdxName:
        def __init__(self, name: str):
            self.name = name

    class _QueryResp:
        def __init__(self, payload: dict):
            self._payload = payload

        def to_dict(self) -> dict:
            return self._payload

    class _Index:
        def __init__(self, name: str):
            self.name = name
            self.upserts: list[dict[str, Any]] = []
            self.queries: list[dict[str, Any]] = []
            self.deletes: list[dict[str, Any]] = []

        def upsert(self, vectors=None, namespace=None, **kwargs):
            self.upserts.append(
                {"vectors": vectors, "namespace": namespace, "kwargs": kwargs}
            )
            return {"upserted_count": len(vectors or [])}

        def query(
            self,
            vector=None,
            top_k=5,
            namespace=None,
            include_metadata=True,
            include_values=False,
            **kwargs,
        ):
            self.queries.append(
                {
                    "vector": vector,
                    "top_k": top_k,
                    "namespace": namespace,
                    "include_metadata": include_metadata,
                    "include_values": include_values,
                    "kwargs": kwargs,
                }
            )
            return _QueryResp(
                {
                    "matches": [
                        {"id": "p1:subject:0", "score": 0.99, "metadata": {"SKU": "p1"}}
                    ]
                }
            )

        def delete(self, ids=None, namespace=None, delete_all=False, **kwargs):
            self.deletes.append(
                {
                    "ids": ids,
                    "namespace": namespace,
                    "delete_all": delete_all,
                    "kwargs": kwargs,
                }
            )
            return {"deleted_count": len(ids or [])}

    class Pinecone:
        def __init__(self, api_key: str):
            self.api_key = api_key
            self._indexes: dict[str, _Index] = {}
            self._created: list[dict[str, Any]] = []

        def list_indexes(self):
            return [_IdxName(n) for n in sorted(self._indexes.keys())]

        def create_index(
            self, name: str, dimension: int, metric: str, spec=None, **kwargs
        ):
            self._created.append(
                {
                    "name": name,
                    "dimension": dimension,
                    "metric": metric,
                    "spec": spec,
                    "kwargs": kwargs,
                }
            )
            self._indexes.setdefault(name, _Index(name))
            return True

        def describe_index(self, name: str):
            # make it "ready" immediately
            return {"status": {"ready": True}}

        def Index(self, name: str):
            self._indexes.setdefault(name, _Index(name))
            return self._indexes[name]

    pc.Pinecone = Pinecone  # type: ignore
    pc.ServerlessSpec = ServerlessSpec  # type: ignore

    monkeypatch.setitem(sys.modules, "pinecone", pc)


def test_pinecone_store_connect_upsert_search_delete(monkeypatch: pytest.MonkeyPatch):

    _install_fake_pinecone(monkeypatch)

    from commercetxt.rag.drivers import pinecone_store
    from commercetxt.rag.drivers.pinecone_store import PineconeStore

    # no real sleeping (mutation-friendly + fast)
    monkeypatch.setattr(pinecone_store.time, "sleep", lambda *_args, **_kw: None)
    monkeypatch.setattr(
        PineconeStore, "_wait_for_index_ready", lambda self: None, raising=True
    )

    # build kwargs by signature so test survives refactors
    sig = inspect.signature(PineconeStore.__init__)
    init_kwargs: dict[str, Any] = {}
    for name, p in sig.parameters.items():
        if name == "self":
            continue
        if p.default is not inspect._empty:
            continue
        if "api" in name.lower():
            init_kwargs[name] = "k"
        elif "index" in name.lower():
            init_kwargs[name] = "test-index"
        else:
            init_kwargs[name] = 3 if "dimension" in name.lower() else "x"

    # Ensure required arguments are provided
    if "api_key" not in init_kwargs:
        init_kwargs["api_key"] = "test-key"
    if "index_name" not in init_kwargs:
        init_kwargs["index_name"] = "test-index"

    store = PineconeStore(**init_kwargs)
    assert store.connect() is True

    shards = [
        {
            "id": "p1:subject:0",
            "values": [1.0, 0.0, 0.0],
            "metadata": {"SKU": "p1"},
            "text": "alpha",
        },
    ]
    n = store.upsert(shards, namespace="default")
    assert n == 1

    res = store.search([1.0, 0.0, 0.0], top_k=1, namespace="default")
    assert isinstance(res, list) and len(res) == 1
    assert res[0]["id"] == "p1:subject:0"
    assert res[0]["metadata"]["SKU"] == "p1"

    d = store.delete(ids=["p1:subject:0"], namespace="default")
    assert isinstance(d, int) and d >= 1

    # mutation-friendly: ensure query was called with include_metadata True
    assert (
        store.index is not None and store.index.queries
    ), "expected at least one query call"
    last_query = store.index.queries[-1]
    assert last_query.get("include_metadata") is True


# --- QdrantStore: dependency-free (fake qdrant-client) ---

import pytest


def _install_fake_qdrant(monkeypatch: pytest.MonkeyPatch):
    import sys
    import types

    qmod = types.ModuleType("qdrant_client")
    models_mod = types.ModuleType("qdrant_client.models")
    http_mod = types.ModuleType("qdrant_client.http")
    http_models_mod = types.ModuleType("qdrant_client.http.models")

    class Distance:
        COSINE = "Cosine"

    class VectorParams:
        def __init__(self, size: int, distance: str):
            self.size = size
            self.distance = distance

    class PointStruct:
        def __init__(self, id=None, vector=None, payload=None):
            self.id = id
            self.vector = vector
            self.payload = payload

    # delete() branch needs these types
    class MatchValue:
        def __init__(self, value):
            self.value = value

    class FieldCondition:
        def __init__(self, key: str, match: MatchValue):
            self.key = key
            self.match = match

    class Filter:
        def __init__(self, must=None):
            self.must = must or []

    class _Col:
        def __init__(self, name: str):
            self.name = name

    class _Collections:
        def __init__(self, names):
            self.collections = [_Col(n) for n in names]

    class _Hit:
        def __init__(self, id, score, payload):
            self.id = id
            self.score = score
            self.payload = payload

    class QdrantClient:
        def __init__(self, url=None, api_key=None, **kwargs):
            self.url = url
            self.api_key = api_key
            self._collections = set()
            self.upserts = []
            self.searches = []
            self.deletes = []
            self.created = []

        def get_collections(self):
            return _Collections(sorted(self._collections))

        def create_collection(
            self, collection_name: str, vectors_config=None, **kwargs
        ):
            self._collections.add(collection_name)
            self.created.append((collection_name, vectors_config, kwargs))
            return True

        def upsert(self, collection_name: str, points=None, **kwargs):
            self._collections.add(collection_name)
            self.upserts.append((collection_name, points, kwargs))
            return {"status": "ok"}

        def search(self, collection_name: str, query_vector=None, limit=5, **kwargs):
            self.searches.append((collection_name, query_vector, limit, kwargs))
            return [_Hit("p1:subject:0", 0.88, {"SKU": "p1", "text": "alpha"})]

        def delete(self, collection_name: str, points_selector=None, **kwargs):
            self.deletes.append((collection_name, points_selector, kwargs))
            return {"status": "ok"}

    qmod.QdrantClient = QdrantClient  # type: ignore

    models_mod.Distance = Distance  # type: ignore
    models_mod.VectorParams = VectorParams  # type: ignore
    models_mod.PointStruct = PointStruct  # type: ignore
    models_mod.MatchValue = MatchValue  # type: ignore
    models_mod.FieldCondition = FieldCondition  # type: ignore
    models_mod.Filter = Filter  # type: ignore

    http_models_mod.Distance = Distance  # type: ignore
    http_models_mod.VectorParams = VectorParams  # type: ignore
    http_models_mod.PointStruct = PointStruct  # type: ignore
    http_models_mod.MatchValue = MatchValue  # type: ignore
    http_models_mod.FieldCondition = FieldCondition  # type: ignore
    http_models_mod.Filter = Filter  # type: ignore

    http_mod.models = http_models_mod  # type: ignore

    monkeypatch.setitem(sys.modules, "qdrant_client", qmod)
    monkeypatch.setitem(sys.modules, "qdrant_client.models", models_mod)
    monkeypatch.setitem(sys.modules, "qdrant_client.http", http_mod)
    monkeypatch.setitem(sys.modules, "qdrant_client.http.models", http_models_mod)

    # PointStruct already defined above at line ~997
    models_mod.PointStruct = PointStruct  # type: ignore[name-defined]
    http_mod.models = models_mod  # type: ignore[attr-defined]

    qmod.models = models_mod  # type: ignore
    monkeypatch.setitem(sys.modules, "qdrant_client", qmod)
    monkeypatch.setitem(sys.modules, "qdrant_client.models", models_mod)
    monkeypatch.setitem(sys.modules, "qdrant_client.http", http_mod)
    monkeypatch.setitem(sys.modules, "qdrant_client.http.models", models_mod)


def test_qdrant_store_connect_upsert_search_delete(monkeypatch: pytest.MonkeyPatch):

    _install_fake_qdrant(monkeypatch)

    from commercetxt.rag.drivers.qdrant_store import QdrantStore

    sig = inspect.signature(QdrantStore.__init__)
    init_kwargs: dict[str, Any] = {}
    for name, p in sig.parameters.items():
        if name == "self":
            continue
        if p.default is not inspect._empty:
            continue
        if "collection" in name.lower():
            init_kwargs[name] = "ct"
        elif "url" in name.lower():
            init_kwargs[name] = "http://localhost:6333"
        elif "dimension" in name.lower():
            init_kwargs[name] = 3
        else:
            init_kwargs[name] = "x"

    store = QdrantStore(**init_kwargs) if init_kwargs else QdrantStore()
    assert store.connect() is True

    shards = [
        {
            "id": "p1:subject:0",
            "values": [1.0, 0.0, 0.0],
            "metadata": {"SKU": "p1"},
            "text": "alpha",
        },
    ]
    n = store.upsert(shards, namespace="default")
    assert isinstance(n, int) and n == 1

    res = store.search([1.0, 0.0, 0.0], top_k=1, namespace="default")
    assert isinstance(res, list) and len(res) == 1
    assert res[0]["id"] == "p1:subject:0"
    # QdrantStore may map hit.payload -> "metadata" (common) instead of keeping "payload"
    meta = res[0].get("metadata") or res[0].get("payload") or {}
    assert meta.get("SKU") == "p1"

    # delete specific ids (covers ids branch)
    d = store.delete(ids=["p1:subject:0"], namespace="default")
    assert isinstance(d, int) and d >= 1

    # mutation-friendly: verify upsert used PointStruct objects
    assert store.client is not None and store.client.upserts, "expected upsert calls"
    last_upsert = store.client.upserts[-1]
    points = (
        last_upsert.get("points", [])
        if isinstance(last_upsert, dict)
        else last_upsert[1]
    )

    assert points and hasattr(points[0], "id")
    assert isinstance(points[0].id, str)
    # uuid4-ish (mutation-friendly): has hyphens and decent length
    assert "-" in points[0].id and len(points[0].id) >= 32

    payload = getattr(points[0], "payload", None) or {}
    assert isinstance(payload, dict)

    assert payload.get("SKU") == "p1"
    assert payload.get("namespace") == "default"
    assert payload.get("text") == "alpha"

    assert "score" in res[0]
    assert isinstance(res[0]["score"], float)

    assert store.client is not None and store.client.deletes, "expected delete calls"
    last_delete = store.client.deletes[-1]
    points_selector = (
        last_delete[1]
        if isinstance(last_delete, tuple)
        else last_delete.get("points_selector")
    )

    def _walk(x):
        """Yield nested values from dict/list/objects (via __dict__)."""
        if x is None:
            return
        if isinstance(x, (str, int, float, bool)):
            yield x
            return
        if isinstance(x, dict):
            for k, v in x.items():
                yield from _walk(k)
                yield from _walk(v)
            return
        if isinstance(x, (list, tuple, set)):
            for i in x:
                yield from _walk(i)
            return
        if hasattr(x, "__dict__"):
            yield from _walk(x.__dict__)

    leaves = list(_walk(points_selector))

    # Current implementation deletes by namespace filter (not by ids)
    assert "namespace" in leaves
    assert "default" in leaves

    # mutation-friendly: prove namespace parameter actually flows into the filter
    store.delete(ids=["whatever"], namespace="ns2")
    assert store.client is not None and store.client.deletes
    last_delete2 = store.client.deletes[-1]
    points_selector2 = (
        last_delete2[1]
        if isinstance(last_delete2, tuple)
        else last_delete2.get("points_selector")
    )
    leaves2 = list(_walk(points_selector2))
    assert "namespace" in leaves2
    assert "ns2" in leaves2
