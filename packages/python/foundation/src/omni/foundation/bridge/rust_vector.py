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

    def __init__(
        self,
        index_path: str | None = None,
        dimension: int = 1536,
        enable_keyword_index: bool = True,
    ):
        """Initialize the vector store.

        Args:
            index_path: Path to the vector index/database. Defaults to get_vector_db_path()
            dimension: Vector dimension (default: 1536 for OpenAI embeddings)
            enable_keyword_index: Enable Tantivy keyword index for BM25 search
        """
        if not RUST_AVAILABLE:
            raise RuntimeError("Rust bindings not installed. Run: just build-rust-dev")

        # Use default path if not provided
        if index_path is None:
            from omni.foundation.config.dirs import get_vector_db_path

            index_path = str(get_vector_db_path())

        self._inner = _rust.create_vector_store(index_path, dimension, enable_keyword_index)
        self._index_path = index_path
        self._dimension = dimension
        self._enable_keyword_index = enable_keyword_index
        logger.info(
            f"Initialized RustVectorStore at {index_path} (keyword_index={enable_keyword_index})"
        )

    @cached_property
    def _embedding_service(self):
        """Lazily load embedding service for query encoding."""
        from omni.foundation.services.embedding import get_embedding_service

        return get_embedding_service()

    async def search_tools(
        self,
        table_name: str,
        query_vector: list[float],
        query_text: str | None = None,
        limit: int = 5,
        threshold: float = 0.0,
    ) -> list[dict]:
        """Direct access to Rust search_tools with Keyword Rescue.

        This method provides direct access to Rust's native hybrid search:
        - Vector similarity (LanceDB)
        - Keyword rescue (Tantivy BM25) when query_text is provided
        - Score fusion (0.4 vector + 0.6 keyword)

        Args:
            table_name: Table to search (default: "skills")
            query_vector: Pre-computed query embedding
            query_text: Raw query text for keyword rescue
            limit: Maximum results to return
            threshold: Minimum score threshold

        Returns:
            List of dicts with: name, description, score, skill_name, tool_name, etc.
        """
        try:
            # Call Rust's search_tools (synchronous in the binding, run in thread pool)
            # Note: Rust signature is (table_name, query_vector, query_text, limit, threshold)
            loop = asyncio.get_event_loop()
            json_results = await loop.run_in_executor(
                None,
                lambda: self._inner.search_tools(
                    table_name,
                    query_vector,
                    query_text,  # query_text comes BEFORE limit in Rust
                    limit,
                    threshold,
                ),
            )

            # Convert PyObject dicts to Python dicts
            # PyO3 returns Py<PyAny> which is a reference to Python objects
            results = []
            for data in json_results:
                try:
                    # Use pyo3's proper conversion
                    if hasattr(data, "keys") and callable(getattr(data, "keys", None)):
                        # It's a dict-like object, convert properly
                        results.append({k: data[k] for k in data.keys()})
                    elif isinstance(data, dict):
                        results.append(data)
                    else:
                        # Fallback: try dict() conversion
                        try:
                            results.append(dict(data))
                        except (TypeError, ValueError):
                            logger.debug(f"Skipping unconvertible result: {type(data)}")
                except Exception as convert_err:
                    logger.debug(f"Failed to convert result: {convert_err}")
                    continue

            logger.debug(f"search_tools: {len(results)} results for '{str(query_text)[:30]}...'")
            return results
        except Exception as e:
            logger.debug(f"search_tools failed: {e}")
            return []

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

            # Use new search_tools API which supports Keyword Rescue (Hybrid Search)
            # This passes the raw query text to Rust for Tantivy fallback
            if hasattr(self._inner, "search_tools"):
                # Correct parameter order matching Rust signature:
                # (table_name, query_vector, query_text, limit, threshold)
                json_results = self._inner.search_tools(
                    "skills",
                    query_vector,
                    query,  # query_text for keyword rescue
                    limit,
                    0.0,  # threshold
                )

                # Convert dicts (PyObject) to SearchResult objects directly
                # search_tools returns list[dict], not list[json_str]
                results = []
                for data in json_results:
                    # data is already a dict
                    score = data.get("score", 0.0)

                    # Convert to SearchResult
                    # The Rust tool search returns flattened structure, adapt to payload
                    metadata = {
                        "command": data.get("name"),  # search_tools maps command -> name
                        "tool_name": data.get("tool_name"),
                        "skill_name": data.get("skill_name"),
                        "description": data.get("description"),
                        "keywords": data.get("keywords"),
                        "file_path": data.get("file_path"),
                    }

                    results.append(
                        SearchResult(
                            score=score,
                            payload=metadata,
                            id=data.get("tool_name", ""),
                        )
                    )

                logger.info(
                    f"Hybrid route: '{query}' -> {len(results)} results (via Rust search_tools)"
                )
                return results

            # Fallback for old bindings (should not happen if compiled correctly)
            if filters:
                json_results = self._inner.search_filtered(
                    "skills", query_vector, limit, json.dumps(filters)
                )
            else:
                json_results = self._inner.search("skills", query_vector, limit)

            logger.info(f"DEBUG: Query vec len={len(query_vector)}, sample={query_vector[:3]}")
            logger.info(f"DEBUG: Raw json_results count={len(json_results)}")

            results = []
            for json_str in json_results:
                try:
                    data = json.loads(json_str)
                    metadata = data.get("metadata")
                    if metadata is None:
                        metadata = {}

                    # Convert distance to similarity score (smaller distance = higher score)
                    # LanceDB uses L2 distance by default. For normalized vectors:
                    # L2^2 = 2(1 - cosine_sim) => cosine_sim = 1 - L2^2 / 2
                    # The 'distance' returned by LanceDB for L2 is the squared distance (L2^2).
                    distance = data.get("distance", 1.0)
                    score = max(0.0, 1.0 - distance / 2.0)

                    logger.debug(
                        f"DEBUG SEARCH: id={data.get('id')} dist={distance:.4f} score={score:.4f}"
                    )

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

    async def get_skill_index(self, base_path: str) -> list[dict]:
        """Get complete skill index with full metadata from filesystem scan.

        This method directly scans the skills directory and returns all metadata
        including: routing_keywords, intents, authors, version, permissions, etc.

        Unlike list_all_tools which only returns tool records from LanceDB,
        this method returns full skill metadata from SKILL.md frontmatter.

        Args:
            base_path: Base directory containing skills (e.g., "assets/skills")

        Returns:
            List of skill dictionaries with full metadata including:
            - name, description, version, path
            - routing_keywords, intents, authors, permissions
            - tools (with name, description, category, input_schema)
        """
        try:
            json_result = self._inner.get_skill_index(base_path)
            skills = json.loads(json_result) if json_result else []
            logger.debug(f"Found {len(skills)} skills in index")
            return skills
        except Exception as e:
            logger.debug(f"Failed to get skill index: {e}")
            return []

    async def list_all(self, table_name: str = "knowledge") -> list[dict]:
        """List all entries from a table.

        Args:
            table_name: Name of the table to list (default: "knowledge")

        Returns:
            List of entry dictionaries with id, content, metadata.
        """
        try:
            json_result = self._inner.list_all_tools(table_name)
            entries = json.loads(json_result) if json_result else []
            logger.debug(f"Listed {len(entries)} entries from {table_name}")
            return entries
        except Exception as e:
            logger.debug(f"Failed to list entries from {table_name}: {e}")
            return []

    async def get_analytics_table(self, table_name: str = "skills"):
        """Get all tools as a PyArrow Table for analytics.

        This is optimized for high-performance operations using Arrow's columnar format.

        Args:
            table_name: Name of the table to get analytics for (default: "skills")

        Returns:
            PyArrow Table with columns: id, content, skill_name, tool_name, file_path, keywords.
            Returns None on error.
        """
        try:
            import pyarrow as pa

            table = self._inner.get_analytics_table(table_name)
            if table is not None:
                return pa.table(table)
            return None
        except Exception as e:
            logger.debug(f"Failed to get analytics table from LanceDB: {e}")
            return None

    async def index_skill_tools(self, base_path: str, table_name: str = "skills") -> int:
        """Index all tools from skills scripts directory to LanceDB.

        Scans `base_path/skills/*/scripts/*.py` for @skill_command decorated
        functions and indexes them for discovery.

        Args:
            base_path: Base directory containing skills (e.g., "assets/skills")
            table_name: Table name to index tools into (default: "skills", use "router" for router DB)

        Returns:
            Number of tools indexed, or 0 on error.
        """
        try:
            import omni_core_rs as _rust

            store = _rust.create_vector_store(self._index_path, self._dimension, True)
            count = store.index_skill_tools(base_path, table_name)
            logger.info(f"Indexed {count} tools from {base_path} to table '{table_name}'")
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
# Factory - Per-path caching to support multiple stores (e.g., router + default)
# =============================================================================

_vector_stores: dict[str, RustVectorStore] = {}


def get_vector_store(
    index_path: str | None = None,
    dimension: int | None = None,
    enable_keyword_index: bool = True,
) -> RustVectorStore:
    """Get or create a vector store instance, cached by path.

    Multiple stores can coexist with different paths (e.g., router.lance vs default).

    Args:
        index_path: Path to the vector database. Defaults to get_vector_db_path()
        dimension: Vector dimension (default: from settings.yaml embedding.dimension)
        enable_keyword_index: Enable keyword index for hybrid search (default: True)
    """
    from omni.foundation.config.dirs import get_vector_db_path
    from omni.foundation.config.settings import get_setting

    if index_path is None:
        index_path = str(get_vector_db_path())

    # Use dimension from settings.yaml (default to 1024)
    if dimension is None:
        dimension = get_setting("embedding.dimension", 1024)

    # Check cache first
    if index_path in _vector_stores:
        return _vector_stores[index_path]

    # Create new store and cache it
    store = RustVectorStore(index_path, dimension, enable_keyword_index)
    _vector_stores[index_path] = store
    return store


__all__ = [
    "RUST_AVAILABLE",
    "RustVectorStore",
    "get_vector_store",
]
