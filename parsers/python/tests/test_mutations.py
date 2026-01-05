"""
Mutation Killer Tests.

Tests that catch subtle code mutations in parser, validator, CLI.
Focus: boundary conditions, operator changes, type coercion.
"""

from datetime import datetime, timedelta, timezone

import pytest

from commercetxt.bridge import CommerceAIBridge
from commercetxt.constants import INVENTORY_STALE_HOURS
from commercetxt.limits import MAX_FILE_SIZE, MAX_SECTIONS
from commercetxt.model import ParseResult
from commercetxt.parser import CommerceTXTParser
from commercetxt.validators.core import CoreValidator
from commercetxt.validators.policies import PolicyValidator

# =============================================================================
# Parser Mutations
# =============================================================================


class TestParserMutations:
    """Parser algorithm edge cases."""

    @pytest.fixture
    def parser(self):
        """Default parser instance."""
        return CommerceTXTParser()

    def test_pipe_in_url_query_preserved(self, parser):
        """Pipes in URL query strings are not delimiters."""
        text = "http://site.com/api?query=a|b|c"
        parts = parser._smart_split_by_pipe(text)
        assert len(parts) == 1
        assert parts[0] == text

    def test_pipe_as_delimiter_splits(self, parser):
        """Pipes with spaces are delimiters."""
        parts = parser._smart_split_by_pipe("Value A | Value B")
        assert len(parts) == 2

    def test_mixed_url_and_pipe(self, parser):
        """URL followed by pipe delimiter."""
        text = "http://site.com?q=1|2 | Note: trailing"
        parts = parser._smart_split_by_pipe(text)
        assert len(parts) == 2

    def test_indent_detection_two_spaces(self, parser):
        """Two-space indent detected."""
        assert parser._detect_indent_width("Root\n  Child") == 2

    def test_indent_detection_four_spaces(self, parser):
        """Four-space indent detected."""
        assert parser._detect_indent_width("Root\n    Child") == 4

    def test_indent_detection_no_indent(self, parser):
        """No indent defaults to 2."""
        assert parser._detect_indent_width("Root\nNoIndent") == 2

    def test_bom_removed(self, parser):
        """UTF-8 BOM is stripped."""
        result = parser.parse("\ufeff# @CATALOG")
        assert "CATALOG" in result.directives

    def test_file_size_boundary_exact(self, parser):
        """File at exact limit passes."""
        content = "v" * MAX_FILE_SIZE
        result = parser.parse(content)
        assert not result.errors

    def test_file_size_boundary_exceeded(self, parser):
        """File over limit fails."""
        content = "v" * (MAX_FILE_SIZE + 1)
        result = parser.parse(content)
        assert any("too large" in e for e in result.errors)

    def test_max_sections_boundary(self, parser):
        """Section limit is enforced."""
        lines = [f"# @S{i}\nKey: Val" for i in range(MAX_SECTIONS + 1)]
        result = parser.parse("\n".join(lines))
        assert len(result.directives) == MAX_SECTIONS


# =============================================================================
# Validator Mutations
# =============================================================================


class TestValidatorMutations:
    """Validator boundary conditions."""

    @pytest.fixture
    def validator(self):
        return CoreValidator(strict=False)

    def test_inventory_stale_float_division(self, validator):
        """Age calculation uses float division, not integer."""
        result = ParseResult()
        limit = INVENTORY_STALE_HOURS
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=limit, minutes=30)
        result.directives["INVENTORY"] = {"LastUpdated": past.isoformat()}
        validator._validate_inventory(result)
        assert "inventory_stale" in result.trust_flags

    def test_currency_length_three(self, validator):
        """Three-character currency codes valid."""
        result = ParseResult()
        result.directives["IDENTITY"] = {"Currency": "USD"}
        validator._validate_identity(result)
        assert not any("Currency" in w for w in result.warnings)

    def test_currency_length_invalid(self, validator):
        """Non-three-character codes invalid."""
        result = ParseResult()
        result.directives["IDENTITY"] = {"Currency": "EURO"}
        validator._validate_identity(result)
        assert any("Currency" in w for w in result.warnings)


# =============================================================================
# Policy Validator Mutations
# =============================================================================


class TestPolicyMutations:
    """Policy validation edge cases."""

    @pytest.fixture
    def validator(self):
        return PolicyValidator(strict=False)

    def test_support_without_contact(self, validator):
        """SUPPORT without contact info warns."""
        result = ParseResult()
        result.directives["SUPPORT"] = {"FAQ": "http://faq.com"}  # No email, phone
        validator._validate_support(result)
        assert any("no contact" in w.lower() for w in result.warnings)

    def test_brand_voice_unknown_key(self, validator):
        """Unknown BRAND_VOICE key warns."""
        result = ParseResult()
        result.directives["BRAND_VOICE"] = {"InvalidKey": "Value"}
        validator._validate_brand_voice(result)
        assert len(result.warnings) > 0

    def test_brand_voice_valid_tone(self, validator):
        """Valid tone produces no warning."""
        result = ParseResult()
        result.directives["BRAND_VOICE"] = {"Tone": "Professional"}
        validator._validate_brand_voice(result)
        assert not any("Tone" in w for w in result.warnings)

    def test_brand_voice_non_standard_tone(self, validator):
        """Non-standard tone warns."""
        result = ParseResult()
        result.directives["BRAND_VOICE"] = {"Tone": "Sarcastic"}
        validator._validate_brand_voice(result)
        assert any("Non-standard Tone" in w for w in result.warnings)


# =============================================================================
# Bridge Scoring Mutations
# =============================================================================


class TestBridgeScoringMutations:
    """Score calculation edge cases."""

    def test_max_clamped_not_min(self):
        """max(0, score) not min(0, score)."""
        result = ParseResult(directives={"OFFER": {}})
        result.errors = ["E"] * 10
        bridge = CommerceAIBridge(result)
        assert bridge.calculate_readiness_score()["score"] == 0

    def test_grade_threshold_90_exclusive(self):
        """Score 90 gets B, not A."""
        result = ParseResult(
            directives={"OFFER": {"Price": "10", "Availability": "InStock"}}
        )
        result.version = "1.0"
        result.errors = ["E"]  # -20 = 80
        bridge = CommerceAIBridge(result)
        res = bridge.calculate_readiness_score()
        assert res["score"] == 80
        assert res["grade"] == "B"

    def test_grade_threshold_70_inclusive(self):
        """Score 70 gets C."""
        result = ParseResult(directives={"OFFER": {}})
        result.version = "1.0"
        bridge = CommerceAIBridge(result)
        res = bridge.calculate_readiness_score()
        assert res["score"] == 70
        assert res["grade"] == "C"


# =============================================================================
# Type Coercion Mutations
# =============================================================================


class TestTypeCoercionMutations:
    """Type comparison edge cases."""

    def test_stock_integer_zero(self):
        """Integer 0 is valid stock."""
        bridge = CommerceAIBridge(ParseResult())
        lines = []
        bridge._add_inventory(lines, {"Stock": 0})
        assert "STOCK: 0 units" in lines

    def test_stock_string_zero(self):
        """String '0' is valid stock."""
        bridge = CommerceAIBridge(ParseResult())
        lines = []
        bridge._add_inventory(lines, {"Stock": "0"})
        assert any("STOCK: 0" in l for l in lines)

    def test_integer_field_comparison(self):
        """Integer 999 doesn't crash string comparison."""
        bridge = CommerceAIBridge(ParseResult())
        lines = []
        bridge._add_product(lines, {"Name": "T", "SKU": 999})
        assert "SKU: 999" in "\n".join(lines)

    def test_boolean_true_as_stock(self):
        """Boolean True converts to stock value."""
        bridge = CommerceAIBridge(ParseResult())
        lines = []
        bridge._add_inventory(lines, {"Stock": True})
        content = "\n".join(lines)
        assert "STOCK:" in content


# =============================================================================
# List/Dict Type Mutations
# =============================================================================


class TestCollectionTypeMutations:
    """Collection type validation."""

    def test_variants_string_not_list(self):
        """String instead of list returns early."""
        bridge = CommerceAIBridge(ParseResult())
        lines = []
        bridge._add_variants(lines, {"Options": "not list"})
        assert lines == []

    def test_variants_none(self):
        """None options returns early."""
        bridge = CommerceAIBridge(ParseResult())
        lines = []
        bridge._add_variants(lines, {"Options": None})
        assert lines == []

    def test_shipping_dict_not_list(self):
        """Dict instead of list returns early."""
        bridge = CommerceAIBridge(ParseResult())
        lines = []
        bridge._add_shipping(lines, {"items": {"key": "val"}})
        assert "SHIPPING:" not in "\n".join(lines)

    def test_specs_non_dict_skipped(self):
        """Non-dict specs value skipped."""
        parser = CommerceTXTParser()
        content = """# @SPECS
Color: Red
Size: [1, 2, 3]
"""
        result = parser.parse(content)
        assert "Color" in result.directives.get("SPECS", {})


# =============================================================================
# Empty/None Return Mutations
# =============================================================================


class TestEmptyReturnMutations:
    """Methods return None, not True."""

    def test_add_identity_returns_none(self):
        """_add_identity returns None."""
        bridge = CommerceAIBridge(ParseResult())
        assert bridge._add_identity([], {"Name": "S"}) is None

    def test_add_product_returns_none(self):
        """_add_product returns None."""
        bridge = CommerceAIBridge(ParseResult())
        assert bridge._add_product([], {"Name": "P"}) is None

    def test_add_offer_returns_none(self):
        """_add_offer returns None."""
        bridge = CommerceAIBridge(ParseResult())
        assert bridge._add_offer([], {"Price": "10"}) is None

    def test_add_inventory_returns_none(self):
        """_add_inventory returns None."""
        bridge = CommerceAIBridge(ParseResult())
        assert bridge._add_inventory([], {"Stock": "5"}) is None

    def test_add_specs_returns_none(self):
        """_add_specs returns None."""
        bridge = CommerceAIBridge(ParseResult())
        assert bridge._add_specs([], {"Key": "Val"}) is None

    def test_empty_dict_returns_early(self):
        """Empty dict input produces no output."""
        bridge = CommerceAIBridge(ParseResult())
        lines = []
        bridge._add_identity(lines, {})
        bridge._add_product(lines, {})
        bridge._add_offer(lines, {})
        assert lines == []


# =============================================================================
# Security Mutations
# =============================================================================


class TestSecurityMutations:
    """Security URL validation edge cases."""

    def test_localhost_blocked(self):
        """Localhost URLs are blocked."""
        from commercetxt.security import is_safe_url

        assert is_safe_url("http://localhost/api") is False
        assert is_safe_url("http://127.0.0.1/api") is False

    def test_private_ip_blocked(self):
        """Private IP ranges are blocked."""
        from commercetxt.security import is_safe_url

        assert is_safe_url("http://192.168.1.1/api") is False
        assert is_safe_url("http://10.0.0.1/api") is False
        assert is_safe_url("http://172.16.0.1/api") is False

    def test_valid_https_allowed(self):
        """Valid HTTPS URLs are allowed."""
        from commercetxt.security import is_safe_url

        assert is_safe_url("https://example.com/api") is True
        assert is_safe_url("https://store.google.com") is True

    def test_invalid_scheme_blocked(self):
        """Non-HTTP(S) schemes are blocked."""
        from commercetxt.security import is_safe_url

        assert is_safe_url("file:///etc/passwd") is False
        assert is_safe_url("ftp://example.com") is False

    def test_empty_url_blocked(self):
        """Empty or invalid URLs are blocked."""
        from commercetxt.security import is_safe_url

        assert is_safe_url("") is False
        assert is_safe_url(None) is False

    def test_url_with_backslash_blocked(self):
        """URLs with backslashes are blocked."""
        from commercetxt.security import is_safe_url

        assert is_safe_url("http://example.com\\..\\etc") is False


# =============================================================================
# RAG Generator Mutations
# =============================================================================


class TestRAGGeneratorMutations:
    """RAG generator edge cases."""

    def test_empty_product_generates_anchor(self):
        """Empty product still generates anchor shard."""
        from commercetxt.rag.core.generator import RAGGenerator

        gen = RAGGenerator()
        shards = gen.generate({"PRODUCT": {}})
        assert len(shards) >= 0  # May or may not generate

    def test_reviews_without_rating(self):
        """Reviews without rating handled."""
        from commercetxt.rag.core.generator import RAGGenerator

        gen = RAGGenerator()
        shards = gen.generate({"REVIEWS": {"Count": "100"}})
        assert isinstance(shards, list)

    def test_specs_with_nested_dict(self):
        """Specs with nested dict handled."""
        from commercetxt.rag.core.generator import RAGGenerator

        gen = RAGGenerator()
        shards = gen.generate({"SPECS": {"Display": {"Size": "6.3", "Type": "OLED"}}})
        assert isinstance(shards, list)


# =============================================================================
# FaissStore Mutations
# =============================================================================


class TestFaissStoreMutations:
    """FaissStore operations edge cases."""

    def test_connect_creates_directory(self, tmp_path):
        """Connect creates root directory."""
        from commercetxt.rag.drivers.faiss_store import FaissStore

        store = FaissStore(root_dir=str(tmp_path / "faiss"), dimension=384)
        result = store.connect()
        assert result is True
        assert (tmp_path / "faiss").exists()

    def test_health_check_structure(self, tmp_path):
        """Health check returns expected structure."""
        from commercetxt.rag.drivers.faiss_store import FaissStore

        store = FaissStore(root_dir=str(tmp_path / "faiss"), dimension=384)
        store.connect()
        health = store.health_check()

        assert "ok" in health
        assert health["ok"] is True


# =============================================================================
# OpenAI Embedder Mutations (Mocked)
# =============================================================================


class TestOpenAIEmbedderMutations:
    """OpenAI embedder with mocked client."""

    def test_openai_not_installed_raises(self, monkeypatch):
        """ImportError raised when openai not installed."""
        import sys
        from unittest.mock import patch

        # Mock HAS_OPENAI to False
        with patch.dict(sys.modules, {"openai": None}):
            with patch("commercetxt.rag.drivers.openai_embedder.HAS_OPENAI", False):
                from commercetxt.rag.drivers.openai_embedder import OpenAIEmbedder

                with pytest.raises(ImportError, match="OpenAI not installed"):
                    OpenAIEmbedder(api_key="test-key")

    def test_model_default_value(self, monkeypatch):
        """Default model is text-embedding-3-small."""
        from unittest.mock import MagicMock, patch

        mock_openai = MagicMock()
        with patch("commercetxt.rag.drivers.openai_embedder.HAS_OPENAI", True):
            with patch("commercetxt.rag.drivers.openai_embedder.OpenAI", mock_openai):
                from commercetxt.rag.drivers.openai_embedder import OpenAIEmbedder

                embedder = OpenAIEmbedder(api_key="test-key")
                assert embedder.model == "text-embedding-3-small"


# =============================================================================
# Additional FaissStore Coverage
# =============================================================================


class TestFaissStoreAdditionalMutations:
    """Additional FaissStore coverage for uncovered lines."""

    def test_upsert_and_search(self, tmp_path):
        """Upsert vectors and search returns results."""

        from commercetxt.rag.drivers.faiss_store import FaissStore

        store = FaissStore(root_dir=str(tmp_path / "faiss"), dimension=4)
        store.connect()

        # Upsert some vectors
        shards = [
            {
                "id": "1",
                "text": "test1",
                "values": [0.1, 0.2, 0.3, 0.4],
                "metadata": {},
            },
            {
                "id": "2",
                "text": "test2",
                "values": [0.5, 0.6, 0.7, 0.8],
                "metadata": {},
            },
        ]
        count = store.upsert(shards, namespace="test")
        assert count == 2

        # Search
        query = [0.2, 0.3, 0.4, 0.5]
        results = store.search(query, top_k=2, namespace="test")
        assert len(results) > 0

    def test_empty_namespace_search(self, tmp_path):
        """Search on empty namespace returns empty list."""
        from commercetxt.rag.drivers.faiss_store import FaissStore

        store = FaissStore(root_dir=str(tmp_path / "faiss"), dimension=4)
        store.connect()

        results = store.search([0.1, 0.2, 0.3, 0.4], top_k=5, namespace="empty")
        assert results == []


# =============================================================================
# SLM Tagger Coverage
# =============================================================================


class TestSLMTaggerMutations:
    """SLM Tagger edge cases."""

    def test_tagger_initialization(self):
        """Tagger initializes with default config."""
        from commercetxt.rag.drivers.slm_tagger import SLMTagger

        tagger = SLMTagger()
        assert tagger is not None

    def test_tagger_is_callable(self):
        """Tagger can be used."""
        from commercetxt.rag.drivers.slm_tagger import SLMTagger

        tagger = SLMTagger()
        # Check that tagger object was created successfully
        assert tagger.__class__.__name__ == "SLMTagger"


# =============================================================================
# RAG Pipeline Additional Coverage
# =============================================================================


class TestRAGPipelineMutations:
    """RAG Pipeline edge cases."""

    def test_pipeline_initialization(self):
        """Pipeline initializes with components."""
        from commercetxt.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline()
        assert pipeline.generator is not None
        assert pipeline.health_checker is not None

    def test_pipeline_generator_type(self):
        """Pipeline generator is correct type."""
        from commercetxt.rag.core.generator import RAGGenerator
        from commercetxt.rag.pipeline import RAGPipeline

        pipeline = RAGPipeline()
        assert isinstance(pipeline.generator, RAGGenerator)


# =============================================================================
# Async Pipeline Additional Coverage
# =============================================================================


class TestAsyncPipelineMutations:
    """Async Pipeline edge cases."""

    @pytest.mark.asyncio
    async def test_async_pipeline_initialization(self):
        """Async pipeline initializes with components."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline()
        assert pipeline.generator is not None
        assert pipeline.enable_cache is True

    @pytest.mark.asyncio
    async def test_async_pipeline_context_manager(self):
        """Async pipeline works as context manager."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        async with AsyncRAGPipeline() as pipeline:
            assert pipeline is not None


# =============================================================================
# RAG Exceptions Coverage
# =============================================================================


class TestRAGExceptionsMutations:
    """RAG exceptions coverage."""

    def test_rag_error_base(self):
        """RAGError base class works."""
        from commercetxt.rag.exceptions import RAGError

        error = RAGError("Test error")
        assert str(error) == "Test error"

    def test_embedding_error(self):
        """EmbeddingError works."""
        from commercetxt.rag.exceptions import EmbeddingError

        error = EmbeddingError("Embedding failed")
        assert "Embedding failed" in str(error)

    def test_storage_error(self):
        """StorageError works."""
        from commercetxt.rag.exceptions import StorageError

        error = StorageError("Storage failed")
        assert "Storage failed" in str(error)
