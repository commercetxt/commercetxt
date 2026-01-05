"""
Health monitoring system for RAG components.

Provides comprehensive health checks and status aggregation.
"""

from __future__ import annotations

import time
from typing import Any

# Constants
HEALTH_CHECK_CACHE_TTL = 30  # seconds - cache health check results


class HealthMonitor:
    """
    Aggregated health monitoring for RAG system.

    Checks all components and provides overall system health status.

    Example:
        monitor = HealthMonitor(pipeline)

        health = await monitor.check_health()
        print(health["status"])  # "healthy" or "degraded" or "unhealthy"

        # Detailed component status
        for component, status in health["components"].items():
            print(f"{component}: {status['status']}")
    """

    def __init__(self, pipeline=None):
        """
        Initialize health monitor.

        Args:
            pipeline: RAG pipeline instance to monitor
        """
        self.pipeline = pipeline
        self._last_check = None
        self._last_result = None

    async def check_health(self, force: bool = False) -> dict[str, Any]:
        """
        Perform comprehensive health check.

        Args:
            force: Force fresh check (ignore cache)

        Returns:
            Health status dictionary with component details
        """
        # Return cached result if recent (within HEALTH_CHECK_CACHE_TTL seconds)
        if not force and self._last_check:
            if time.time() - self._last_check < HEALTH_CHECK_CACHE_TTL:
                cached_result: dict[str, Any] = self._last_result
                return cached_result

        checks = {}

        # Check pipeline
        if self.pipeline:
            if hasattr(self.pipeline, "health_check"):
                try:
                    checks["pipeline"] = await self.pipeline.health_check()
                except Exception as e:
                    checks["pipeline"] = {"status": "unhealthy", "error": str(e)}
            else:
                checks["pipeline"] = {
                    "status": "healthy",
                    "note": "No health_check method",
                }

            # Check cache if enabled
            if hasattr(self.pipeline, "get_cache_stats"):
                try:
                    cache_stats = self.pipeline.get_cache_stats()
                    if cache_stats.get("caching_enabled"):
                        checks["cache"] = {
                            "status": "healthy",
                            "stats": cache_stats,
                        }
                    else:
                        checks["cache"] = {"status": "disabled"}
                except Exception as e:
                    checks["cache"] = {"status": "unhealthy", "error": str(e)}

        # Determine overall status
        component_statuses = [c.get("status", "unknown") for c in checks.values()]

        if all(s == "healthy" for s in component_statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in component_statuses):
            overall_status = "unhealthy"
        elif "disabled" in component_statuses:
            overall_status = "healthy"  # Disabled is not unhealthy
        else:
            overall_status = "degraded"

        result = {
            "status": overall_status,
            "timestamp": time.time(),
            "components": checks,
            "version": "1.0.0",
        }

        # Cache result
        self._last_check = time.time()
        self._last_result = result

        return result

    def get_metrics_summary(self) -> dict[str, Any]:
        """
        Get metrics summary for monitoring dashboard.

        Returns:
            Metrics summary dictionary
        """
        from ..metrics import get_metrics_summary

        return get_metrics_summary()

    async def check_component(self, component_name: str) -> dict[str, Any]:
        """
        Check specific component health.

        Args:
            component_name: Component to check (e.g., "cache", "vector_store")

        Returns:
            Component health status
        """
        full_health = await self.check_health(force=True)
        component_status: dict[str, Any] = full_health["components"].get(
            component_name, {"status": "unknown", "error": "Component not found"}
        )
        return component_status


async def create_health_endpoint(pipeline) -> dict[str, Any]:
    """
    Create health check endpoint response.

    Args:
        pipeline: RAG pipeline instance

    Returns:
        Health check response suitable for HTTP endpoint
    """
    monitor = HealthMonitor(pipeline)
    health = await monitor.check_health()

    # Add useful metadata
    health["uptime"] = time.time()  # Could track actual uptime
    health["metrics_enabled"] = True  # From metrics module

    return health
