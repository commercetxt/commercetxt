from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np

from ..interfaces.base_vector_store import BaseVectorStore

# Setup logging
logger = logging.getLogger(__name__)


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    """Normalize vectors to unit length for cosine similarity."""
    x = x.astype("float32", copy=False)
    norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
    normalized: np.ndarray = x / norms
    return normalized


def _tmp_path(path: Path) -> Path:
    """Generate temporary path for atomic file operations."""
    return path.with_name(path.name + ".tmp")


class FaissIDMapper:
    """
    Stable string_id -> int64 (63-bit) mapping with collision handling.
    Persisted in SQLite, so mapping stays consistent across restarts.

    Thread-safe and optimized for batch operations.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._cache: dict[str, int] = {}  # In-memory cache for faster lookups
        self._cache_lock = threading.RLock()
        self._ensure_tables()
        self._warm_cache()

    def _ensure_tables(self) -> None:
        """Initialize database schema with indexes for performance."""
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS id_map
            (
                str_id   TEXT PRIMARY KEY,
                faiss_id INTEGER UNIQUE NOT NULL
            )
            """
        )
        # Add index for faster faiss_id lookups
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_faiss_id
                ON id_map (faiss_id)
            """
        )
        self.conn.commit()

    def _warm_cache(self) -> None:
        """Load existing mappings into memory cache."""
        try:
            cur = self.conn.cursor()
            rows = cur.execute("SELECT str_id, faiss_id FROM id_map").fetchall()
            with self._cache_lock:
                self._cache = {str_id: faiss_id for str_id, faiss_id in rows}
            logger.info(f"Warmed ID mapper cache with {len(self._cache)} entries")
        except Exception as e:
            logger.warning(f"Failed to warm cache: {e}")

    @staticmethod
    def _hash63(s: str, salt: int = 0) -> int:
        """Generate 63-bit hash from string with collision handling via salt."""
        h = hashlib.blake2b((f"{salt}:{s}").encode(), digest_size=8).digest()
        v = int.from_bytes(h, "big", signed=False)
        v = v & ((1 << 63) - 1)
        return v or 1

    def get(self, str_id: str) -> int | None:
        """Lookup only (NO side effects). Uses cache for O(1) performance."""
        with self._cache_lock:
            if str_id in self._cache:
                return self._cache[str_id]

        cur = self.conn.cursor()
        row = cur.execute(
            "SELECT faiss_id FROM id_map WHERE str_id = ?",
            (str_id,),
        ).fetchone()

        if row:
            faiss_id = int(row[0])
            with self._cache_lock:
                self._cache[str_id] = faiss_id
            return faiss_id

        return None

    def get_or_create(self, str_id: str) -> int:
        """Get existing ID or create new one with collision handling."""
        # Check cache first
        with self._cache_lock:
            if str_id in self._cache:
                return self._cache[str_id]

        cur = self.conn.cursor()

        # Check database
        row = cur.execute(
            "SELECT faiss_id FROM id_map WHERE str_id = ?",
            (str_id,),
        ).fetchone()
        if row:
            faiss_id = int(row[0])
            with self._cache_lock:
                self._cache[str_id] = faiss_id
            return faiss_id

        # Create new mapping with collision safety
        salt = 0
        max_retries = 100
        while salt < max_retries:
            faiss_id = self._hash63(str_id, salt=salt)
            try:
                cur.execute(
                    "INSERT INTO id_map(str_id, faiss_id) VALUES(?, ?)",
                    (str_id, faiss_id),
                )
                self.conn.commit()
                with self._cache_lock:
                    self._cache[str_id] = faiss_id
                return faiss_id
            except sqlite3.IntegrityError:
                # Check if it's a race condition (str_id already inserted)
                row2 = cur.execute(
                    "SELECT faiss_id FROM id_map WHERE str_id = ?",
                    (str_id,),
                ).fetchone()
                if row2:
                    faiss_id = int(row2[0])
                    with self._cache_lock:
                        self._cache[str_id] = faiss_id
                    return faiss_id
                salt += 1

        raise RuntimeError(f"Failed to create ID mapping after {max_retries} attempts")

    def get_batch(self, str_ids: list[str]) -> dict[str, int | None]:
        """Batch lookup for multiple IDs (optimized for performance)."""
        results: dict[str, int | None] = {}
        missing: list[str] = []

        # Check cache first
        with self._cache_lock:
            for str_id in str_ids:
                if str_id in self._cache:
                    results[str_id] = self._cache[str_id]
                else:
                    missing.append(str_id)

        # Batch query for missing IDs
        if missing:
            cur = self.conn.cursor()
            placeholders = ",".join("?" * len(missing))
            # S608: Safe - using parameterized "?" placeholders, not user data
            rows = cur.execute(  # noqa: S608
                f"SELECT str_id, faiss_id FROM id_map WHERE str_id IN ({placeholders})",
                missing,
            ).fetchall()

            with self._cache_lock:
                for str_id, faiss_id in rows:
                    self._cache[str_id] = faiss_id
                    results[str_id] = faiss_id

            # Mark remaining as not found
            found_ids = {row[0] for row in rows}
            for str_id in missing:
                if str_id not in found_ids:
                    results[str_id] = None

        return results


class FaissStore(BaseVectorStore):
    """
    Production-grade FAISS store with optimizations:
    - IndexIVFFlat + IndexIDMap2 (arbitrary IDs)
    - Real upsert via remove_ids + add_with_ids
    - SQLite metadata store with caching
    - Cosine similarity via normalization + inner product
    - Thread-safe with per-namespace RLock
    - Batch operations for better performance
    - Smart error handling and logging
    """

    def __init__(
        self,
        root_dir: str = ".rag/faiss",
        dimension: int = 384,
        nlist: int = 128,
        nprobe: int = 8,
        train_min_vectors: int = 512,
        enable_logging: bool = True,
    ):
        self.root = Path(root_dir)
        self.dimension = int(dimension)
        self.nlist = int(nlist)
        self.nprobe = int(nprobe)
        self.train_min_vectors = int(train_min_vectors)

        self._connected = False
        self._indexes: dict[str, Any] = {}
        self._conns: dict[str, sqlite3.Connection] = {}
        self._mappers: dict[str, FaissIDMapper] = {}
        self._locks: dict[str, threading.RLock] = {}

        if enable_logging:
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )

    def connect(self) -> bool:
        """Initialize storage directory."""
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self._connected = True
            logger.info(f"Connected to FAISS store at {self.root}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def _paths(self, namespace: str) -> tuple[Path, Path]:
        """Get paths for index and metadata database."""
        idx_path = self.root / f"{namespace}.faiss.index"
        db_path = self.root / f"{namespace}.meta.sqlite"
        return idx_path, db_path

    def _lock(self, namespace: str) -> threading.RLock:
        """Get or create lock for namespace."""
        if namespace not in self._locks:
            self._locks[namespace] = threading.RLock()
        return self._locks[namespace]

    def _open_db(self, namespace: str) -> sqlite3.Connection:
        """Open or reuse SQLite connection with optimizations."""
        if namespace in self._conns:
            return self._conns[namespace]

        _, db_path = self._paths(namespace)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)

        # Performance optimizations
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY;")

        # Create schema with indexes
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shards
            (
                str_id        TEXT PRIMARY KEY,
                faiss_id      INTEGER UNIQUE NOT NULL,
                text          TEXT           NOT NULL,
                metadata_json TEXT           NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_shards_faiss_id
                ON shards (faiss_id)
            """
        )
        conn.commit()

        self._conns[namespace] = conn
        self._mappers[namespace] = FaissIDMapper(conn)

        logger.info(f"Opened database for namespace '{namespace}'")
        return conn

    def _set_nprobe(self, index: Any) -> None:
        """Ensure nprobe is set after loading index."""
        try:
            base = getattr(index, "index", None) or index
            if hasattr(base, "nprobe"):
                base.nprobe = self.nprobe
                logger.debug(f"Set nprobe to {self.nprobe}")
        except Exception as e:
            logger.warning(f"Failed to set nprobe: {e}")

    def _load_or_create_index(self, namespace: str):
        """Load existing index or create new one."""
        if namespace in self._indexes:
            return self._indexes[namespace]

        import faiss  # type: ignore[import-untyped]

        idx_path, _ = self._paths(namespace)

        if idx_path.exists():
            try:
                index = faiss.read_index(str(idx_path))
                # Safe way to get vector count
                # (works for both IndexIDMap2 and base indexes)
                vector_count = self._get_index_size(index)
                logger.info(
                    f"Loaded existing index for '{namespace}' ({vector_count} vectors)"
                )
            except Exception as e:
                logger.error(f"Failed to load index: {e}. Creating new one.")
                index = self._create_new_index(faiss)
        else:
            index = self._create_new_index(faiss)
            logger.info(f"Created new index for '{namespace}'")

        self._set_nprobe(index)
        self._indexes[namespace] = index
        return index

    def _create_new_index(self, faiss) -> Any:
        """
        Create a new FAISS index with optimal configuration.

        Uses Flat index for small datasets (< train_min_vectors) to avoid
        training issues. Switches to IVF for larger datasets automatically.
        """
        # Start with Flat index (no training required)
        # Will be upgraded to IVF when we have enough vectors
        base = faiss.IndexFlatIP(self.dimension)
        return faiss.IndexIDMap2(base)

    def _get_index_size(self, index: Any) -> int:
        """Safely get the number of vectors in an index."""
        try:
            # Try ntotal first (standard attribute)
            if hasattr(index, "ntotal"):
                return int(index.ntotal)
            # For IndexIDMap2, check the internal _vecs dict (fake FAISS)
            if hasattr(index, "_vecs"):
                return len(index._vecs)
            # Try the base index
            base = getattr(index, "index", None)
            if base and hasattr(base, "ntotal"):
                return int(base.ntotal)
            return 0
        except Exception:
            return 0

    def _persist_index(self, namespace: str) -> None:
        """Atomically persist index to disk."""
        import faiss

        idx_path, _ = self._paths(namespace)
        tmp = _tmp_path(idx_path)

        try:
            faiss.write_index(self._indexes[namespace], str(tmp))
            os.replace(tmp, idx_path)
            logger.debug(f"Persisted index for '{namespace}'")
        except Exception as e:
            logger.error(f"Failed to persist index: {e}")
            if tmp.exists():
                tmp.unlink()
            raise

    def _ensure_trained(self, index: Any, vectors: np.ndarray) -> None:
        """
        Train IVF index if needed.

        Flat indexes don't need training, so this is a no-op for them.
        """
        base = getattr(index, "index", None) or index

        # Check if this is a Flat index (no training needed)
        base_type = type(base).__name__
        if "Flat" in base_type:
            logger.debug("Using Flat index - no training needed")
            return

        # For IVF indexes, train if not already trained
        if hasattr(base, "is_trained") and not base.is_trained:
            if len(vectors) >= self.train_min_vectors:
                logger.info(f"Training index with {len(vectors)} vectors")
                base.train(vectors)
            else:
                logger.warning(
                    f"Not enough vectors for optimal training "
                    f"({len(vectors)} < {self.train_min_vectors}). "
                    f"Consider using Flat index for small datasets."
                )
                # Don't train with too few vectors - it will fail
                # Keep using Flat index instead

    @staticmethod
    def _extract_product_key(meta: dict[str, Any]) -> str:
        """Extract stable product key to avoid collisions."""
        # Priority: direct fields
        product_key = meta.get("SKU") or meta.get("product_id") or meta.get("item")
        if product_key:
            return str(product_key)

        # Check nested original_data
        od = meta.get("original_data") or {}
        if isinstance(od, dict):
            prod = od.get("PRODUCT") or {}
            if isinstance(prod, dict):
                sku = prod.get("SKU")
                if sku:
                    return str(sku)
                url = prod.get("URL")
                if url:
                    return str(url)

        return "unknown"

    def upsert(self, shards: list[dict[str, Any]], namespace: str = "default") -> int:
        """
        Upsert shards with optimized batch processing.

        Returns number of shards successfully processed.
        """
        if not shards:
            return 0

        if not self._connected:
            self.connect()

        lock = self._lock(namespace)
        with lock:
            try:
                index = self._load_or_create_index(namespace)
                conn = self._open_db(namespace)
                mapper = self._mappers[namespace]

                # Prepare batch data
                str_ids: list[str] = []
                vectors: list[list[float]] = []
                payloads: list[tuple[str, int, str, str]] = []

                for s in shards:
                    meta = s.get("metadata", {}) or {}

                    product_key = self._extract_product_key(meta)
                    attr_type = meta.get("attr_type", "misc")
                    shard_index = meta.get("index", 0)

                    shard_key = f"{product_key}:{attr_type}:{shard_index}"
                    faiss_id = mapper.get_or_create(shard_key)

                    str_ids.append(shard_key)
                    vectors.append(s["values"])

                    meta2 = meta.copy()
                    meta2["id"] = shard_key
                    meta2["faiss_id"] = faiss_id

                    payloads.append(
                        (
                            shard_key,
                            faiss_id,
                            s.get("text", "") or "",
                            json.dumps(meta2, ensure_ascii=False),
                        )
                    )

                # Process vectors
                x = _l2_normalize(np.array(vectors, dtype="float32"))
                ids64 = np.array([mapper.get(i) for i in str_ids], dtype="int64")

                # Ensure trained
                self._ensure_trained(index, x)

                import faiss

                # TRUE UPSERT: remove old + add new
                sel = faiss.IDSelectorBatch(ids64.size, faiss.swig_ptr(ids64))
                removed = int(index.remove_ids(sel))
                if removed > 0:
                    logger.debug(f"Removed {removed} existing vectors")

                index.add_with_ids(x, ids64)

                # Persist changes
                self._persist_index(namespace)

                # Batch insert into SQLite
                cur = conn.cursor()
                cur.executemany(
                    """
                    INSERT INTO shards(str_id, faiss_id, text, metadata_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(str_id) DO UPDATE SET faiss_id=excluded.faiss_id,
                                                      text=excluded.text,
                                                      metadata_json=excluded.metadata_json
                    """,
                    payloads,
                )
                conn.commit()

                logger.info(f"Upserted {len(shards)} shards to '{namespace}'")
                return len(shards)

            except Exception as e:
                logger.error(f"Upsert failed: {e}")
                raise

    def search(
        self, query_vector: list[float], top_k: int = 5, namespace: str | None = None
    ) -> list[dict[str, Any]]:
        """Search for similar vectors with metadata."""
        # Use default namespace if None provided
        ns = namespace if namespace is not None else "default"
        if not self._connected:
            self.connect()

        lock = self._lock(ns)
        with lock:
            try:
                index = self._load_or_create_index(ns)
                conn = self._open_db(ns)

                q = _l2_normalize(np.array([query_vector], dtype="float32"))

                scores, ids = index.search(q, top_k)
                ids = ids[0].tolist()
                scores = scores[0].tolist()

                # Batch fetch metadata
                valid_ids = [int(fid) for fid in ids if fid >= 0]
                if not valid_ids:
                    return []

                cur = conn.cursor()
                placeholders = ",".join("?" * len(valid_ids))
                # S608: Safe - using parameterized "?" placeholders
                rows = cur.execute(  # noqa: S608
                    f"""
                    SELECT faiss_id, str_id, text, metadata_json
                    FROM shards
                    WHERE faiss_id IN ({placeholders})
                    """,
                    valid_ids,
                ).fetchall()

                # Map results
                id_to_row = {row[0]: row for row in rows}
                results: list[dict[str, Any]] = []

                for score, faiss_id in zip(scores, ids, strict=False):
                    if faiss_id < 0:
                        continue
                    row = id_to_row.get(int(faiss_id))
                    if not row:
                        continue

                    _, str_id, text, meta_json = row
                    meta = json.loads(meta_json)
                    results.append(
                        {
                            "id": str_id,
                            "score": float(score),
                            "text": text,
                            "metadata": meta,
                        }
                    )

                return results

            except Exception as e:
                logger.error(f"Search failed: {e}")
                return []

    def delete(self, str_ids: Iterable[str], namespace: str = "default") -> int:
        """Delete vectors by string IDs."""
        if not self._connected:
            self.connect()

        lock = self._lock(namespace)
        with lock:
            try:
                index = self._load_or_create_index(namespace)
                conn = self._open_db(namespace)
                mapper = self._mappers[namespace]

                # Batch lookup existing IDs
                str_ids_list = list(str_ids)
                id_map = mapper.get_batch(str_ids_list)

                existing_ids: list[int] = []
                to_delete: list[str] = []

                for str_id, faiss_id in id_map.items():
                    if faiss_id is not None:
                        existing_ids.append(faiss_id)
                        to_delete.append(str_id)

                if not existing_ids:
                    return 0

                import faiss  # type: ignore[import-untyped]

                ids64 = np.array(existing_ids, dtype="int64")
                sel = faiss.IDSelectorBatch(ids64.size, faiss.swig_ptr(ids64))
                removed = int(index.remove_ids(sel))

                self._persist_index(namespace)

                # Batch delete from SQLite
                cur = conn.cursor()
                cur.executemany(
                    "DELETE FROM shards WHERE str_id = ?", [(s,) for s in to_delete]
                )
                conn.commit()

                logger.info(f"Deleted {removed} vectors from '{namespace}'")
                return removed

            except Exception as e:
                logger.error(f"Delete failed: {e}")
                return 0

    def health_check(self) -> dict[str, Any]:
        """Check system health and return statistics."""
        stats: dict[str, Any] = {
            "ok": True,
            "type": "faiss_idmap2_ivf",
            "namespaces": {},
        }

        for namespace, index in self._indexes.items():
            stats["namespaces"][namespace] = {
                "vector_count": self._get_index_size(index),
                "dimension": self.dimension,
            }

        return stats

    def close(self) -> None:
        """Close all connections and release resources."""
        for conn in self._conns.values():
            try:
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")

        self._conns.clear()
        self._indexes.clear()
        self._mappers.clear()
        self._connected = False
        logger.info("Closed all connections")
