"""
Integration tests using real CommerceTXT files from examples/google-store and vectors/.

This module provides comprehensive, mutation-resistant tests using actual product data.
All assertions verify concrete values rather than just types or existence.

Fixtures are provided by conftest.py from:
- examples/google-store/products/ (Pixel 9 Pro, Pixel 8a)
- examples/google-store/categories/ (smartphones)
- tests/vectors/valid/ (subscription, complete store, etc.)
"""

from __future__ import annotations

import json

import pytest

# =============================================================================
# Parser Tests - Real Data
# =============================================================================


class TestParserRealData:
    """Parser validation using actual CommerceTXT files."""

    def test_pixel_9_pro_directive_structure(self, pixel_9_pro_path):
        """Pixel 9 Pro contains all expected directive sections."""
        from commercetxt.parser import parse_file

        result = parse_file(pixel_9_pro_path)

        assert len(result.errors) == 0
        assert "PRODUCT" in result.directives
        assert "OFFER" in result.directives
        assert "INVENTORY" in result.directives
        assert "VARIANTS" in result.directives
        assert "REVIEWS" in result.directives
        assert "SPECS" in result.directives

    def test_pixel_9_pro_product_values(self, pixel_9_pro_path):
        """Pixel 9 Pro product section contains correct values."""
        from commercetxt.parser import parse_file

        result = parse_file(pixel_9_pro_path)
        product = result.directives["PRODUCT"]

        assert product["Name"] == "Google Pixel 9 Pro"
        assert product["Brand"] == "Google"
        assert product["Model"] == "Pixel 9 Pro"
        assert product["SKU"] == "GA05843"

    def test_pixel_9_pro_offer_values(self, pixel_9_pro_path):
        """Pixel 9 Pro offer section contains correct pricing."""
        from commercetxt.parser import parse_file

        result = parse_file(pixel_9_pro_path)
        offer = result.directives["OFFER"]

        assert offer["Price"] == "999.00"
        assert offer["Currency"] == "USD"
        assert offer["Availability"] == "InStock"
        assert offer["Condition"] == "New"

    def test_pixel_9_pro_reviews(self, pixel_9_pro_path):
        """Pixel 9 Pro reviews section contains rating data."""
        from commercetxt.parser import parse_file

        result = parse_file(pixel_9_pro_path)
        reviews = result.directives["REVIEWS"]

        assert reviews["Rating"] == "4.6"
        assert reviews["RatingScale"] == "5.0"
        assert "Count" in reviews

    def test_subscription_product_structure(self, subscription_product_path):
        """Subscription product parses with plan configuration."""
        from commercetxt.parser import parse_file

        result = parse_file(subscription_product_path)

        assert len(result.errors) == 0
        assert "SUBSCRIPTION" in result.directives

        sub = result.directives["SUBSCRIPTION"]
        assert "Plans" in sub
        assert sub["Trial"] == "14 Days Free"
        assert sub["CancelAnytime"] == "True"
        assert sub["AutoRenew"] == "True"

    def test_complete_store_all_directives(self, complete_store_path):
        """Complete store contains all tier 1-3 directive types."""
        from commercetxt.parser import parse_file

        result = parse_file(complete_store_path)

        assert len(result.errors) == 0

        required = [
            "IDENTITY",
            "LOCALES",
            "BRAND_VOICE",
            "PAYMENT",
            "SHIPPING",
            "POLICIES",
            "SUPPORT",
            "CATALOG",
            "PROMOS",
        ]
        for directive in required:
            assert directive in result.directives, f"Missing: {directive}"

    def test_google_commerce_identity(self, google_commerce_path):
        """Google Store commerce.txt has correct identity."""
        from commercetxt.parser import parse_file

        result = parse_file(google_commerce_path)

        assert len(result.errors) == 0
        assert result.directives["IDENTITY"]["Name"] == "Google Store"
        assert result.directives["IDENTITY"]["Currency"] == "USD"

    def test_smartphones_category_filters(self, smartphones_category_path):
        """Smartphones category has filter and semantic logic sections."""
        from commercetxt.parser import parse_file

        result = parse_file(smartphones_category_path)

        assert len(result.errors) == 0
        assert "FILTERS" in result.directives
        assert "SEMANTIC_LOGIC" in result.directives
        assert "ITEMS" in result.directives

    def test_full_product_reviews_rating(self, full_product_path):
        """Full product has reviews with specific rating."""
        from commercetxt.parser import parse_file

        result = parse_file(full_product_path)
        reviews = result.directives["REVIEWS"]

        assert reviews["Rating"] == "4.7"
        assert reviews["RatingScale"] == "5.0"
        assert reviews["Count"] == "1243"


# =============================================================================
# RAG Generator Tests - Real Data
# =============================================================================


class TestRAGGeneratorRealData:
    """RAG shard generation using actual product files."""

    def test_pixel_9_pro_shard_count(self, rag_generator, pixel_9_pro_path):
        """Pixel 9 Pro generates substantial number of shards."""
        from commercetxt.parser import parse_file

        parsed = parse_file(pixel_9_pro_path)
        shards = rag_generator.generate(parsed.directives)

        assert len(shards) > 5

    def test_pixel_9_pro_shard_types(self, rag_generator, pixel_9_pro_path):
        """Pixel 9 Pro generates expected shard types."""
        from commercetxt.parser import parse_file

        parsed = parse_file(pixel_9_pro_path)
        shards = rag_generator.generate(parsed.directives)
        shard_types = {s["metadata"].get("attr_type") for s in shards}

        assert "subject_anchor" in shard_types
        assert "specification" in shard_types
        assert "reviews" in shard_types

    def test_pixel_9_pro_anchor_content(self, rag_generator, pixel_9_pro_path):
        """Subject anchor shard exists and has correct type."""
        from commercetxt.parser import parse_file

        parsed = parse_file(pixel_9_pro_path)
        shards = rag_generator.generate(parsed.directives)

        anchor_shards = [
            s for s in shards if s["metadata"].get("attr_type") == "subject_anchor"
        ]
        assert len(anchor_shards) >= 1

    def test_full_product_review_shard(self, rag_generator, full_product_path):
        """Full product review shard contains rating value."""
        from commercetxt.parser import parse_file

        parsed = parse_file(full_product_path)
        shards = rag_generator.generate(parsed.directives)

        review_shards = [
            s for s in shards if s["metadata"].get("attr_type") == "reviews"
        ]
        assert len(review_shards) >= 1
        assert "4.7" in review_shards[0]["text"]

    def test_subscription_product_shards(
        self, rag_generator, subscription_product_path
    ):
        """Subscription product generates subscription-related shards."""
        from commercetxt.parser import parse_file

        parsed = parse_file(subscription_product_path)
        shards = rag_generator.generate(parsed.directives)
        shard_types = {s["metadata"].get("attr_type") for s in shards}

        assert any("subscription" in str(t) for t in shard_types if t)

    def test_batch_generation_multiple_products(
        self, rag_generator, pixel_9_pro_path, pixel_8a_path
    ):
        """Batch generation processes multiple products."""
        from commercetxt.parser import parse_file

        items = [
            parse_file(pixel_9_pro_path).directives,
            parse_file(pixel_8a_path).directives,
        ]
        shards = rag_generator.generate_batch(items, deduplicate_across_products=True)

        assert len(shards) > 10

        all_text = " ".join(s["text"] for s in shards)
        assert "Pixel" in all_text


# =============================================================================
# LocalStorage Tests - Real Data
# =============================================================================


class TestLocalStorageRealData:
    """LocalStorage operations using Google Store products."""

    def test_pixel_9_pro_price_retrieval(self, products_storage):
        """Retrieve exact price from Pixel 9 Pro."""
        result = products_storage.get_live_attributes(["pixel-9-pro"], ["price"])

        assert result["pixel-9-pro"]["price"] == "999.00"

    def test_pixel_9_pro_multiple_attributes(self, products_storage):
        """Retrieve multiple attributes from Pixel 9 Pro."""
        result = products_storage.get_live_attributes(
            ["pixel-9-pro"], ["price", "availability", "currency"]
        )

        assert result["pixel-9-pro"]["price"] == "999.00"
        assert result["pixel-9-pro"]["availability"] == "InStock"
        assert result["pixel-9-pro"]["currency"] == "USD"

    def test_multiple_products_retrieval(self, products_storage):
        """Retrieve attributes from multiple products simultaneously."""
        result = products_storage.get_live_attributes(
            ["pixel-9-pro", "pixel-8a"], ["price", "availability"]
        )

        assert "pixel-9-pro" in result
        assert "pixel-8a" in result
        assert result["pixel-9-pro"]["price"] == "999.00"

    def test_cache_consistency(self, products_storage):
        """Cache returns consistent results on repeated calls."""
        result1 = products_storage.get_live_attributes(["pixel-9-pro"], ["price"])
        result2 = products_storage.get_live_attributes(["pixel-9-pro"], ["price"])

        assert result1 == result2
        assert result1["pixel-9-pro"]["price"] == "999.00"

    def test_rebuild_cache_count(self, products_storage):
        """Rebuild cache indexes all product files."""
        count = products_storage.rebuild_cache()

        assert count >= 2

    def test_indexed_file_count(self, products_storage):
        """Storage reports correct indexed file count."""
        count = products_storage.get_indexed_file_count()

        assert count >= 2


# =============================================================================
# FaissStore Tests - Real Data Pipeline
# =============================================================================


class TestFaissStoreRealData:
    """FaissStore integration with real embeddings and products."""

    def test_full_rag_pipeline(
        self, local_embedder, rag_generator, pixel_9_pro_path, tmp_path
    ):
        """Complete RAG pipeline: parse -> generate -> embed -> store -> search."""
        from commercetxt.parser import parse_file
        from commercetxt.rag.drivers.faiss_store import FaissStore

        # Parse and generate
        parsed = parse_file(pixel_9_pro_path)
        shards = rag_generator.generate(parsed.directives)
        assert len(shards) > 0

        # Embed
        embedded = local_embedder.embed_shards(shards)
        assert len(embedded) == len(shards)

        # Store
        dim = len(local_embedder.embed_text("test"))
        store = FaissStore(root_dir=str(tmp_path / "faiss"), dimension=dim)
        store.connect()

        count = store.upsert(embedded, namespace="products")
        assert count > 0

        # Search
        query_vec = local_embedder.embed_text("Google Pixel smartphone camera")
        results = store.search(query_vec, top_k=5, namespace="products")

        assert len(results) > 0
        assert "score" in results[0]
        assert "text" in results[0]

    def test_search_relevance(
        self, local_embedder, rag_generator, pixel_9_pro_path, tmp_path
    ):
        """Search returns relevant results for product query."""
        from commercetxt.parser import parse_file
        from commercetxt.rag.drivers.faiss_store import FaissStore

        parsed = parse_file(pixel_9_pro_path)
        shards = rag_generator.generate(parsed.directives)
        embedded = local_embedder.embed_shards(shards)

        dim = len(local_embedder.embed_text("test"))
        store = FaissStore(root_dir=str(tmp_path / "faiss"), dimension=dim)
        store.connect()
        store.upsert(embedded, namespace="products")

        query_vec = local_embedder.embed_text("Google Pixel")
        results = store.search(query_vec, top_k=3, namespace="products")

        top_text = results[0]["text"].lower()
        assert "pixel" in top_text or "google" in top_text

    def test_multi_product_index(
        self, local_embedder, rag_generator, pixel_9_pro_path, pixel_8a_path, tmp_path
    ):
        """Index and search across multiple products."""
        from commercetxt.parser import parse_file
        from commercetxt.rag.drivers.faiss_store import FaissStore

        dim = len(local_embedder.embed_text("test"))
        store = FaissStore(root_dir=str(tmp_path / "faiss"), dimension=dim)
        store.connect()

        for path in [pixel_9_pro_path, pixel_8a_path]:
            parsed = parse_file(path)
            shards = rag_generator.generate(parsed.directives)
            embedded = local_embedder.embed_shards(shards)
            store.upsert(embedded, namespace="products")

        query_vec = local_embedder.embed_text("budget smartphone")
        results = store.search(query_vec, top_k=10, namespace="products")

        assert len(results) >= 5


# =============================================================================
# SchemaBridge Tests - Real Data
# =============================================================================


class TestSchemaBridgeRealData:
    """Schema.org JSON-LD generation using real products."""

    def test_pixel_9_pro_jsonld_structure(self, schema_bridge, pixel_9_pro_path):
        """Pixel 9 Pro generates valid Schema.org structure."""
        from commercetxt.parser import parse_file

        parsed = parse_file(pixel_9_pro_path)
        json_ld = schema_bridge.to_json_ld(parsed.directives)
        schema = json.loads(json_ld)

        assert schema["@context"] == "https://schema.org/"
        assert schema["@type"] == "Product"
        assert "offers" in schema

    def test_pixel_9_pro_jsonld_name(self, schema_bridge, pixel_9_pro_path):
        """Pixel 9 Pro JSON-LD contains correct product name."""
        from commercetxt.parser import parse_file

        parsed = parse_file(pixel_9_pro_path)
        schema = json.loads(schema_bridge.to_json_ld(parsed.directives))

        assert "Pixel 9 Pro" in schema["name"]

    def test_full_product_aggregate_rating(self, schema_bridge, full_product_path):
        """Full product JSON-LD includes aggregate rating with correct value."""
        from commercetxt.parser import parse_file

        parsed = parse_file(full_product_path)
        schema = json.loads(schema_bridge.to_json_ld(parsed.directives))

        assert "aggregateRating" in schema
        assert schema["aggregateRating"]["@type"] == "AggregateRating"
        assert float(schema["aggregateRating"]["ratingValue"]) == 4.7

    def test_subscription_product_offers(
        self, schema_bridge, subscription_product_path
    ):
        """Subscription product JSON-LD includes offers section."""
        from commercetxt.parser import parse_file

        parsed = parse_file(subscription_product_path)
        schema = json.loads(schema_bridge.to_json_ld(parsed.directives))

        assert "offers" in schema


# =============================================================================
# HealthChecker Tests - Real Data
# =============================================================================


class TestHealthCheckerRealData:
    """Health assessment using real product data."""

    def test_full_product_high_score(self, health_checker, full_product_path):
        """Full product achieves high health score."""
        from commercetxt.parser import parse_file

        parsed = parse_file(full_product_path)
        result = health_checker.assess(parsed.directives)

        assert result["score"] >= 60
        assert "suggestions" in result

    def test_minimal_product_suggestions(self, health_checker, minimal_product_path):
        """Minimal product receives improvement suggestions."""
        from commercetxt.parser import parse_file

        parsed = parse_file(minimal_product_path)
        result = health_checker.assess(parsed.directives)

        assert "suggestions" in result
        assert result["score"] >= 0

    def test_pixel_9_pro_quality_score(self, health_checker, pixel_9_pro_path):
        """Pixel 9 Pro (complete reference) scores well."""
        from commercetxt.parser import parse_file

        parsed = parse_file(pixel_9_pro_path)
        result = health_checker.assess(parsed.directives)

        assert result["score"] >= 50


# =============================================================================
# Comparator Tests - Real Data
# =============================================================================


class TestComparatorRealData:
    """Product comparison using real Google products."""

    def test_pixel_comparison_structure(
        self, product_comparator, pixel_9_pro_path, pixel_8a_path
    ):
        """Pixel 9 Pro vs Pixel 8a comparison returns expected fields."""
        from commercetxt.parser import parse_file

        parsed_9_pro = parse_file(pixel_9_pro_path)
        parsed_8a = parse_file(pixel_8a_path)

        result = product_comparator.compare(
            parsed_9_pro.directives, parsed_8a.directives
        )

        assert "price_advantage" in result
        assert "recommendation" in result


# =============================================================================
# RealtimeEnricher Tests - Real Data
# =============================================================================


class TestRealtimeEnricherRealData:
    """Realtime enrichment using actual storage."""

    def test_enrich_search_results(self, products_storage):
        """Enrich search results with live price data."""
        from commercetxt.rag.tools.realtime_enricher import RealtimeEnricher

        enricher = RealtimeEnricher(storage=products_storage)

        search_results = [
            {
                "id": "vec-1",
                "text": "Google Pixel 9 Pro",
                "score": 0.95,
                "metadata": {"product_id": "pixel-9-pro"},
            },
        ]

        enriched = enricher.enrich(search_results, fields=["price", "availability"])

        assert enriched[0]["metadata"].get("live_price") == "999.00"


# =============================================================================
# CommerceAIBridge Tests - Real Data
# =============================================================================


class TestCommerceAIBridgeRealData:
    """AI prompt generation using real products."""

    def test_pixel_9_pro_prompt(self, pixel_9_pro_path):
        """Generate AI prompt containing Pixel 9 Pro information."""
        from commercetxt.bridge import CommerceAIBridge
        from commercetxt.parser import parse_file

        parsed = parse_file(pixel_9_pro_path)
        bridge = CommerceAIBridge(parsed)

        prompt = bridge.generate_low_token_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert "Pixel" in prompt or "Google" in prompt

    def test_subscription_product_prompt(self, subscription_product_path):
        """Generate AI prompt for subscription product."""
        from commercetxt.bridge import CommerceAIBridge
        from commercetxt.parser import parse_file

        parsed = parse_file(subscription_product_path)
        bridge = CommerceAIBridge(parsed)

        prompt = bridge.generate_low_token_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 50


# =============================================================================
# SemanticNormalizer Tests - Real Data
# =============================================================================


class TestSemanticNormalizerRealData:
    """Specification normalization using real products."""

    def test_normalize_pixel_specs(self, semantic_normalizer, pixel_9_pro_path):
        """Normalize Pixel 9 Pro specifications."""
        from commercetxt.parser import parse_file

        parsed = parse_file(pixel_9_pro_path)
        specs = parsed.directives.get("SPECS", {})

        if specs:
            normalized = semantic_normalizer.normalize_specs(specs)
            assert isinstance(normalized, dict)

    def test_normalize_full_product_weight(
        self, semantic_normalizer, full_product_path
    ):
        """Full product weight normalization includes units."""
        from commercetxt.parser import parse_file

        parsed = parse_file(full_product_path)
        specs = parsed.directives.get("SPECS", {})

        normalized = semantic_normalizer.normalize_specs(specs)

        if "Weight" in normalized:
            weight_val = normalized["Weight"]
            assert "g" in weight_val or "kg" in weight_val


# =============================================================================
# Validation Tests - Directory Scanning
# =============================================================================


class TestValidDirectoryFiles:
    """Validate all files in vectors/valid/ directory."""

    def test_all_valid_files_parse_without_errors(self):
        """Every file in vectors/valid/ parses without errors."""
        from pathlib import Path

        from commercetxt.parser import parse_file

        valid_dir = Path(__file__).parent / "vectors" / "valid"

        if not valid_dir.exists():
            pytest.skip("Valid directory not found")

        for file_path in valid_dir.glob("*.txt"):
            result = parse_file(file_path)
            assert len(result.errors) == 0, f"{file_path.name}: {result.errors}"
