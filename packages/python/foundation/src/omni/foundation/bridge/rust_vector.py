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

from .types import FileContent, IngestResult

# Thread pool for blocking embedding operations (prevents event loop blocking)
_EMBEDDING_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="embedding")

try:
    import omni_core_rs as _rust

    RUST_AVAILABLE = True
except ImportError:
    _rust = None
    RUST_AVAILABLE = False

logger = get_logger("omni.bridge.vector")

# Bounded defaults when settings.yaml has null (avoids unbounded LanceDB cache growth in long-lived MCP)
_DEFAULT_INDEX_CACHE_BYTES = 256 * 1024 * 1024  # 256 MiB
_DEFAULT_MAX_CACHED_TABLES = 8


def _list_of_dicts_to_table(rows: list[dict[str, Any]]) -> Any:
    """Convert list of dicts to pyarrow.Table; nested dict/list values are JSON-encoded."""
    if not rows:
        import pyarrow as pa

        return pa.table({})
    import pyarrow as pa

    all_keys: set[str] = set()
    for r in rows:
        all_keys.update(r.keys())
    columns: dict[str, list[Any]] = {k: [] for k in sorted(all_keys)}
    for row in rows:
        for k in columns:
            v = row.get(k)
            if isinstance(v, (dict, list)):
                columns[k].append(json.dumps(v) if v is not None else None)
            else:
                columns[k].append(v)
    return pa.table({k: pa.array(columns[k]) for k in columns})


def _confidence_profile_json() -> str:
    """Build JSON payload for Rust-side confidence calibration.

    Source of truth is `router.search.profiles` + `router.search.active_profile`.
    """
    from omni.foundation.config.settings import get_setting

    profile = {
        "high_threshold": 0.75,
        "medium_threshold": 0.5,
        "high_base": 0.90,
        "high_scale": 0.05,
        "high_cap": 0.99,
        "medium_base": 0.60,
        "medium_scale": 0.30,
        "medium_cap": 0.89,
        "low_floor": 0.10,
    }
    active_name = str(get_setting("router.search.active_profile"))
    profiles = get_setting("router.search.profiles")
    if isinstance(profiles, dict):
        selected = profiles.get(active_name)
        if isinstance(selected, dict):
            for key, value in selected.items():
                if key in profile:
                    profile[key] = float(value)
    return json.dumps(profile)


def _rerank_enabled() -> bool:
    """Resolve rerank flag from unified search settings."""
    from omni.foundation.config.settings import get_setting

    return bool(get_setting("router.search.rerank"))


class RustVectorStore:
    """Vector store implementation using Rust bindings (LanceDB)."""

    def __init__(
        self,
        index_path: str | None = None,
        dimension: int | None = None,
        enable_keyword_index: bool = True,
        index_cache_size_bytes: int | None = None,
        max_cached_tables: int | None = None,
    ):
        """Initialize the vector store.

        Args:
            index_path: Path to the vector index/database. Defaults to get_vector_db_path()
            dimension: Vector dimension. If None, uses get_effective_embedding_dimension()
                (which considers truncate_dim from settings.yaml).
            enable_keyword_index: Enable Tantivy keyword index for BM25 search
            index_cache_size_bytes: Optional LanceDB index cache size in bytes.
                If None, falls back to settings.yaml vector.index_cache_size_bytes.
            max_cached_tables: Optional cap on in-memory dataset cache (LRU eviction when exceeded).
                Phase 2: use e.g. 2 or 4 for memory-constrained or many-table setups.
        """
        if not RUST_AVAILABLE:
            raise RuntimeError("Rust bindings not installed. Run: just build-rust-dev")

        # Use effective embedding dimension if not provided (considers truncate_dim)
        if dimension is None:
            from omni.foundation.services.index_dimension import (
                get_effective_embedding_dimension,
            )

            dimension = get_effective_embedding_dimension()

        # Use default path if not provided
        if index_path is None:
            from omni.foundation.config.dirs import get_vector_db_path

            index_path = str(get_vector_db_path())

        # Index cache: explicit arg overrides settings.yaml. Use bounded default when null to avoid MCP memory growth.
        if index_cache_size_bytes is None:
            from omni.foundation.config.settings import get_setting

            index_cache_size_bytes = get_setting("vector.index_cache_size_bytes")
        if index_cache_size_bytes is not None:
            index_cache_size_bytes = int(index_cache_size_bytes)
        else:
            index_cache_size_bytes = _DEFAULT_INDEX_CACHE_BYTES

        # Phase 2: bounded dataset cache (LRU). Use bounded default when null so tables are evicted.
        if max_cached_tables is None:
            from omni.foundation.config.settings import get_setting

            max_cached_tables = get_setting("vector.max_cached_tables")
        if max_cached_tables is not None:
            max_cached_tables = int(max_cached_tables)
        else:
            max_cached_tables = _DEFAULT_MAX_CACHED_TABLES

        self._inner = _rust.create_vector_store(
            index_path,
            dimension,
            enable_keyword_index,
            index_cache_size_bytes,
            max_cached_tables,
        )
        self._index_path = index_path
        self._dimension = dimension
        self._enable_keyword_index = enable_keyword_index
        self._index_cache_size_bytes = index_cache_size_bytes
        self._max_cached_tables = max_cached_tables
        logger.info(
            f"Initialized RustVectorStore at {index_path} (keyword_index={enable_keyword_index})"
        )

    def _default_table_name(self) -> str:
        """Infer default table name from database file path."""
        from pathlib import Path

        name = Path(self._index_path).name.lower()
        if name.endswith("router.lance"):
            return "router"
        return "skills"

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
        confidence_profile: dict[str, float] | None = None,
        rerank: bool | None = None,
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
            confidence_profile: Optional explicit confidence calibration profile.
            rerank: Optional override for Rust metadata-aware rerank stage.
                None uses `router.search.rerank`.

        Returns:
            List of dicts with: name, description, score, skill_name, tool_name, etc.
        """
        try:
            rerank_enabled = _rerank_enabled() if rerank is None else rerank
            loop = asyncio.get_running_loop()

            # Prefer IPC path when available: zero-copy Arrow → ToolSearchPayload batch parse
            if hasattr(self._inner, "search_tools_ipc"):
                try:
                    ipc_bytes = await loop.run_in_executor(
                        None,
                        lambda: self._inner.search_tools_ipc(
                            table_name,
                            query_vector,
                            query_text,
                            limit,
                            threshold,
                            rerank_enabled,
                        ),
                    )
                    import io

                    import pyarrow as pa
                    from omni.foundation.services.vector_schema import (
                        ToolSearchPayload,
                    )

                    table = pa.ipc.open_stream(io.BytesIO(ipc_bytes)).read_all()
                    payloads = ToolSearchPayload.from_arrow_table(table)
                    results = [p.model_dump(by_alias=True) for p in payloads]
                    logger.debug(
                        f"search_tools (IPC): {len(results)} results for '{str(query_text)[:30]}...'"
                    )
                    return results
                except Exception as ipc_err:
                    logger.debug(f"search_tools_ipc failed, falling back to JSON: {ipc_err}")

            # Fallback: Rust search_tools returns list of dicts (PyObject)
            confidence_profile_json = (
                json.dumps(confidence_profile, sort_keys=True)
                if confidence_profile is not None
                else _confidence_profile_json()
            )
            json_results = await loop.run_in_executor(
                None,
                lambda: self._inner.search_tools(
                    table_name,
                    query_vector,
                    query_text,
                    limit,
                    threshold,
                    confidence_profile_json,
                    rerank_enabled,
                ),
            )

            results = []
            for data in json_results:
                try:
                    if hasattr(data, "keys") and callable(getattr(data, "keys", None)):
                        candidate = {k: data[k] for k in data}
                    elif isinstance(data, dict):
                        candidate = dict(data)
                    else:
                        try:
                            candidate = dict(data)
                        except (TypeError, ValueError):
                            logger.debug(f"Skipping unconvertible result: {type(data)}")
                            continue
                    results.append(candidate)
                except Exception as convert_err:
                    logger.debug(f"Failed to convert result: {convert_err}")
                    continue

            logger.debug(f"search_tools: {len(results)} results for '{str(query_text)[:30]}...'")
            return results
        except Exception as e:
            logger.debug(f"search_tools failed: {e}")
            return []

    async def agentic_search(
        self,
        table_name: str,
        query_vector: list[float],
        query_text: str | None = None,
        limit: int = 5,
        threshold: float = 0.0,
        intent: str | None = None,
        confidence_profile: dict[str, float] | None = None,
        rerank: bool | None = None,
        skill_name_filter: str | None = None,
        category_filter: str | None = None,
        semantic_weight: float | None = None,
        keyword_weight: float | None = None,
    ) -> list[dict]:
        """Intent-aware tool search (exact / semantic / hybrid).

        Args:
            table_name: Table to search (e.g. "skills").
            query_vector: Pre-computed query embedding.
            query_text: Raw query text for keyword path / hybrid.
            limit: Max results.
            threshold: Minimum score threshold.
            intent: "exact" (keyword-only when query_text set), "semantic" (vector-only),
                "hybrid" or "category" (default: vector + keyword fusion).
            confidence_profile: Optional confidence calibration; None uses router profile.
            rerank: None uses router.search.rerank.
            skill_name_filter: Optional; restrict results to tools from this skill (e.g. "git").
            category_filter: Optional; restrict results to this category.
            semantic_weight: Override vector weight for RRF fusion (None uses Rust default 1.0).
            keyword_weight: Override keyword weight for RRF fusion (None uses Rust default 1.5).

        Returns:
            List of tool result dicts (same shape as search_tools), with confidence.
        """
        try:
            confidence_profile_json = (
                json.dumps(confidence_profile, sort_keys=True)
                if confidence_profile is not None
                else _confidence_profile_json()
            )
            rerank_enabled = _rerank_enabled() if rerank is None else rerank
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None,
                lambda: self._inner.agentic_search(
                    table_name,
                    query_vector,
                    query_text,
                    limit,
                    threshold,
                    intent,
                    confidence_profile_json,
                    rerank_enabled,
                    skill_name_filter,
                    category_filter,
                    semantic_weight,
                    keyword_weight,
                ),
            )
            # Return raw Rust shape so callers (e.g. hybrid_search, indexer) parse once.
            results: list[dict[str, Any]] = []
            for data in raw:
                try:
                    candidate = (
                        {k: data[k] for k in data}
                        if hasattr(data, "keys") and callable(getattr(data, "keys", None))
                        else dict(data)
                    )
                    results.append(candidate)
                except Exception:
                    continue
            return results
        except Exception as e:
            logger.debug(f"agentic_search failed: {e}")
            return []

    def search_optimized(
        self,
        table_name: str,
        query_vector: list[float],
        limit: int,
        options_json: str | None = None,
    ) -> list[str]:
        """Vector search; returns list of JSON strings (one per row)."""
        if not hasattr(self._inner, "search_optimized"):
            raise RuntimeError(
                "VectorStore binding missing search_optimized (upgrade omni-core-rs)"
            )
        return self._inner.search_optimized(table_name, query_vector, limit, options_json)

    def search_optimized_ipc(
        self,
        table_name: str,
        query_vector: list[float],
        limit: int,
        options_json: str | None = None,
        projection: list[str] | None = None,
    ) -> bytes:
        """Search and return Arrow IPC stream bytes (single RecordBatch) for zero-copy consumption.

        When ``projection`` is set (e.g. ["id", "content", "_distance"]), only those columns
        are included in the batch (smaller payload; useful for batch search with 100+ rows).
        Use: ``pyarrow.ipc.open_stream(io.BytesIO(bytes)).read_all()`` to get a pyarrow.Table.
        See docs/reference/search-result-batch-contract.md.
        """
        if not hasattr(self._inner, "search_optimized_ipc"):
            raise RuntimeError(
                "VectorStore binding missing search_optimized_ipc (upgrade omni-core-rs)"
            )
        if projection is not None:
            opts: dict[str, Any] = {}
            if options_json:
                opts = json.loads(options_json)
            opts["projection"] = projection
            options_json = json.dumps(opts, sort_keys=True)
        return self._inner.search_optimized_ipc(table_name, query_vector, limit, options_json)

    def get_search_profile(self) -> dict[str, Any]:
        """Return Rust-owned hybrid search profile."""
        default_profile = {
            "semantic_weight": 1.0,
            "keyword_weight": 1.5,
            "rrf_k": 10,
            "implementation": "rust-native-weighted-rrf",
            "strategy": "weighted_rrf_field_boosting",
            "field_boosting": {"name_token_boost": 0.5, "exact_phrase_boost": 1.5},
        }
        try:
            if hasattr(self._inner, "get_search_profile"):
                raw = self._inner.get_search_profile()
                if isinstance(raw, dict):
                    merged = dict(default_profile)
                    merged.update(raw)
                    fb = raw.get("field_boosting")
                    if isinstance(fb, dict):
                        merged["field_boosting"] = {
                            "name_token_boost": float(fb.get("name_token_boost", 0.5)),
                            "exact_phrase_boost": float(fb.get("exact_phrase_boost", 1.5)),
                        }
                    return merged
        except Exception as exc:
            logger.debug(f"get_search_profile failed, using defaults: {exc}")
        return default_profile

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

    async def add_documents_partitioned(
        self,
        table_name: str,
        partition_by: str | None,
        ids: list[str],
        vectors: list[list[float]],
        contents: list[str],
        metadatas: list[str],
    ) -> None:
        """Add documents with rows grouped by a partition column for fragment alignment.

        Args:
            table_name: Name of the table/collection
            partition_by: Metadata key to partition by (e.g. 'skill_name', 'category').
                When None, uses vector.default_partition_column from settings (default "skill_name").
            ids: Unique identifiers for each document
            vectors: Embedding vectors
            contents: Text content for each document
            metadatas: JSON metadata (must contain partition_by key per row)
        """
        from omni.foundation.config.settings import get_setting

        resolved_partition = (
            partition_by
            if partition_by is not None
            else get_setting("vector.default_partition_column")
        )
        if not resolved_partition:
            raise ValueError(
                "partition_by is required when vector.default_partition_column is not set"
            )
        rust_vectors: list[list[float]] = []
        for vec in vectors:
            if vec and isinstance(vec[0], list):
                rust_vectors.append([float(v) for v in vec[0]])
            else:
                rust_vectors.append([float(v) for v in vec])
        self._inner.add_documents_partitioned(
            table_name, resolved_partition, ids, rust_vectors, contents, metadatas
        )

    async def replace_documents(
        self,
        table_name: str,
        ids: list[str],
        vectors: list[list[float]],
        contents: list[str],
        metadatas: list[str],
    ) -> None:
        """Replace all documents in table with the provided batch."""
        rust_vectors = [list(map(float, vec)) for vec in vectors]
        self._inner.replace_documents(table_name, ids, rust_vectors, contents, metadatas)

    async def merge_insert_documents(
        self,
        table_name: str,
        ids: list[str],
        vectors: list[list[float]],
        contents: list[str],
        metadatas: list[str],
        match_on: str = "id",
    ) -> dict:
        """Upsert documents using merge-insert (match on key column).

        Updates existing rows and inserts new ones based on the match_on column.
        Unlike replace_documents, this preserves existing data (e.g. keyword index).
        """
        import json as _json

        rust_vectors = [list(map(float, vec)) for vec in vectors]
        result_json = self._inner.merge_insert_documents(
            table_name, ids, rust_vectors, contents, metadatas, match_on
        )
        return _json.loads(result_json)

    async def ingest(self, content: FileContent) -> IngestResult:
        """Ingest a document into the vector store."""
        try:
            logger.debug(f"Ingesting {content.path}")
            return IngestResult(success=True, document_id=content.path, chunks_created=1)
        except Exception as e:
            logger.error(f"Document ingestion failed: {e}")
            return IngestResult(success=False, error=str(e))

    async def delete(self, document_id: str) -> bool:
        """Delete a document from the vector store (legacy; table fixed as 'skills')."""
        try:
            self._inner.delete("skills", [document_id])
            return True
        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            return False

    def delete_by_ids(self, table_name: str, ids: list[str]) -> None:
        """Delete documents by id in the given table (e.g. collection name)."""
        self._inner.delete(table_name, ids)

    def count(self, table_name: str) -> int:
        """Return row count for the given table (e.g. collection name)."""
        return int(self._inner.count(table_name))

    def delete_by_file_path(self, table_name: str, file_paths: list[str]) -> None:
        """Delete all documents matching the given file paths.

        Args:
            table_name: Name of the table to delete from
            file_paths: List of file paths to match for deletion
        """
        try:
            self._inner.delete_by_file_path(table_name, file_paths)
        except Exception as e:
            logger.error(f"Delete by file path failed: {e}")
            raise

    async def create_index(
        self,
        name: str,
        dimension: int,
        path: str | None = None,
    ) -> bool:
        """Create a new vector index (dimension/path unused; kept for compatibility)."""
        try:
            self._inner.create_index(name)
            return True
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            return False

    async def create_index_for_table(self, table_name: str) -> bool:
        """Create vector index for the given table (e.g. collection name)."""
        return await self.create_index(table_name, 0, None)

    async def health_check(self) -> bool:
        """Check if the vector store is healthy."""
        try:
            count = self._inner.count("skills")
            logger.debug(f"Vector store health check: {count} documents")
            return True
        except Exception as e:
            logger.error(f"Vector store health check failed: {e}")
            return False

    def analyze_table_health(self, table_name: str) -> dict[str, Any]:
        """Return table health report (row_count, fragment_count, recommendations).

        Uses LanceDB observability (Phase 5). Returns dict with keys:
        row_count, fragment_count, fragmentation_ratio, indices_status, recommendations.
        """
        try:
            json_str = self._inner.analyze_table_health(table_name)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"analyze_table_health failed: {e}")
            return {}

    def analyze_table_health_ipc(self, table_name: str) -> bytes:
        """Return table health report as Arrow IPC stream bytes.

        Decode with pyarrow to get a table:
            import io
            import pyarrow.ipc
            table = pyarrow.ipc.open_stream(io.BytesIO(store.analyze_table_health_ipc("t"))).read_all()
        Columns: row_count, fragment_count, fragmentation_ratio, index_names, index_types, recommendations.
        """
        return bytes(self._inner.analyze_table_health_ipc(table_name))

    def compact(self, table_name: str) -> dict[str, Any]:
        """Run compaction (cleanup + compact_files) on a table.

        Returns dict with fragments_before, fragments_after, fragments_removed,
        bytes_freed, duration_ms.
        """
        try:
            json_str = self._inner.compact(table_name)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"compact failed: {e}")
            return {}

    def check_migrations(self, table_name: str) -> list[dict[str, Any]]:
        """List pending schema migrations for a table.

        Returns list of {from_version, to_version, description}.
        """
        try:
            json_str = self._inner.check_migrations(table_name)
            return json.loads(json_str) if json_str else []
        except Exception as e:
            logger.debug(f"check_migrations failed: {e}")
            raise

    def migrate(self, table_name: str) -> dict[str, Any]:
        """Run pending schema migrations for a table.

        Returns dict with applied (list of [from_version, to_version]) and rows_processed.
        """
        try:
            json_str = self._inner.migrate(table_name)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"migrate failed: {e}")
            raise

    def get_query_metrics(self, table_name: str) -> dict[str, Any]:
        """Return per-table query metrics (placeholder until Lance tracing).

        Returns dict with query_count, last_query_ms (None until wired).
        """
        try:
            json_str = self._inner.get_query_metrics(table_name)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"get_query_metrics failed: {e}")
            return {}

    def get_index_cache_stats(self, table_name: str) -> dict[str, Any]:
        """Return index cache stats (entry_count, hit_rate) for the table's dataset."""
        try:
            json_str = self._inner.get_index_cache_stats(table_name)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"get_index_cache_stats failed: {e}")
            return {}

    def create_btree_index(self, table_name: str, column: str) -> dict[str, Any]:
        """Create a BTree index on a column (exact match / range). Returns index stats."""
        try:
            json_str = self._inner.create_btree_index(table_name, column)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"create_btree_index failed: {e}")
            raise

    def create_bitmap_index(self, table_name: str, column: str) -> dict[str, Any]:
        """Create a Bitmap index on a column (low-cardinality). Returns index stats."""
        try:
            json_str = self._inner.create_bitmap_index(table_name, column)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"create_bitmap_index failed: {e}")
            raise

    def create_hnsw_index(self, table_name: str) -> dict[str, Any]:
        """Create an IVF+HNSW vector index. Requires at least 50 rows. Returns index stats."""
        try:
            json_str = self._inner.create_hnsw_index(table_name)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"create_hnsw_index failed: {e}")
            raise

    def create_optimal_vector_index(self, table_name: str) -> dict[str, Any]:
        """Create the best vector index for table size (HNSW or IVF_FLAT). Returns index stats."""
        try:
            json_str = self._inner.create_optimal_vector_index(table_name)
            return json.loads(json_str) if json_str else {}
        except Exception as e:
            logger.debug(f"create_optimal_vector_index failed: {e}")
            raise

    def create_index_background(self, table_name: str) -> None:
        """Start building the vector index in a background task. Returns immediately.

        Phase 2: use this to avoid blocking the caller; index builds asynchronously.
        Table must have at least 100 rows for the background job to run.
        """
        self._inner.create_index_background(table_name)

    def suggest_partition_column(self, table_name: str) -> str | None:
        """Suggest a partition column if table is large and schema supports it (e.g. skill_name)."""
        try:
            return self._inner.suggest_partition_column(table_name)
        except Exception as e:
            logger.debug(f"suggest_partition_column failed: {e}")
            return None

    def auto_index_if_needed(self, table_name: str) -> dict[str, Any] | None:
        """Create vector/FTS/scalar indexes if table meets row thresholds. Returns last stats or None."""
        try:
            json_str = self._inner.auto_index_if_needed(table_name)
            if json_str is None:
                return None
            return json.loads(json_str) if json_str else None
        except Exception as e:
            logger.debug(f"auto_index_if_needed failed: {e}")
            raise

    def list_all_tools(self) -> list[dict]:
        """List all tools from LanceDB.

        Returns tools with: name, description, skill_name, category, input_schema.

        Returns:
            List of tool dictionaries, or empty list if table doesn't exist.
        """
        try:
            json_result = self._inner.list_all_tools(self._default_table_name())
            tools = json.loads(json_result) if json_result else []
            logger.debug(f"Listed {len(tools)} tools from LanceDB")
            return tools
        except Exception as e:
            logger.debug(f"Failed to list tools from LanceDB: {e}")
            return []

    def list_all_resources(self, table_name: str | None = None) -> list[dict]:
        """List all skill-declared resources from LanceDB (rows with non-empty resource_uri).

        Returns:
            List of resource dicts with: resource_uri, description, skill_name, tool_name, id.
        """
        try:
            tbl = table_name or self._default_table_name()
            json_result = self._inner.list_all_resources(tbl)
            resources = json.loads(json_result) if json_result else []
            logger.debug(f"Listed {len(resources)} resources from LanceDB")
            return resources
        except Exception as e:
            logger.debug(f"Failed to list resources from LanceDB: {e}")
            return []

    def get_skill_index_sync(self, base_path: str) -> list[dict]:
        """Get complete skill index with full metadata from filesystem scan (sync)."""
        try:
            json_result = self._inner.get_skill_index(base_path)
            skills = json.loads(json_result) if json_result else []
            logger.debug(f"Found {len(skills)} skills in index")
            return skills
        except Exception as e:
            logger.debug(f"Failed to get skill index: {e}")
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
        return self.get_skill_index_sync(base_path)

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

    def list_all_tools_arrow(self) -> Any:
        """List all tools from LanceDB as a pyarrow.Table.

        Same data as list_all_tools(); returns Table for columnar use.
        Nested dict/list fields are JSON-encoded as strings.
        """
        rows = self.list_all_tools()
        return _list_of_dicts_to_table(rows)

    def get_skill_index_arrow(self, base_path: str) -> Any:
        """Get skill index from filesystem scan as a pyarrow.Table.

        Same data as get_skill_index_sync(); returns Table for columnar use.
        Nested dict/list fields are JSON-encoded as strings.
        """
        rows = self.get_skill_index_sync(base_path)
        return _list_of_dicts_to_table(rows)

    def list_all_arrow(self, table_name: str = "knowledge") -> Any:
        """List all entries from a table as a pyarrow.Table.

        Same data as list_all(); returns Table for columnar use.
        Nested dict/list fields are JSON-encoded as strings.
        """
        try:
            json_result = self._inner.list_all_tools(table_name)
            entries = json.loads(json_result) if json_result else []
            return _list_of_dicts_to_table(entries)
        except Exception as e:
            logger.debug(f"Failed to list entries from {table_name}: {e}")
            import pyarrow as pa

            return pa.table({})

    def get_analytics_table_sync(self, table_name: str = "skills"):
        """Get all tools as a PyArrow Table for analytics (sync path)."""
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
            table_name: Table name to index tools into (default: "skills")

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

    async def index_skill_tools_dual(
        self,
        base_path: str,
        skills_table: str = "skills",
        router_table: str = "skills",
    ) -> tuple[int, int]:
        """Index skill tools into one or two tables from one Rust scan (single table: use same name for both)."""
        try:
            skills_count, router_count = self._inner.index_skill_tools_dual(
                base_path, skills_table, router_table
            )
            logger.info(
                "Indexed dual tool tables from %s: %s=%s, %s=%s",
                base_path,
                skills_table,
                skills_count,
                router_table,
                router_count,
            )
            return int(skills_count), int(router_count)
        except Exception as e:
            logger.error(f"Failed to index dual skill tables: {e}")
            return 0, 0

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

    async def get_table_info(self, table_name: str = "skills") -> dict[str, Any] | None:
        """Get table metadata including version, rows, schema and fragment count."""
        try:
            raw = self._inner.get_table_info(table_name)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.debug(f"Failed to get table info for {table_name}: {e}")
            return None

    async def list_versions(self, table_name: str = "skills") -> list[dict[str, Any]]:
        """List historical table versions."""
        try:
            raw = self._inner.list_versions(table_name)
            return json.loads(raw) if raw else []
        except Exception as e:
            logger.debug(f"Failed to list versions for {table_name}: {e}")
            return []

    async def get_fragment_stats(self, table_name: str = "skills") -> list[dict[str, Any]]:
        """Get fragment-level row/file stats."""
        try:
            raw = self._inner.get_fragment_stats(table_name)
            return json.loads(raw) if raw else []
        except Exception as e:
            logger.debug(f"Failed to get fragment stats for {table_name}: {e}")
            return []

    async def add_columns(self, table_name: str, columns: list[dict[str, Any]]) -> bool:
        """Add nullable columns via schema evolution API."""
        try:
            payload = json.dumps({"columns": columns})
            self._inner.add_columns(table_name, payload)
            return True
        except Exception as e:
            logger.debug(f"Failed to add columns on {table_name}: {e}")
            return False

    async def alter_columns(self, table_name: str, alterations: list[dict[str, Any]]) -> bool:
        """Alter columns (rename / nullability) via schema evolution API."""
        try:
            payload = json.dumps({"alterations": alterations})
            self._inner.alter_columns(table_name, payload)
            return True
        except Exception as e:
            logger.debug(f"Failed to alter columns on {table_name}: {e}")
            return False

    async def drop_columns(self, table_name: str, columns: list[str]) -> bool:
        """Drop non-reserved columns via schema evolution API."""
        try:
            self._inner.drop_columns(table_name, columns)
            return True
        except Exception as e:
            logger.debug(f"Failed to drop columns on {table_name}: {e}")
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

    # Use effective embedding dimension (respects truncate_dim) so ingest/search match
    if dimension is None:
        from omni.foundation.services.index_dimension import (
            get_effective_embedding_dimension,
        )

        dimension = get_effective_embedding_dimension()

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
    "_DEFAULT_MAX_CACHED_TABLES",  # Re-export for PyVectorStore users
]
