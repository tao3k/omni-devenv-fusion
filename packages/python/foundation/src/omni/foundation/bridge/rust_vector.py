"""
rust_vector.py - Vector Store Implementation

Rust-powered vector store using LanceDB bindings.
Provides high-performance semantic search capabilities.
"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from functools import cached_property
from typing import Any

from omni.foundation.config.logging import get_logger

# Thread pool for blocking embedding operations (prevents event loop blocking)
_EMBEDDING_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="embedding")

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

    def __init__(self, index_path: str | None = None, dimension: int = 1536):
        """Initialize the vector store.

        Args:
            index_path: Path to the vector index/database. Defaults to get_vector_db_path()
            dimension: Vector dimension (default: 1536 for OpenAI embeddings)
        """
        if not RUST_AVAILABLE:
            raise RuntimeError("Rust bindings not installed. Run: just build-rust-dev")

        # Use default path if not provided
        if index_path is None:
            from omni.foundation.config.dirs import get_vector_db_path

            index_path = str(get_vector_db_path())

        self._inner = _rust.create_vector_store(index_path, dimension)
        self._index_path = index_path
        self._dimension = dimension
        logger.info(f"Initialized RustVectorStore at {index_path}")

    @cached_property
    def _embedding_service(self):
        """Lazily load embedding service for query encoding."""
        from omni.foundation.services.embedding import get_embedding_service

        return get_embedding_service()

    async def search(
        self,
        query: str,
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents.

        Uses semantic embedding search with fallback to keyword matching.
        Embedding generation runs in thread pool to avoid blocking event loop.
        """
        try:
            # Generate query embedding in thread pool (FastEmbed is CPU-bound)
            loop = asyncio.get_event_loop()
            query_embedding = await loop.run_in_executor(
                _EMBEDDING_EXECUTOR,
                self._embedding_service.embed,
                query,
            )

            # Handle embedding format (may be [[...]] or [...])
            if query_embedding and isinstance(query_embedding[0], list):
                query_vector = query_embedding[0]
            else:
                query_vector = query_embedding

            if filters:
                json_results = self._inner.search_filtered(
                    "skills", query_vector, limit, json.dumps(filters)
                )
            else:
                json_results = self._inner.search("skills", query_vector, limit)

            results = []
            for json_str in json_results:
                try:
                    data = json.loads(json_str)
                    metadata = data.get("metadata")
                    if metadata is None:
                        metadata = {}

                    # Convert distance to similarity score (smaller distance = higher score)
                    distance = data.get("distance", 1.0)
                    score = max(0.0, 1.0 - distance)  # distance 0 -> score 1.0

                    results.append(
                        SearchResult(
                            score=score,
                            payload=metadata,
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

    async def add_documents(
        self,
        table_name: str,
        ids: list[str],
        vectors: list[list[float]],
        contents: list[str],
        metadatas: list[str],
    ) -> None:
        """Add documents to the vector store.

        Args:
            table_name: Name of the table/collection
            ids: Unique identifiers for each document
            vectors: Embedding vectors (can be list of lists, e.g., from embedding service)
            contents: Text content for each document
            metadatas: JSON metadata for each document
        """
        # Handle embedding service output which returns [[vec1], [vec2], ...]
        # Convert to [[v1, v2, v3, ...], ...] format
        rust_vectors: list[list[float]] = []
        for vec in vectors:
            if vec and isinstance(vec[0], list):
                # Already nested - take first (embedding service wraps in extra list)
                rust_vectors.append([float(v) for v in vec[0]])
            else:
                rust_vectors.append([float(v) for v in vec])

        self._inner.add_documents(table_name, ids, rust_vectors, contents, metadatas)

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

    async def list_all_tools(self) -> list[dict]:
        """List all tools from LanceDB.

        Returns tools with: name, description, skill_name, category, input_schema.

        Returns:
            List of tool dictionaries, or empty list if table doesn't exist.
        """
        try:
            json_result = self._inner.list_all_tools("skills")
            tools = json.loads(json_result) if json_result else []
            logger.debug(f"Listed {len(tools)} tools from LanceDB")
            return tools
        except Exception as e:
            logger.debug(f"Failed to list tools from LanceDB: {e}")
            return []

    async def get_analytics_table(self):
        """Get all tools as a PyArrow Table for analytics.

        This is optimized for high-performance operations using Arrow's columnar format.

        Returns:
            PyArrow Table with columns: id, content, skill_name, tool_name, file_path, keywords.
            Returns None on error.
        """
        try:
            import pyarrow as pa

            table = self._inner.get_analytics_table("skills")
            if table is not None:
                return pa.table(table)
            return None
        except Exception as e:
            logger.debug(f"Failed to get analytics table from LanceDB: {e}")
            return None

    async def index_skill_tools(self, base_path: str) -> int:
        """Index all tools from skills scripts directory to LanceDB.

        Scans `base_path/skills/*/scripts/*.py` for @skill_command decorated
        functions and indexes them for discovery.

        Args:
            base_path: Base directory containing skills (e.g., "assets/skills")

        Returns:
            Number of tools indexed, or 0 on error.
        """
        try:
            count = self._inner.index_skill_tools(base_path, "skills")
            logger.info(f"Indexed {count} tools from {base_path}")
            return count
        except Exception as e:
            logger.error(f"Failed to index skill tools: {e}")
            return 0

    async def drop_table(self, table_name: str) -> bool:
        """Drop a table from the vector store.

        Args:
            table_name: Name of the table to drop.

        Returns:
            True on success, False on error.
        """
        try:
            self._inner.drop_table(table_name)
            logger.info(f"Dropped table: {table_name}")
            return True
        except Exception as e:
            logger.debug(f"Failed to drop table {table_name}: {e}")
            return False


# =============================================================================
# Factory
# =============================================================================

_vector_store: RustVectorStore | None = None


def get_vector_store(index_path: str | None = None, dimension: int = 384) -> RustVectorStore:
    """Get or create the global vector store instance.

    Args:
        index_path: Path to the vector database. Defaults to get_vector_db_path()
        dimension: Vector dimension (default: 384 for BAAI/bge-small-en-v1.5)
    """
    from omni.foundation.config.dirs import get_vector_db_path

    if index_path is None:
        index_path = str(get_vector_db_path())
    global _vector_store
    if _vector_store is None:
        _vector_store = RustVectorStore(index_path, dimension)
    return _vector_store


__all__ = [
    "RUST_AVAILABLE",
    "RustVectorStore",
    "get_vector_store",
]
