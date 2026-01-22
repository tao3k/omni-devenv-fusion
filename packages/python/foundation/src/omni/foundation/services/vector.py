"""
omni.foundation.vector_store - Foundation Vector Store

Centralized access to omni-vector (LanceDB).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from omni.foundation.config.dirs import PRJ_CACHE
from omni.foundation.services.embedding import get_embedding_service

logger = structlog.get_logger(__name__)

# Lazy loader for Rust extension
_cached_omni_vector: Any | None = None


def _get_omni_vector() -> Any | None:
    """Lazy load the Rust vector store creator function.

    Handles both real Rust modules and mock objects (e.g., in test environments).
    """
    global _cached_omni_vector
    if _cached_omni_vector is None:
        try:
            import omni_core_rs

            # Support both real module and Mock object
            if hasattr(omni_core_rs, "create_vector_store"):
                _cached_omni_vector = omni_core_rs.create_vector_store
            else:
                # Mock is setup differently - use a fallback
                logger.warning(
                    "omni_core_rs exists but has no create_vector_store, using degraded mode"
                )
                _cached_omni_vector = None
        except ImportError:
            _cached_omni_vector = None
            logger.debug(
                "Rust VectorStore not found, running in degraded mode (expected in test env)"
            )
    return _cached_omni_vector


@dataclass
class SearchResult:
    """Result from a vector store search operation."""

    content: str
    metadata: dict[str, Any]
    distance: float
    id: str


class VectorStoreClient:
    """Foundation-level Vector Store Client.

    Provides a unified interface to the LanceDB-based vector store
    for the entire omni system.
    """

    _instance: VectorStoreClient | None = None

    def __new__(cls) -> VectorStoreClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store = None
            cls._instance._cache_path = PRJ_CACHE("omni-vector")
            cls._instance._cache_path.mkdir(parents=True, exist_ok=True)
        return cls._instance

    @property
    def store(self) -> Any | None:
        """Get the underlying vector store, initializing if needed."""
        if self._store is None:
            create_store = _get_omni_vector()
            if create_store:
                try:
                    # Initialize with dimension from embedding service
                    dim = get_embedding_service().dimension
                    self._store = create_store(str(self._cache_path), dim)
                    logger.info("VectorStore initialized", path=str(self._cache_path))
                except Exception as e:
                    logger.error("VectorStore init failed", error=str(e))
        return self._store

    @property
    def path(self) -> Path:
        """Get the path to the vector store data."""
        return self._cache_path

    async def search(
        self, query: str, n_results: int = 5, collection: str = "knowledge"
    ) -> list[SearchResult]:
        """Search the vector store for similar content.

        Args:
            query: Search query text.
            n_results: Maximum number of results to return.
            collection: Collection name to search in.

        Returns:
            List of SearchResult objects ranked by similarity.
        """
        store = self.store
        if not store:
            logger.warning("VectorStore not available, returning empty results")
            return []

        try:
            # Get embedding from Foundation service
            service = get_embedding_service()
            vector = service.embed(query)[0]

            # Execute Search
            results_json = store.search(collection, vector, n_results)

            # Parse Results
            return [
                SearchResult(
                    content=r.get("content", ""),
                    metadata=r.get("metadata", {}),
                    distance=r.get("distance", 0.0),
                    id=r.get("id", ""),
                )
                for r in (json.loads(s) for s in results_json)
            ]
        except Exception as e:
            logger.error("Search failed", error=str(e))
            return []

    async def add(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        collection: str = "knowledge",
    ) -> bool:
        """Add content to the vector store.

        Args:
            content: Text content to embed and store.
            metadata: Optional metadata dictionary.
            collection: Collection name.

        Returns:
            True if successful, False otherwise.
        """
        store = self.store
        if not store:
            return False

        try:
            # Get embedding for content
            service = get_embedding_service()
            vector = service.embed(content)[0]

            # Add to store
            store.add(collection, content, vector, json.dumps(metadata or {}))
            return True
        except Exception as e:
            logger.error("Add failed", error=str(e))
            return False

    async def delete(self, id: str, collection: str = "knowledge") -> bool:
        """Delete an entry from the vector store.

        Args:
            id: Entry ID to delete.
            collection: Collection name.

        Returns:
            True if successful, False otherwise.
        """
        store = self.store
        if not store:
            return False

        try:
            store.delete(collection, id)
            return True
        except Exception as e:
            logger.error("Delete failed", error=str(e))
            return False

    async def count(self, collection: str = "knowledge") -> int:
        """Get the number of entries in a collection.

        Args:
            collection: Collection name.

        Returns:
            Number of entries.
        """
        store = self.store
        if not store:
            return 0

        try:
            return store.count(collection)
        except Exception as e:
            logger.error("Count failed", error=str(e))
            return 0

    async def create_index(self, collection: str = "knowledge") -> bool:
        """Create an IVF-FLAT index for a collection.

        Args:
            collection: Collection name.

        Returns:
            True if successful, False otherwise.
        """
        store = self.store
        if not store:
            return False

        try:
            store.create_index(collection)
            return True
        except Exception as e:
            logger.error("Create index failed", error=str(e))
            return False


def get_vector_store() -> VectorStoreClient:
    """Get the singleton VectorStoreClient instance.

    Returns:
        The global VectorStoreClient singleton.
    """
    return VectorStoreClient()


# Convenience functions


async def search_knowledge(query: str, n_results: int = 5) -> list[SearchResult]:
    """Search the knowledge collection.

    Args:
        query: Search query.
        n_results: Maximum results.

    Returns:
        List of SearchResult objects.
    """
    return await get_vector_store().search(query, n_results, collection="knowledge")


async def add_knowledge(content: str, metadata: dict[str, Any] | None = None) -> bool:
    """Add content to the knowledge collection.

    Args:
        content: Text content.
        metadata: Optional metadata.

    Returns:
        True if successful.
    """
    return await get_vector_store().add(content, metadata, collection="knowledge")
