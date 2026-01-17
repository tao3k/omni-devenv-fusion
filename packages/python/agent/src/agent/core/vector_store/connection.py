# agent/core/vector_store/connection.py
"""
Vector store connection and initialization.

Provides VectorMemory singleton with lazy store initialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from common import prj_dirs
from dataclasses import dataclass

# Lazy imports to avoid slow module loading
_cached_omni_vector: Any = None
_cached_logger: Any = None


def _get_omni_vector() -> Any:
    """Get omni_vector lazily to avoid slow import."""
    global _cached_omni_vector
    if _cached_omni_vector is None:
        try:
            from omni_core_rs import create_vector_store

            _cached_omni_vector = create_vector_store
        except ImportError:
            _cached_omni_vector = None
    return _cached_omni_vector


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


@dataclass
class SearchResult:
    """A single search result from vector store."""

    content: str
    metadata: Dict[str, Any]
    distance: float
    id: str


class VectorMemory:
    """
    omni-vector (LanceDB) based Vector Memory for RAG.

    Migrated from ChromaDB to Rust + LanceDB for better performance.

    Stores and retrieves semantic embeddings for:
    - Project documentation
    - Workflow rules
    - Architectural decisions
    - Code patterns and examples

    Features:
    - Persistent storage in .cache/omni-vector/
    - Multiple tables for different knowledge domains
    - Configurable similarity threshold
    """

    _instance: Optional["VectorMemory"] = None
    _store: Optional[Any] = None  # omni_vector.PyVectorStore, lazy loaded
    _cache_path: Optional[Path] = None

    # Default embedding dimension for text-embedding-ada-002
    DEFAULT_DIMENSION = 1536

    def __new__(cls) -> "VectorMemory":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._store = None
            cls._instance._cache_path = None
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        # Defer omni-vector client creation - only compute path
        self._cache_path = prj_dirs.PRJ_CACHE("omni-vector")
        self._cache_path.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        self._default_table = "project_knowledge"

    def _ensure_store(self) -> Any:
        """Lazily create omni-vector store only when needed."""
        if self._store is None and self._cache_path is not None:
            create_store = _get_omni_vector()
            if create_store is not None:
                try:
                    self._store = create_store(
                        str(self._cache_path),
                        self.DEFAULT_DIMENSION,
                    )
                    _get_logger().info(
                        "Vector memory initialized (omni-vector)",
                        db_path=str(self._cache_path),
                    )
                except Exception as e:
                    _get_logger().error("Failed to initialize omni-vector store", error=str(e))
                    self._store = None
            else:
                _get_logger().warning("omni-vector not available, vector memory disabled")
        return self._store

    @property
    def store(self) -> Any:
        """Get the omni-vector store (lazy)."""
        return self._ensure_store()

    def _get_table_name(self, collection: str | None) -> str:
        """Get table name from collection."""
        return collection or self._default_table

    def _json_to_metadata(self, json_str: str) -> Dict[str, Any]:
        """Parse metadata from JSON string."""
        try:
            return json.loads(json_str) if json_str else {}
        except json.JSONDecodeError:
            return {}


def get_vector_memory() -> VectorMemory:
    """Get the vector memory singleton instance."""
    return VectorMemory()
