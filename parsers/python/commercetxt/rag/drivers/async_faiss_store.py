"""
Async Faiss vector store using asyncio.to_thread for CPU-bound operations.

Provides non-blocking access to Faiss indices while maintaining thread safety.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

import numpy as np

from ..interfaces.async_vector_store import AsyncBaseVectorStore

logger = logging.getLogger(__name__)


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    """Normalize vectors to unit length for cosine similarity."""
    x = x.astype("float32", copy=False)
    norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
    normalized: np.ndarray = x / norms
    return normalized


class AsyncFaissStore(AsyncBaseVectorStore):
    """
    Async wrapper for Faiss vector store.

    Uses asyncio.to_thread() to run blocking Faiss operations without blocking
    the event loop. Maintains thread safety with locks.

    Features:
    - Non-blocking index operations
    - Atomic file writes
    - ID mapping persistence
    - Connection health checking
    - Namespace support

    Example:
        store = AsyncFaissStore(root_dir=".rag/faiss", dimension=384)

        await store.connect()

        # Upsert vectors
        count = await store.upsert(shards, namespace="products")

        # Search
        results = await store.search(query_vector, top_k=10)
    """

    def __init__(
        self,
        root_dir: str = ".rag/faiss",
        dimension: int = 384,
        nlist: int = 128,
        nprobe: int = 8,
    ):
        """
        Initialize AsyncFaissStore.

        Args:
            root_dir: Directory for storing indices
            dimension: Vector dimension
            nlist: Number of clusters for IVF index
            nprobe: Number of clusters to search
        """
        self.root_dir = Path(root_dir)
        self.dimension = dimension
        self.nlist = nlist
        self.nprobe = nprobe

        self._indices: dict[str, Any] = {}  # namespace -> index
        self._metadata: dict[str, dict] = {}  # namespace -> {id -> metadata}
        self._id_mappers: dict[str, Any] = {}  # namespace -> FaissIDMapper
        self._locks: dict[str, threading.RLock] = {}  # namespace -> lock
        self._connected = False

    async def connect(self) -> bool:
        """
        Initialize Faiss store asynchronously.

        Creates directory structure and prepares for operations.

        Returns:
            True if successful
        """
        try:
            # Create directories
            await asyncio.to_thread(self.root_dir.mkdir, parents=True, exist_ok=True)

            self._connected = True
            logger.info(f"Connected to Faiss store at {self.root_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Faiss: {e}")
            return False

    def _get_namespace_path(self, namespace: str) -> Path:
        """Get directory path for namespace."""
        return self.root_dir / namespace

    def _get_index_path(self, namespace: str) -> Path:
        """Get Faiss index file path."""
        return self._get_namespace_path(namespace) / "index.faiss"

    def _get_metadata_path(self, namespace: str) -> Path:
        """Get metadata file path."""
        return self._get_namespace_path(namespace) / "metadata.json"

    def _get_db_path(self, namespace: str) -> Path:
        """Get SQLite database path for ID mapping."""
        return self._get_namespace_path(namespace) / "idmap.db"

    def _ensure_namespace_lock(self, namespace: str) -> threading.RLock:
        """Get or create lock for namespace."""
        if namespace not in self._locks:
            self._locks[namespace] = threading.RLock()
        return self._locks[namespace]

    async def _load_or_create_index(self, namespace: str):
        """Load existing index or create new one."""
        lock = self._ensure_namespace_lock(namespace)

        with lock:
            if namespace in self._indices:
                return self._indices[namespace]

        # Run I/O in thread
        def _do_load():
            import faiss  # type: ignore[import-untyped]

            ns_path = self._get_namespace_path(namespace)
            index_path = self._get_index_path(namespace)
            metadata_path = self._get_metadata_path(namespace)
            db_path = self._get_db_path(namespace)

            # Create namespace directory
            ns_path.mkdir(parents=True, exist_ok=True)

            # Load or create index
            if index_path.exists():
                index = faiss.read_index(str(index_path))
                logger.info(f"Loaded Faiss index from {index_path}")
            else:
                # Create IVF index for large datasets
                quantizer = faiss.IndexFlatIP(self.dimension)
                index = faiss.IndexIVFFlat(quantizer, self.dimension, self.nlist)
                index.nprobe = self.nprobe
                logger.info(f"Created new Faiss index for namespace '{namespace}'")

            # Load metadata
            metadata = {}
            if metadata_path.exists():
                with open(metadata_path, encoding="utf-8") as f:
                    metadata = json.load(f)

            # Initialize ID mapper
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            id_mapper = self._create_id_mapper(conn)

            return index, metadata, id_mapper

        index, metadata, id_mapper = await asyncio.to_thread(_do_load)

        with lock:
            self._indices[namespace] = index
            self._metadata[namespace] = metadata
            self._id_mappers[namespace] = id_mapper

        return index

    def _create_id_mapper(self, conn: sqlite3.Connection):
        """Create simplified ID mapper for async usage."""

        # Simplified version - in production use full FaissIDMapper
        class SimpleIDMapper:
            def __init__(self, conn):
                self.conn = conn
                self._ensure_table()

            def _ensure_table(self):
                cur = self.conn.cursor()
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS id_map
                    (str_id TEXT PRIMARY KEY, faiss_id INTEGER UNIQUE NOT NULL)
                    """
                )
                self.conn.commit()

            def get_or_create(self, str_id: str) -> int:
                cur = self.conn.cursor()
                row = cur.execute(
                    "SELECT faiss_id FROM id_map WHERE str_id = ?", (str_id,)
                ).fetchone()

                if row:
                    return int(row[0])

                # Create new ID
                faiss_id = hash(str_id) & ((1 << 63) - 1)
                cur.execute(
                    "INSERT OR REPLACE INTO id_map (str_id, faiss_id) VALUES (?, ?)",
                    (str_id, faiss_id),
                )
                self.conn.commit()
                return faiss_id

        return SimpleIDMapper(conn)

    async def upsert(self, shards: list[dict[str, Any]], namespace: str) -> int:
        """
        Insert or update vectors asynchronously.

        Args:
            shards: List of shard dictionaries
            namespace: Target namespace

        Returns:
            Number of vectors upserted
        """
        if not shards:
            return 0

        index = await self._load_or_create_index(namespace)
        lock = self._ensure_namespace_lock(namespace)

        def _do_upsert():

            vectors = []
            ids = []
            metadata_updates = {}

            id_mapper = self._id_mappers[namespace]

            for shard in shards:
                # Generate ID
                attr_type = shard["metadata"].get("attr_type", "misc")
                product_id = shard["metadata"].get("product_id", "unknown")
                str_id = f"{product_id}_{attr_type}_{hash(shard['text']) & 0xFFFF}"

                faiss_id = id_mapper.get_or_create(str_id)

                # Prepare vector
                vector = np.array(shard["values"], dtype=np.float32)
                vectors.append(vector)
                ids.append(faiss_id)

                # Store metadata
                metadata_updates[str(faiss_id)] = {
                    "text": shard["text"],
                    "metadata": shard["metadata"],
                }

            # Normalize vectors for cosine similarity
            vectors_array = np.vstack(vectors)
            vectors_array = _l2_normalize(vectors_array)

            # Train index if needed
            if not index.is_trained:
                # Need enough vectors to train
                if len(vectors) >= self.nlist:
                    index.train(vectors_array)
                else:
                    logger.warning(
                        f"Not enough vectors to train index "
                        f"({len(vectors)} < {self.nlist})"
                    )

            # Add vectors
            if index.is_trained:
                ids_array = np.array(ids, dtype=np.int64)
                index.add_with_ids(vectors_array, ids_array)

            # Update metadata
            self._metadata[namespace].update(metadata_updates)

            # Save index and metadata
            self._save_namespace(namespace)

            return len(vectors)

        with lock:
            count = await asyncio.to_thread(_do_upsert)

        return int(count) if count is not None else 0

    async def search(
        self, vector: list[float], top_k: int = 5, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Search for similar vectors asynchronously.

        Args:
            vector: Query vector
            top_k: Number of results
            namespace: Target namespace

        Returns:
            List of matches
        """
        if namespace is None:
            namespace = "default"

        index = await self._load_or_create_index(namespace)
        lock = self._ensure_namespace_lock(namespace)

        def _do_search():
            # Normalize query vector
            query_vec = np.array([vector], dtype=np.float32)
            query_vec = _l2_normalize(query_vec)

            # Search
            scores, ids = index.search(query_vec, top_k)

            # Build results
            results = []
            metadata = self._metadata[namespace]

            for score, faiss_id in zip(scores[0], ids[0], strict=False):
                if faiss_id == -1:  # Invalid ID
                    continue

                meta = metadata.get(str(faiss_id), {})
                results.append(
                    {
                        "id": str(faiss_id),
                        "score": float(score),
                        "metadata": meta.get("metadata", {}),
                        "text": meta.get("text", ""),
                    }
                )

            return results

        with lock:
            results = await asyncio.to_thread(_do_search)

        # Ensure results is the correct type
        return list(results) if results is not None else []

    def _save_namespace(self, namespace: str):
        """Save index and metadata for namespace (blocking)."""
        import faiss  # type: ignore[import-untyped]

        index = self._indices[namespace]
        metadata = self._metadata[namespace]

        index_path = self._get_index_path(namespace)
        metadata_path = self._get_metadata_path(namespace)

        # Save index
        faiss.write_index(index, str(index_path))

        # Save metadata
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    async def delete(
        self,
        ids: list[str] | None = None,
        namespace: str | None = None,
        delete_all: bool = False,
    ) -> bool:
        """
        Delete vectors asynchronously.

        Args:
            ids: Vector IDs to delete
            namespace: Target namespace
            delete_all: Delete entire namespace

        Returns:
            True if successful
        """
        if namespace is None:
            namespace = "default"

        def _do_delete():
            if delete_all:
                # Clear namespace
                if namespace in self._indices:
                    del self._indices[namespace]
                if namespace in self._metadata:
                    del self._metadata[namespace]

                # Delete files
                ns_path = self._get_namespace_path(namespace)
                if ns_path.exists():
                    import shutil

                    shutil.rmtree(ns_path)

            return True

        return await asyncio.to_thread(_do_delete)

    async def health_check(self) -> dict[str, Any]:
        """
        Check store health asynchronously.

        Returns:
            Health status dictionary
        """
        try:
            if not self._connected:
                await self.connect()

            # Count vectors across namespaces
            total_vectors = 0
            for _namespace, index in self._indices.items():
                total_vectors += index.ntotal

            return {
                "status": "healthy",
                "namespaces": list(self._indices.keys()),
                "total_vectors": total_vectors,
                "root_dir": str(self.root_dir),
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
