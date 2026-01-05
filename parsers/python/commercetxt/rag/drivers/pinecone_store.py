"""
Pinecone vector store driver with retry logic and error handling.
"""

from __future__ import annotations

import logging
import time
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
    """
    Retry decorator with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exceptions to catch
    """

    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt == max_retries:
                    raise

                # Exponential backoff with jitter
                delay = min(base_delay * (2**attempt), max_delay)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)

        raise last_exception  # type: ignore

    return wrapper


class PineconeStore(BaseVectorStore):
    """
    Production-ready driver for Pinecone Vector Database.

    Features:
    - Automatic retry with exponential backoff
    - Connection health checking
    - Batch upsert with configurable size
    - Rate limit handling
    """

    DEFAULT_BATCH_SIZE = 100
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0

    def __init__(
        self,
        api_key: str,
        index_name: str,
        dimension: int = 384,
        batch_size: int | None = None,
        max_retries: int | None = None,
    ):
        """
        Initialize PineconeStore.

        Args:
            api_key: Pinecone API key
            index_name: Name of the index
            dimension: Vector dimension (default: 384 for MiniLM)
            batch_size: Vectors per upsert batch (default: 100)
            max_retries: Max retry attempts (default: 3)
        """
        self.api_key = api_key
        self.index_name = index_name
        self.dimension = dimension
        self.batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self.max_retries = max_retries or self.MAX_RETRIES
        self.index = None
        self.client = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to Pinecone with health check.

        Reuses existing connection if healthy.

        Returns:
            True if connection successful
        """
        # Reuse existing connection if healthy
        if self._connected and self.index is not None and self._is_connection_healthy():
            logger.debug("Reusing existing Pinecone connection")
            return True

        try:
            from pinecone import Pinecone, ServerlessSpec

            self.client = Pinecone(api_key=self.api_key)  # type: ignore[assignment]

            assert self.client is not None
            existing_indexes = [i.name for i in self.client.list_indexes()]
            if self.index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index '{self.index_name}'...")
                self.client.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )
                # Wait for index to be ready
                self._wait_for_index_ready()

            self.index = self.client.Index(self.index_name)
            self._connected = True
            logger.info(f"Connected to Pinecone index '{self.index_name}'")
            return True

        except ImportError:
            raise ImportError("Missing dependency. Run: pip install pinecone") from None
        except Exception as e:
            logger.error(f"Failed to connect to Pinecone: {e}")
            self._connected = False
            raise

    def _is_connection_healthy(self) -> bool:
        """
        Check if the current connection is healthy.

        Returns:
            True if connection is healthy and usable
        """
        if not self._connected or self.index is None:
            return False

        try:
            # Lightweight health check - fetch index stats
            self.index.describe_index_stats()
            return True
        except Exception as e:
            logger.warning(f"Pinecone connection unhealthy: {e}")
            self._connected = False
            return False

    def _wait_for_index_ready(self, timeout: int = 60) -> None:
        """Wait for index to be ready after creation."""
        assert self.client is not None
        start = time.time()
        while time.time() - start < timeout:
            try:
                index_info = self.client.describe_index(self.index_name)
                if index_info.status.ready:
                    return
            except Exception as e:
                logger.debug(f"Index not ready yet: {e}")
            time.sleep(2)
        logger.warning(f"Index ready timeout after {timeout}s, proceeding anyway")

    def upsert(self, shards: list[dict[str, Any]], namespace: str) -> int:
        """
        Upload vectors with retry logic.

        Args:
            shards: List of shard dictionaries with 'values' and 'metadata'
            namespace: Target namespace

        Returns:
            Number of vectors upserted
        """
        if not self.index:
            raise ConnectionError("Pinecone not connected. Call connect() first.")

        vectors = []
        for i, shard in enumerate(shards):
            attr_type = shard["metadata"].get("attr_type", "misc")
            safe_id = f"{attr_type}_{i}_{int(time.time())}"

            meta = shard["metadata"].copy()
            meta["text"] = shard["text"]
            if "original_data" in meta:
                del meta["original_data"]
            # Flatten semantic_tags if it's a list of dicts
            tags = meta.get("semantic_tags", [])
            if tags and isinstance(tags, list) and isinstance(tags[0], dict):
                meta["semantic_tags"] = [t.get("tag", str(t)) for t in tags]

            vectors.append({"id": safe_id, "values": shard["values"], "metadata": meta})

        # Batch upload with retry
        total_upserted = 0
        for i in range(0, len(vectors), self.batch_size):
            batch = vectors[i : i + self.batch_size]
            total_upserted += self._upsert_batch_with_retry(batch, namespace)

        return total_upserted

    def _upsert_batch_with_retry(
        self, batch: list[dict[str, Any]], namespace: str
    ) -> int:
        """Upsert a single batch with retry logic."""

        def _do_upsert():
            self.index.upsert(vectors=batch, namespace=namespace)
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
            namespace: Target namespace

        Returns:
            List of matches with scores and metadata
        """
        if not self.index:
            raise ConnectionError("Pinecone not connected. Call connect() first.")

        def _do_search():
            results = self.index.query(
                vector=vector, top_k=top_k, namespace=namespace, include_metadata=True
            )
            return results.to_dict()["matches"]

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
        Delete vectors by ID or delete all in namespace.

        Args:
            ids: List of vector IDs to delete
            namespace: Target namespace
            delete_all: If True, delete all vectors in namespace

        Returns:
            True if deletion successful
        """
        if not self.index:
            raise ConnectionError("Pinecone not connected.")

        try:
            if delete_all:
                self.index.delete(delete_all=True, namespace=namespace)
            elif ids:
                self.index.delete(ids=ids, namespace=namespace)
            return True
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

    def health_check(self) -> dict[str, Any]:
        """
        Check connection health and index stats.

        Returns:
            Health status dictionary
        """
        try:
            if not self._connected or not self.index:
                self.connect()

            assert self.index is not None  # Ensured by connect()
            stats = self.index.describe_index_stats()
            return {
                "status": "healthy",
                "index_name": self.index_name,
                "total_vectors": stats.total_vector_count,
                "namespaces": list(stats.namespaces.keys()) if stats.namespaces else [],
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def disconnect(self) -> None:
        """Close connection and cleanup."""
        self.index = None
        self.client = None
        self._connected = False
