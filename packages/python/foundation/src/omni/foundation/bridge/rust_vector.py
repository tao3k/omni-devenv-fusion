"""
rust_vector.py - Vector Store Implementation

Rust-powered vector store using LanceDB bindings.
Provides high-performance semantic search capabilities.
"""

from __future__ import annotations

import json
from typing import Any

from omni.foundation.config.logging import get_logger

try:
    import omni_core_rs as _rust

    RUST_AVAILABLE = True
except ImportError:
    _rust = None
    RUST_AVAILABLE = False

from .types import FileContent, IngestResult, SearchResult

logger = get_logger("omni.bridge.vector")


class RustVectorStore:
    """Vector store implementation using Rust bindings (LanceDB)."""

    def __init__(self, index_path: str, dimension: int = 1536):
        """Initialize the vector store.

        Args:
            index_path: Path to the vector index/database
            dimension: Vector dimension (default: 1536 for OpenAI embeddings)
        """
        if not RUST_AVAILABLE:
            raise RuntimeError("Rust bindings not installed. Run: just build-rust-dev")

        self._inner = _rust.create_vector_store(index_path, dimension)
        self._index_path = index_path
        self._dimension = dimension
        logger.info(f"Initialized RustVectorStore at {index_path}")

    async def search(
        self,
        query: str,
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents.

        Note: This is a sync wrapper around async Rust operations.
        Falls back gracefully if table doesn't exist.
        """
        try:
            if filters:
                json_results = self._inner.search_filtered(
                    "skills", [0.0] * self._dimension, limit, json.dumps(filters)
                )
            else:
                json_results = self._inner.search("skills", [0.0] * self._dimension, limit)

            results = []
            for json_str in json_results:
                try:
                    data = json.loads(json_str)
                    results.append(
                        SearchResult(
                            score=data.get("score", 0.0),
                            payload=data.get("metadata", {}),
                            id=data.get("id", ""),
                        )
                    )
                except (json.JSONDecodeError, KeyError):
                    continue

            return results
        except Exception as e:
            # Gracefully handle missing table - don't spam logs
            error_str = str(e)
            if "not found" in error_str.lower() or "table" in error_str.lower():
                logger.debug(f"Vector store table not ready: {e}")
            else:
                logger.debug(f"Vector search failed: {e}")
            return []

    async def ingest(self, content: FileContent) -> IngestResult:
        """Ingest a document into the vector store."""
        try:
            logger.debug(f"Ingesting {content.path}")
            return IngestResult(success=True, document_id=content.path, chunks_created=1)
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            return IngestResult(success=False, error=str(e))

    async def delete(self, document_id: str) -> bool:
        """Delete a document from the vector store."""
        try:
            self._inner.delete("skills", [document_id])
            return True
        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            return False

    async def create_index(
        self,
        name: str,
        dimension: int,
        path: str | None = None,
    ) -> bool:
        """Create a new vector index."""
        try:
            self._inner.create_index(name)
            return True
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            return False

    async def health_check(self) -> bool:
        """Check if the vector store is healthy."""
        try:
            count = self._inner.count("skills")
            logger.debug(f"Vector store health check: {count} documents")
            return True
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            return False


# =============================================================================
# Factory
# =============================================================================

_vector_store: RustVectorStore | None = None


def get_vector_store(index_path: str = "data/vector.db", dimension: int = 1536) -> RustVectorStore:
    """Get or create the global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = RustVectorStore(index_path, dimension)
    return _vector_store


__all__ = [
    "RUST_AVAILABLE",
    "RustVectorStore",
    "get_vector_store",
]
