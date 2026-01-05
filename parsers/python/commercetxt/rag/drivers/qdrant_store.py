"""
Qdrant vector store driver with retry logic and error handling.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from ..interfaces.base_vector_store import BaseVectorStore

logger = logging.getLogger(__name__)


def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
):
    """Retry decorator with exponential backoff."""

    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt == max_retries:
                    raise
                delay = min(base_delay * (2**attempt), max_delay)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
        raise last_exception  # type: ignore

    return wrapper


class QdrantStore(BaseVectorStore):
    """
    Driver for Qdrant (Open Source / Cloud) with retry logic.

    Features:
    - Automatic retry with exponential backoff
    - Connection health checking
    - Namespace emulation via payload filters
    - Batch upsert support
    """

    DEFAULT_BATCH_SIZE = 100
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        collection_name: str = "commerce",
        dimension: int = 384,
        batch_size: int | None = None,
        max_retries: int | None = None,
    ):
        """
        Initialize QdrantStore.

        Args:
            url: Qdrant server URL
            api_key: API key for Qdrant Cloud
            collection_name: Name of the collection
            dimension: Vector dimension (default: 384)
            batch_size: Points per upsert batch
            max_retries: Max retry attempts
        """
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.dimension = dimension
        self.batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self.max_retries = max_retries or self.MAX_RETRIES
        self.client = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to Qdrant with health check.

        Reuses existing connection if healthy.

        Returns:
            True if connection successful
        """
        # Reuse existing connection if healthy
        if (
            self._connected
            and self.client is not None
            and self._is_connection_healthy()
        ):
            logger.debug("Reusing existing Qdrant connection")
            return True

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self.client = QdrantClient(url=self.url, api_key=self.api_key)  # type: ignore[assignment]

            # Check if collection exists
            assert self.client is not None  # Help mypy understand client is initialized
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                logger.info(f"Creating Qdrant collection '{self.collection_name}'...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension, distance=Distance.COSINE
                    ),
                )

            self._connected = True
            logger.info(f"Connected to Qdrant collection '{self.collection_name}'")
            return True

        except ImportError:
            raise ImportError(
                "Missing dependency. Run: pip install qdrant-client"
            ) from None
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            self._connected = False
            raise

    def _is_connection_healthy(self) -> bool:
        """
        Check if the current connection is healthy.

        Returns:
            True if connection is healthy and usable
        """
        if not self._connected or self.client is None:
            return False

        try:
            # Lightweight health check - fetch collection info
            self.client.get_collection(self.collection_name)
            return True
        except Exception as e:
            logger.warning(f"Qdrant connection unhealthy: {e}")
            self._connected = False
            return False

    def upsert(self, shards: list[dict[str, Any]], namespace: str) -> int:
        """
        Upload vectors with retry logic.

        Args:
            shards: List of shard dictionaries
            namespace: Namespace (stored in payload for filtering)

        Returns:
            Number of points upserted
        """
        if not self.client:
            raise ConnectionError("Qdrant not connected. Call connect() first.")

        from qdrant_client.models import PointStruct

        points = []
        for shard in shards:
            point_id = str(uuid.uuid4())
            payload = shard["metadata"].copy()
            payload["text"] = shard["text"]
            payload["namespace"] = namespace

            # Flatten semantic_tags if needed
            tags = payload.get("semantic_tags", [])
            if tags and isinstance(tags, list) and isinstance(tags[0], dict):
                payload["semantic_tags"] = [t.get("tag", str(t)) for t in tags]

            # Remove complex objects that Qdrant can't store
            if "original_data" in payload:
                del payload["original_data"]

            points.append(
                PointStruct(id=point_id, vector=shard["values"], payload=payload)
            )

        # Batch upsert with retry
        total_upserted = 0
        for i in range(0, len(points), self.batch_size):
            batch = points[i : i + self.batch_size]
            total_upserted += self._upsert_batch_with_retry(batch)

        return total_upserted

    def _upsert_batch_with_retry(self, batch: list) -> int:
        """Upsert a single batch with retry logic."""

        def _do_upsert():
            self.client.upsert(collection_name=self.collection_name, points=batch)
            return len(batch)

        result = retry_with_backoff(
            _do_upsert,
            max_retries=self.max_retries,
            base_delay=self.RETRY_BASE_DELAY,
        )()
        return int(result) if result is not None else 0

    def search(
        self, vector: list[float], top_k: int = 5, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors with retry logic.

        Args:
            vector: Query vector
            top_k: Number of results
            namespace: Filter by namespace (optional)

        Returns:
            List of matches with scores and metadata
        """
        if not self.client:
            raise ConnectionError("Qdrant not connected. Call connect() first.")

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        def _do_search():
            query_filter = None
            if namespace:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="namespace", match=MatchValue(value=namespace)
                        )
                    ]
                )

            hits = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=query_filter,
                limit=top_k,
            )

            # Normalize output to match Pinecone structure
            return [
                {"id": str(hit.id), "score": hit.score, "metadata": hit.payload}
                for hit in hits
            ]

        return retry_with_backoff(
            _do_search,
            max_retries=self.max_retries,
            base_delay=self.RETRY_BASE_DELAY,
        )()

    def delete(
        self,
        ids: list[str] | None = None,
        namespace: str | None = None,
        delete_all: bool = False,
    ) -> bool:
        """
        Delete points by ID or by namespace filter.

        Args:
            ids: List of point IDs to delete
            namespace: Delete all points in namespace
            delete_all: Delete entire collection contents

        Returns:
            True if deletion successful
        """
        if not self.client:
            raise ConnectionError("Qdrant not connected.")

        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            if delete_all:
                # Recreate collection to delete all
                self.client.delete_collection(self.collection_name)
                self._connected = False
                self.connect()
            elif namespace:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="namespace", match=MatchValue(value=namespace)
                            )
                        ]
                    ),
                )
            elif ids:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=ids,
                )
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def health_check(self) -> dict[str, Any]:
        """
        Check connection health and collection stats.

        Returns:
            Health status dictionary
        """
        try:
            if not self._connected or not self.client:
                self.connect()

            assert self.client is not None  # Ensured by connect()
            info = self.client.get_collection(self.collection_name)
            return {
                "status": "healthy",
                "collection_name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "collection_status": info.status.name,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def disconnect(self) -> None:
        """Close connection and cleanup."""
        if self.client:
            self.client.close()
        self.client = None
        self._connected = False
