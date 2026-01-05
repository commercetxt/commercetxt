"""
Async storage interface for realtime data lookup.

Defines the contract for async storage backends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any


class AsyncBaseStorage(ABC):
    """
    Abstract base for async realtime storage backends.

    Provides non-blocking access to product attributes for realtime enrichment.
    """

    @abstractmethod
    async def get_live_attributes(
        self, product_ids: list[str], fields: Sequence[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch specific fields for a list of product IDs asynchronously.

        Args:
            product_ids: List of product identifiers
            fields: List of field names to retrieve (e.g., ['price', 'availability'])

        Returns:
            Dictionary mapping product_id -> {field: value}

        Example:
            result = await storage.get_live_attributes(
                ['pixel-9-pro', 'pixel-8a'],
                ['price', 'availability']
            )
            # {
            #     'pixel-9-pro': {'price': 999, 'availability': 'InStock'},
            #     'pixel-8a': {'price': 499, 'availability': 'OutOfStock'}
            # }
        """
        pass

    @abstractmethod
    async def set_live_attributes(
        self, product_id: str, attributes: dict[str, Any]
    ) -> bool:
        """
        Update product attributes asynchronously.

        Args:
            product_id: Product identifier
            attributes: Dictionary of attributes to update

        Returns:
            True if successful

        Example:
            await storage.set_live_attributes(
                'pixel-9-pro',
                {'price': 899, 'availability': 'InStock'}
            )
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Check storage health asynchronously.

        Returns:
            Health status dictionary with 'status' key ('healthy' or 'unhealthy')
        """
        pass
