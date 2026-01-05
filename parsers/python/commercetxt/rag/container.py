"""
RAG Dependency Injection Container.

Provides lazy-loaded embedders, vector stores, and storage backends.
"""

import os

from .interfaces.base_embedder import BaseEmbedder
from .interfaces.base_storage import BaseRealtimeStorage
from .interfaces.base_vector_store import BaseVectorStore


class RAGContainer:
    """
    Dependency Injection Container using Lazy Loading.
    No external libraries required. Ensures lightweight usage.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or dict(os.environ)

        # Cache for singletons
        self._embedder: BaseEmbedder | None = None
        self._vector_store: BaseVectorStore | None = None
        self._storage: BaseRealtimeStorage | None = None

    @property
    def embedder(self) -> BaseEmbedder:
        """Returns the configured Embedder (Singleton)."""
        if not self._embedder:
            driver_type = self.config.get("RAG_EMBEDDER", "local")

            if driver_type == "openai":
                from .drivers.openai_embedder import OpenAIEmbedder

                api_key = self.config.get("OPENAI_API_KEY")
                self._embedder = OpenAIEmbedder(
                    api_key=str(api_key) if api_key else None
                )
            else:
                from .drivers.local_embedder import LocalEmbedder

                self._embedder = LocalEmbedder()

        assert self._embedder is not None
        return self._embedder

    @property
    def vector_store(self) -> BaseVectorStore:
        """Returns the configured Vector DB (Singleton)."""
        if not self._vector_store:
            driver_type = self.config.get("RAG_VECTOR_DB", "faiss")

            if driver_type == "pinecone":
                from .drivers.pinecone_store import PineconeStore

                self._vector_store = PineconeStore(
                    api_key=self.config.get("PINECONE_API_KEY", ""),
                    index_name=self.config.get("PINECONE_INDEX", "commercetxt"),
                )
            elif driver_type == "qdrant":
                from .drivers.qdrant_store import QdrantStore

                self._vector_store = QdrantStore(
                    url=self.config.get("QDRANT_URL", "http://localhost:6333"),
                    api_key=self.config.get("QDRANT_API_KEY"),
                )
            elif driver_type == "faiss":
                from .drivers.faiss_store import FaissStore

                self._vector_store = FaissStore(
                    root_dir=self.config.get("FAISS_DIR", ".rag/faiss"),
                    dimension=int(self.config.get("EMBED_DIM", 384)),
                    nlist=int(self.config.get("FAISS_NLIST", 128)),
                    nprobe=int(self.config.get("FAISS_NPROBE", 8)),
                )

            else:
                # Fallback for testing logic without DB
                raise ValueError(f"Unknown Vector DB driver: {driver_type}")

        assert self._vector_store is not None
        return self._vector_store

    @property
    def storage(self) -> BaseRealtimeStorage:
        """Returns the Realtime Data Source."""
        if not self._storage:
            # Default to local file system for now
            from .drivers.local_storage import LocalStorage

            self._storage = LocalStorage(
                root_path=self.config.get("COMMERCETXT_ROOT", "./")
            )
        assert self._storage is not None
        return self._storage
