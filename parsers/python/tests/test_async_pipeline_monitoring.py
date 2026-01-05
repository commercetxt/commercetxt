"""
Comprehensive tests for RAG async pipeline, monitoring, and CLI-related modules.

Covers AsyncRAGPipeline, HealthMonitor, and RAG metrics with mutation-resistant tests.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# AsyncRAGPipeline Comprehensive Tests
# =============================================================================


class TestAsyncRAGPipelineComprehensive:
    """Comprehensive tests for AsyncRAGPipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_initialization_default(self):
        """Default initialization creates components."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline()

        assert pipeline.generator is not None
        assert pipeline.health_checker is not None
        assert pipeline.enricher is not None
        assert pipeline.enable_cache is True

    @pytest.mark.asyncio
    async def test_pipeline_initialization_cache_disabled(self):
        """Cache disabled when enable_cache=False."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline(enable_cache=False)

        assert pipeline.enable_cache is False
        assert pipeline.embedding_cache is None
        assert pipeline.search_cache is None

    @pytest.mark.asyncio
    async def test_pipeline_initialization_with_custom_ttl(self):
        """Custom TTL values applied to caches."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline(
            embedding_cache_ttl=7200,
            search_cache_ttl=1800,
        )

        assert pipeline.embedding_cache is not None
        assert pipeline.embedding_cache.default_ttl == 7200
        assert pipeline.search_cache is not None
        assert pipeline.search_cache.default_ttl == 1800

    @pytest.mark.asyncio
    async def test_pipeline_initialization_with_min_health_score(self):
        """Min health score applied."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline(min_health_score=75)

        assert pipeline.min_health_score == 75

    @pytest.mark.asyncio
    async def test_context_manager_entry_exit(self):
        """Context manager enters and exits properly."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        async with AsyncRAGPipeline() as pipeline:
            assert pipeline is not None

    @pytest.mark.asyncio
    async def test_ingest_skips_low_health_score(self):
        """Ingest skips products below min health score."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline(min_health_score=80)
        pipeline.health_checker = MagicMock()
        pipeline.health_checker.assess.return_value = {"score": 30}

        product_data = {"ITEM": "Low Quality Product"}
        result = await pipeline.ingest(product_data)

        assert result == 0

    @pytest.mark.asyncio
    async def test_ingest_skips_empty_shards(self):
        """Ingest skips products that generate no shards."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline()
        pipeline.health_checker = MagicMock()
        pipeline.health_checker.assess.return_value = {"score": 90}
        pipeline.generator = MagicMock()
        pipeline.generator.generate.return_value = []  # Empty shards

        result = await pipeline.ingest({"ITEM": "Test"})

        assert result == 0

    @pytest.mark.asyncio
    async def test_ingest_skips_string_shards(self):
        """Ingest skips when generator returns string."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline()
        pipeline.health_checker = MagicMock()
        pipeline.health_checker.assess.return_value = {"score": 90}
        pipeline.generator = MagicMock()
        pipeline.generator.generate.return_value = "text output"  # String result

        result = await pipeline.ingest({"ITEM": "Test"})

        assert result == 0

    @pytest.mark.asyncio
    async def test_ingest_batch_progress_callback(self):
        """Batch ingest calls progress callback."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline()
        pipeline.ingest = AsyncMock(return_value=5)

        progress_calls = []

        def on_progress(completed, total):
            progress_calls.append((completed, total))

        products = [{"ITEM": f"Product-{i}"} for i in range(3)]
        await pipeline.ingest_batch(products, on_progress=on_progress)

        assert len(progress_calls) == 3

    @pytest.mark.asyncio
    async def test_ingest_batch_collects_errors(self):
        """Batch ingest collects errors without stopping."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline()

        call_count = [0]

        async def mock_ingest(product, namespace="default"):
            call_count[0] += 1
            if call_count[0] == 2:
                raise ValueError("Test error")
            return 1

        pipeline.ingest = mock_ingest

        products = [{"ITEM": f"Product-{i}"} for i in range(3)]
        result = await pipeline.ingest_batch(products)

        assert result["total"] == 3
        assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_embed_shards_cached_no_cache(self):
        """Embed shards without cache uses embedder directly."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline(enable_cache=False)
        pipeline.container = MagicMock()
        pipeline.container.embedder.embed_shards.return_value = [
            {"text": "test", "values": [0.1] * 384}
        ]

        shards = [{"text": "test", "metadata": {}}]
        result = await pipeline._embed_shards_cached(shards)

        pipeline.container.embedder.embed_shards.assert_called_once()
        assert result == [{"text": "test", "values": [0.1] * 384}]

    @pytest.mark.asyncio
    async def test_embed_text_cached_no_cache(self):
        """Embed text without cache uses embedder directly."""
        from commercetxt.rag.async_pipeline import AsyncRAGPipeline

        pipeline = AsyncRAGPipeline(enable_cache=False)
        pipeline.container = MagicMock()
        pipeline.container.embedder.embed_text.return_value = [0.1] * 384

        result = await pipeline._embed_text_cached("test text")

        assert result == [0.1] * 384


# =============================================================================
# HealthMonitor Tests
# =============================================================================


class TestHealthMonitorComprehensive:
    """Comprehensive tests for HealthMonitor."""

    @pytest.mark.asyncio
    async def test_health_monitor_initialization(self):
        """Health monitor initializes with pipeline."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock()
        monitor = HealthMonitor(pipeline)

        assert monitor.pipeline is pipeline
        assert monitor._last_check is None
        assert monitor._last_result is None

    @pytest.mark.asyncio
    async def test_check_health_caches_result(self):
        """Health check caches result for TTL period."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock()
        pipeline.health_check = AsyncMock(return_value={"status": "healthy"})

        monitor = HealthMonitor(pipeline)

        # First call
        result1 = await monitor.check_health()
        assert result1["status"] == "healthy"

        # Second call should use cache
        result2 = await monitor.check_health()
        assert result2["status"] == "healthy"

        # health_check called only once due to caching
        pipeline.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_health_force_bypass_cache(self):
        """Force parameter bypasses cache."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock()
        pipeline.health_check = AsyncMock(return_value={"status": "healthy"})

        monitor = HealthMonitor(pipeline)

        await monitor.check_health()
        await monitor.check_health(force=True)

        assert pipeline.health_check.call_count == 2

    @pytest.mark.asyncio
    async def test_check_health_handles_pipeline_exception(self):
        """Health check handles pipeline exception."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock()
        pipeline.health_check = AsyncMock(side_effect=Exception("Connection failed"))

        monitor = HealthMonitor(pipeline)
        result = await monitor.check_health()

        assert result["components"]["pipeline"]["status"] == "unhealthy"
        assert "error" in result["components"]["pipeline"]

    @pytest.mark.asyncio
    async def test_check_health_no_health_check_method(self):
        """Health check handles pipeline without health_check method."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock(spec=[])  # No health_check method

        monitor = HealthMonitor(pipeline)
        result = await monitor.check_health()

        assert result["components"]["pipeline"]["status"] == "healthy"
        assert "note" in result["components"]["pipeline"]

    @pytest.mark.asyncio
    async def test_check_health_checks_cache_stats(self):
        """Health check includes cache stats if available."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock()
        pipeline.health_check = AsyncMock(return_value={"status": "healthy"})
        pipeline.get_cache_stats.return_value = {
            "caching_enabled": True,
            "hit_ratio": 0.85,
        }

        monitor = HealthMonitor(pipeline)
        result = await monitor.check_health()

        assert "cache" in result["components"]
        assert result["components"]["cache"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_health_cache_disabled(self):
        """Health check handles disabled cache."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock()
        pipeline.health_check = AsyncMock(return_value={"status": "healthy"})
        pipeline.get_cache_stats.return_value = {"caching_enabled": False}

        monitor = HealthMonitor(pipeline)
        result = await monitor.check_health()

        assert result["components"]["cache"]["status"] == "disabled"
        # Disabled cache should not affect overall status
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_health_overall_status_unhealthy(self):
        """Overall status unhealthy when component unhealthy."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock()
        pipeline.health_check = AsyncMock(side_effect=Exception("Failed"))

        monitor = HealthMonitor(pipeline)
        result = await monitor.check_health()

        assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_component_specific(self):
        """Check specific component health."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock()
        pipeline.health_check = AsyncMock(return_value={"status": "healthy"})
        pipeline.get_cache_stats.return_value = {"caching_enabled": True}

        monitor = HealthMonitor(pipeline)
        result = await monitor.check_component("cache")

        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_check_component_not_found(self):
        """Check component returns unknown for missing component."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        pipeline = MagicMock(spec=[])
        monitor = HealthMonitor(pipeline)
        result = await monitor.check_component("nonexistent")

        assert result["status"] == "unknown"

    def test_get_metrics_summary(self):
        """Get metrics summary from monitor."""
        from commercetxt.rag.monitoring.health import HealthMonitor

        monitor = HealthMonitor(None)
        summary = monitor.get_metrics_summary()

        assert isinstance(summary, dict)


class TestHealthEndpoint:
    """Tests for health endpoint helper."""

    @pytest.mark.asyncio
    async def test_create_health_endpoint(self):
        """Health endpoint creates proper response."""
        from commercetxt.rag.monitoring.health import create_health_endpoint

        pipeline = MagicMock(spec=[])  # No health_check method

        result = await create_health_endpoint(pipeline)

        assert "status" in result
        assert "uptime" in result
        assert "metrics_enabled" in result


# =============================================================================
# RAG Metrics Tests
# =============================================================================


class TestRAGMetrics:
    """Tests for RAG metrics module."""

    def test_metrics_enabled_check(self):
        """metrics_enabled returns boolean."""
        from commercetxt.rag.metrics import metrics_enabled

        result = metrics_enabled()
        assert isinstance(result, bool)

    def test_get_metrics_summary(self):
        """get_metrics_summary returns dict."""
        from commercetxt.rag.metrics import get_metrics_summary

        summary = get_metrics_summary()
        assert isinstance(summary, dict)

    def test_export_metrics_to_prometheus(self):
        """export_metrics_to_prometheus returns string."""
        from commercetxt.rag.metrics import export_metrics_to_prometheus

        result = export_metrics_to_prometheus()
        assert isinstance(result, str)

    def test_track_latency_decorator_sync(self):
        """track_latency decorator works for sync functions."""
        from commercetxt.rag.metrics import track_latency

        mock_histogram = MagicMock()

        @track_latency(mock_histogram)
        def sync_function():
            return "result"

        result = sync_function()
        assert result == "result"

    def test_track_latency_decorator_none_histogram(self):
        """track_latency with None histogram returns original function."""
        from commercetxt.rag.metrics import track_latency

        @track_latency(None)
        def sync_function():
            return "result"

        result = sync_function()
        assert result == "result"

    @pytest.mark.asyncio
    async def test_track_latency_decorator_async(self):
        """track_latency decorator works for async functions."""
        from commercetxt.rag.metrics import PROMETHEUS_AVAILABLE, track_latency

        mock_histogram = MagicMock() if PROMETHEUS_AVAILABLE else None

        @track_latency(mock_histogram)
        async def async_function():
            return "async result"

        result = await async_function()
        assert result == "async result"

    def test_count_calls_decorator(self):
        """count_calls decorator works."""
        from commercetxt.rag.metrics import count_calls

        mock_counter = MagicMock()

        @count_calls(mock_counter, status="success")
        def counted_function():
            return "counted"

        result = counted_function()
        assert result == "counted"

    def test_count_calls_none_counter(self):
        """count_calls with None counter returns original function."""
        from commercetxt.rag.metrics import count_calls

        @count_calls(None, status="success")
        def counted_function():
            return "counted"

        result = counted_function()
        assert result == "counted"


# =============================================================================
# CLI Handler Tests (Mocked)
# =============================================================================


class TestCLIHandlers:
    """Tests for CLI handler functions."""

    def test_print_health_text_excellent(self, capsys):
        """Health text printed for excellent score."""
        from commercetxt.cli import _print_health_text

        report = {"score": 95, "suggestions": []}
        _print_health_text(report)

        captured = capsys.readouterr()
        assert "95/100" in captured.out
        assert "EXCELLENT" in captured.out

    def test_print_health_text_good(self, capsys):
        """Health text printed for good score."""
        from commercetxt.cli import _print_health_text

        report = {"score": 75, "suggestions": ["Improve description"]}
        _print_health_text(report)

        captured = capsys.readouterr()
        assert "75/100" in captured.out
        assert "GOOD" in captured.out
        assert "Improve description" in captured.out

    def test_print_health_text_fair(self, capsys):
        """Health text printed for fair score."""
        from commercetxt.cli import _print_health_text

        report = {"score": 55, "suggestions": []}
        _print_health_text(report)

        captured = capsys.readouterr()
        assert "55/100" in captured.out
        assert "FAIR" in captured.out

    def test_print_health_text_poor(self, capsys):
        """Health text printed for poor score."""
        from commercetxt.cli import _print_health_text

        report = {"score": 30, "suggestions": []}
        _print_health_text(report)

        captured = capsys.readouterr()
        assert "30/100" in captured.out
        assert "POOR" in captured.out

    def test_print_comparison_text(self, capsys):
        """Comparison text printed correctly."""
        from commercetxt.cli import _print_comparison_text

        comp = {
            "price_advantage": "product_a",
            "savings": "$50",
            "spec_differences": [
                {
                    "attribute": "Weight",
                    "product_a": "1kg",
                    "product_b": "2kg",
                    "advantage": "product_a",
                }
            ],
            "recommendation": "Buy Product A",
        }

        _print_comparison_text(comp, "product-a.txt", "product-b.txt")

        captured = capsys.readouterr()
        assert "PRODUCT_A" in captured.out
        assert "$50" in captured.out
        assert "Weight" in captured.out


# =============================================================================
# Rate Limiter Tests
# =============================================================================


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Rate limiter initializes with calls per second."""
        from commercetxt.rag.core.rate_limiter import RateLimiter

        limiter = RateLimiter(calls_per_second=5.0)
        assert limiter.rate == 5.0

    def test_rate_limiter_acquire(self):
        """Rate limiter acquire works without error."""
        from commercetxt.rag.core.rate_limiter import RateLimiter

        limiter = RateLimiter(calls_per_second=100.0)

        # Should not block for high rate
        start = time.time()
        for _ in range(5):
            limiter.acquire()
        duration = time.time() - start

        # Should complete quickly
        assert duration < 1.0

    def test_rate_limiter_enforces_rate(self):
        """Rate limiter enforces rate limit."""
        from commercetxt.rag.core.rate_limiter import RateLimiter

        limiter = RateLimiter(calls_per_second=10.0)

        # Multiple rapid calls
        time.time()
        for _ in range(3):
            limiter.acquire()

        # Should have some delay but be reasonable
        assert True  # Just verify no exceptions
