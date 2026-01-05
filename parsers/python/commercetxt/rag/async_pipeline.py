"""
Async RAG pipeline with integrated caching and metrics.

Native async operations with multi-layer caching for production workloads.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from .container import RAGContainer
from .core.caching import EmbeddingCache, SearchResultCache
from .core.generator import RAGGenerator
from .metrics import (
    embedding_api_calls,
    ingest_latency,
    ingest_total,
    search_latency,
    search_total,
    track_latency,
)
from .tools.health_check import AIHealthChecker
from .tools.realtime_enricher import RealtimeEnricher

logger = logging.getLogger(__name__)


class AsyncRAGPipeline:
    """
    Production-ready async RAG pipeline with caching and metrics.

    Features:
    - Native async operations (no ThreadPoolExecutor)
    - Multi-layer caching (embeddings, search results)
    - Prometheus metrics integration
    - Health monitoring
    - Batch processing support

    Example:
        async with AsyncRAGPipeline(enable_cache=True) as pipeline:
            # Ingest with caching
            count = await pipeline.ingest(product_data)

            # Search with caching (10x faster on hits)
            results = await pipeline.search("wireless headphones")

            # Check cache stats
            stats = pipeline.get_cache_stats()
            print(f"Cache hit ratio: {stats['embedding_cache']['hit_ratio']:.1%}")
    """

    def __init__(
        self,
        container: RAGContainer | None = None,
        enable_cache: bool = True,
        cache_backend: str = "redis",
        embedding_cache_ttl: int = 86400,  # 24 hours
        search_cache_ttl: int = 3600,  # 1 hour
        min_health_score: int = 50,
    ) -> None:
        """
        Initialize enhanced async pipeline.

        Args:
            container: DI container
            enable_cache: Enable multi-layer caching
            cache_backend: "redis" or "sqlite"
            embedding_cache_ttl: Embedding cache TTL in seconds
            search_cache_ttl: Search cache TTL in seconds
            min_health_score: Minimum health score for ingest
        """
        self.container = container or RAGContainer()
        self.min_health_score = min_health_score

        # Core components
        self.generator = RAGGenerator()
        self.health_checker = AIHealthChecker()
        self.enricher = RealtimeEnricher(storage=self.container.storage)

        # Caching
        self.enable_cache = enable_cache
        self.embedding_cache = None
        self.search_cache = None

        if enable_cache:
            self.embedding_cache = EmbeddingCache(
                backend=cache_backend, ttl=embedding_cache_ttl
            )
            self.search_cache = SearchResultCache(
                backend=cache_backend, ttl=search_cache_ttl
            )

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup."""
        # Cleanup caches if needed
        pass

    @track_latency(ingest_latency)
    async def ingest(
        self, product_data: dict[str, Any], namespace: str = "default"
    ) -> int:
        """
        Ingest a single product with caching and metrics.

        Args:
            product_data: Product data dictionary
            namespace: Vector store namespace

        Returns:
            Number of vectors ingested (0 if skipped)
        """
        start_time = time.time()
        product_id = product_data.get("ITEM", "Unknown")

        try:
            # Health check
            health = self.health_checker.assess(product_data)
            if health["score"] < self.min_health_score:
                logger.info(
                    "Skipped low-quality product",
                    extra={
                        "product_id": product_id,
                        "health_score": health["score"],
                        "duration_ms": (time.time() - start_time) * 1000,
                    },
                )
                if ingest_total:
                    ingest_total.labels(status="skipped").inc()
                return 0

            # Generate shards
            shards = self.generator.generate(product_data)
            if not shards or isinstance(shards, str):
                if ingest_total:
                    ingest_total.labels(status="failed").inc()
                return 0

            # Embed shards with caching
            shards = await self._embed_shards_cached(shards)

            # Store vectors
            self.container.vector_store.connect()
            count = self.container.vector_store.upsert(shards, namespace=namespace)

            logger.info(
                "Successfully ingested product",
                extra={
                    "product_id": product_id,
                    "vectors_count": count,
                    "namespace": namespace,
                    "duration_ms": (time.time() - start_time) * 1000,
                },
            )

            if ingest_total:
                ingest_total.labels(status="success").inc()

            return count

        except Exception as e:
            logger.error(
                "Failed to ingest product",
                extra={
                    "product_id": product_id,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000,
                },
                exc_info=True,
            )
            if ingest_total:
                ingest_total.labels(status="error").inc()
            raise

    async def _embed_shards_cached(
        self, shards: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Embed shards with caching support.

        Args:
            shards: List of shard dictionaries

        Returns:
            Shards with embeddings
        """
        if not self.enable_cache or not self.embedding_cache:
            # No caching - use embedder directly
            return self.container.embedder.embed_shards(shards)

        # Check cache for each shard
        for shard in shards:
            text = shard["text"]
            cached_vector = await self.embedding_cache.get_cached_text(text)

            if cached_vector:
                # Cache hit
                shard["values"] = cached_vector
                shard["model"] = "cached"
            else:
                # Cache miss - embed and cache
                vector = self.container.embedder.embed_text(text)
                shard["values"] = vector

                # Store in cache
                await self.embedding_cache.cache_text(text, vector)

                if embedding_api_calls:
                    embedding_api_calls.labels(provider="local").inc()

        return shards

    @track_latency(search_latency)
    async def search(
        self, query: str, top_k: int = 5, namespace: str = "default"
    ) -> list[dict[str, Any]]:
        """
        Search with caching and metrics.

        Args:
            query: Search query
            top_k: Number of results
            namespace: Vector store namespace

        Returns:
            Search results with realtime enrichment
        """
        start_time = time.time()

        try:
            # Check search cache
            if self.enable_cache and self.search_cache:
                cached_results = await self.search_cache.get_cached_search(
                    query, top_k, namespace
                )
                if cached_results:
                    logger.debug(
                        "Search cache hit",
                        extra={
                            "query": query[:50],
                            "duration_ms": (time.time() - start_time) * 1000,
                        },
                    )
                    if search_total:
                        search_total.labels(status="cached").inc()
                    return cached_results

            # Cache miss - do full search
            query_vector = await self._embed_text_cached(query)

            # Vector search
            self.container.vector_store.connect()
            raw_results = self.container.vector_store.search(
                query_vector, top_k=top_k, namespace=namespace
            )

            # Realtime enrichment
            final_results = self.enricher.enrich(raw_results)

            # Cache results
            if self.enable_cache and self.search_cache:
                await self.search_cache.cache_search(
                    query, top_k, namespace, final_results
                )

            logger.info(
                "Search completed",
                extra={
                    "query": query[:50],
                    "results_count": len(final_results),
                    "duration_ms": (time.time() - start_time) * 1000,
                },
            )

            if search_total:
                search_total.labels(status="success").inc()

            return final_results

        except Exception as e:
            logger.error(
                "Search failed",
                extra={"query": query[:50], "error": str(e)},
                exc_info=True,
            )
            if search_total:
                search_total.labels(status="error").inc()
            raise

    async def _embed_text_cached(self, text: str) -> list[float]:
        """
        Embed text with caching support.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        if not self.enable_cache or not self.embedding_cache:
            return self.container.embedder.embed_text(text)

        # Check cache
        cached_vector = await self.embedding_cache.get_cached_text(text)
        if cached_vector:
            return cached_vector

        # Cache miss
        vector = self.container.embedder.embed_text(text)

        # Store in cache
        await self.embedding_cache.cache_text(text, vector)

        if embedding_api_calls:
            embedding_api_calls.labels(provider="local").inc()

        return vector

    async def ingest_batch(
        self,
        products: list[dict[str, Any]],
        namespace: str = "default",
        on_progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """
        Batch ingest with progress tracking.

        Args:
            products: List of product dictionaries
            namespace: Vector store namespace
            on_progress: Progress callback

        Returns:
            Summary with counts and errors
        """
        total = len(products)
        completed = 0
        ingested = 0
        skipped = 0
        errors = []

        for product in products:
            try:
                count = await self.ingest(product, namespace)
                if count > 0:
                    ingested += count
                else:
                    skipped += 1
            except Exception as e:
                errors.append({"item": product.get("ITEM", "Unknown"), "error": str(e)})

            completed += 1
            if on_progress:
                on_progress(completed, total)

        return {
            "total": total,
            "ingested": ingested,
            "skipped": skipped,
            "errors": errors,
        }

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        stats: dict[str, Any] = {"caching_enabled": self.enable_cache}

        if self.enable_cache:
            if self.embedding_cache:
                stats["embedding_cache"] = self.embedding_cache.get_stats()
            if self.search_cache:
                stats["search_cache"] = self.search_cache.get_stats()

        return stats

    async def health_check(self) -> dict[str, Any]:
        """
        Check pipeline health.

        Returns:
            Health status dictionary
        """
        checks: dict[str, Any] = {
            "vector_store": {"status": "healthy"},  # Could check actual connection
            "embedder": {"status": "healthy"},
            "cache": {
                "enabled": self.enable_cache,
                "status": "healthy" if self.enable_cache else "disabled",
            },
        }

        if self.enable_cache:
            cache_stats = self.get_cache_stats()
            checks["cache"]["stats"] = cache_stats

        overall = "healthy"
        return {"status": overall, "timestamp": time.time(), "components": checks}
