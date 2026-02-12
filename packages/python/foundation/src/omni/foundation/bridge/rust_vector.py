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
from omni.foundation.services.vector_schema import parse_tool_search_payload

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
    active_name = str(get_setting("router.search.active_profile", "balanced"))
    profiles = get_setting("router.search.profiles", {})
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

    return bool(get_setting("router.search.rerank", True))


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
            # Call Rust's search_tools (synchronous in the binding, run in thread pool)
            # Rust signature:
            # (
            #   table_name, query_vector, query_text, limit, threshold,
            #   confidence_profile_json, rerank
            # )
            confidence_profile_json = (
                json.dumps(confidence_profile, sort_keys=True)
                if confidence_profile is not None
                else _confidence_profile_json()
            )
            rerank_enabled = _rerank_enabled() if rerank is None else rerank
            loop = asyncio.get_running_loop()
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

            # Convert PyObject dicts to Python dicts and validate against
            # canonical Rust<->Python tool-search schema contract.
            results: list[dict[str, Any]] = []
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

                    payload = parse_tool_search_payload(candidate)
                    results.append(payload.to_router_result())
                except Exception as convert_err:
                    logger.debug(f"Failed to convert result: {convert_err}")
                    continue

            logger.debug(f"search_tools: {len(results)} results for '{str(query_text)[:30]}...'")
            return results
        except Exception as e:
            logger.debug(f"search_tools failed: {e}")
            return []

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

    async def index_skill_tools_dual(
        self,
        base_path: str,
        skills_table: str = "skills",
        router_table: str = "router",
    ) -> tuple[int, int]:
        """Index skills and router tables from one Rust scan."""
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
