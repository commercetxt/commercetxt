"""
RAG Pipeline.

Orchestrates ETL (ingest) and retrieval (search) operations.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .container import RAGContainer
from .core.generator import RAGGenerator
from .tools.health_check import AIHealthChecker
from .tools.realtime_enricher import RealtimeEnricher

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MIN_HEALTH_SCORE = 50  # Minimum quality score to accept products


class RAGPipeline:
    """
    The main orchestrator for CommerceTXT RAG operations.
    Handles ETL (Ingest) and Retrieval (Search).
    """

    container: RAGContainer
    generator: RAGGenerator
    health_checker: AIHealthChecker
    enricher: RealtimeEnricher

    def __init__(self, container: RAGContainer | None = None) -> None:
        # 1. Setup Dependency Injection
        self.container: RAGContainer = container or RAGContainer()

        # 2. Core Logic (Business Rules)
        self.generator: RAGGenerator = RAGGenerator()
        self.health_checker: AIHealthChecker = AIHealthChecker()

        # 3. Tools (injected via container)
        self.enricher: RealtimeEnricher = RealtimeEnricher(
            storage=self.container.storage
        )

    def ingest(self, product_data: dict[str, Any], namespace: str = "default") -> int:
        """
        Full ETL Process: Raw Data -> Health Check -> Shards -> Vectors -> DB.
        """
        start_time = time.time()
        product_id = product_data.get("ITEM", "Unknown")

        try:
            # Step 1: Health Check
            health = self.health_checker.assess(product_data)
            if health["score"] < DEFAULT_MIN_HEALTH_SCORE:
                logger.info(
                    "Skipped low-quality product",
                    extra={
                        "product_id": product_id,
                        "health_score": health["score"],
                        "min_score": 50,
                        "duration_ms": (time.time() - start_time) * 1000,
                    },
                )
                return 0

            # Step 2: Generate Shards
            generated = self.generator.generate(product_data)
            if isinstance(generated, str):
                logger.warning(
                    "Text mode not supported for ingest",
                    extra={"product_id": product_id},
                )
                return 0  # Text mode not supported for ingest
            shards: list[dict[str, Any]] = generated

            # Step 3: Vectorize (Lazy loaded embedder)
            shards = self.container.embedder.embed_shards(shards)

            # Step 4: Store (Lazy loaded vector DB)
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
            return count

        except Exception as e:
            logger.error(
                "Failed to ingest product",
                extra={
                    "product_id": product_id,
                    "namespace": namespace,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": (time.time() - start_time) * 1000,
                },
                exc_info=True,
            )
            raise

    def search(
        self, query: str, top_k: int = 5, namespace: str = "default"
    ) -> list[dict[str, Any]]:
        """
        Retrieval Process: Query -> Vector -> DB -> Realtime Enrichment.
        """
        start_time = time.time()

        try:
            # Step 1: Embed Query
            query_vector = self.container.embedder.embed_text(query)

            # Step 2: Vector Search
            self.container.vector_store.connect()
            raw_results = self.container.vector_store.search(
                query_vector, top_k=top_k, namespace=namespace
            )

            # Step 3: Realtime Enrichment (The 2026 Strategy)
            # Injects current Price and Stock without re-indexing
            final_results = self.enricher.enrich(raw_results)

            logger.info(
                "Search completed",
                extra={
                    "query": query[:100],  # Truncate long queries
                    "results_count": len(final_results),
                    "top_k": top_k,
                    "namespace": namespace,
                    "duration_ms": (time.time() - start_time) * 1000,
                },
            )

            return final_results

        except Exception as e:
            logger.error(
                "Search failed",
                extra={
                    "query": query[:100],
                    "namespace": namespace,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": (time.time() - start_time) * 1000,
                },
                exc_info=True,
            )
            raise
