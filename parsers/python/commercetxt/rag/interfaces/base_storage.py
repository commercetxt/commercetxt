"""
Base Realtime Storage Interface.

Abstract base class for live data providers (price, stock).
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseRealtimeStorage(ABC):
    """
    Contract for retrieving 'live' volatile data (Price, Stock)
    that changes too frequently for Vector DB re-indexing.
    """

    @abstractmethod
    def get_live_attributes(
        self, product_ids: list[str], fields: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Fetches specific fields for a list of Product IDs.
        Returns: { "product_123": {"price": 99.00, "stock": "InStock"} }
        """
        pass
