"""
omni.foundation.vector_store - Foundation Vector Store

Centralized access to omni-vector (LanceDB).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from omni.foundation.config.dirs import PRJ_CACHE
from omni.foundation.services.embedding import get_embedding_service
from omni.core.router.cache import SearchCache
from pydantic import BaseModel

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


class SearchResult(BaseModel):
    """Result from a vector store search operation."""

    content: str
    metadata: dict[str, Any]
    distance: float
    id: str


class VectorStoreClient:
    """Foundation-level Vector Store Client.

    Provides a unified interface to the LanceDB-based vector store
    for the entire omni system.

    Features:
    - LRU search result caching with TTL
    - Async operations for embedding and storage
    - Collection-based organization
    """

    _instance: VectorStoreClient | None = None
    _store: Any | None
    _cache_path: Path
    _search_cache: SearchCache

    def __new__(cls) -> VectorStoreClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._store = None
            cls._instance._cache_path = PRJ_CACHE("omni-vector")
            cls._instance._cache_path.mkdir(parents=True, exist_ok=True)
            cls._instance._search_cache = SearchCache(max_size=500, ttl=300)
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
        self, query: str, n_results: int = 5, collection: str = "knowledge", use_cache: bool = True
    ) -> list[SearchResult]:
        """Search the vector store for similar content.

        Args:
            query: Search query text.
            n_results: Maximum number of results to return.
            collection: Collection name to search in.
            use_cache: Whether to use search result caching (default: True).

        Returns:
            List of SearchResult objects ranked by similarity.
        """
        store = self.store
        if not store:
            logger.warning("VectorStore not available, returning empty results")
            return []

        # Build cache key from query parameters
        cache_key = f"{collection}:{query}:{n_results}"

        # Check cache first
        if use_cache:
            cached = self._search_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return cached

        try:
            # Get embedding from Foundation service
            service = get_embedding_service()
            vector = service.embed(query)[0]

            # Execute Search
            results_json = store.search(collection, vector, n_results)

            # Parse Results
            results = [
                SearchResult(
                    content=r.get("content", ""),
                    metadata=r.get("metadata", {}),
                    distance=r.get("distance", 0.0),
                    id=r.get("id", ""),
                )
                for r in (json.loads(s) for s in results_json)
            ]

            # Cache the results
            if use_cache:
                self._search_cache.set(cache_key, results)

            return results
        except Exception as e:
            # Handle "table not found" errors gracefully - return empty results
            error_str = str(e).lower()
            if "table not found" in error_str or "not found" in error_str:
                logger.debug(
                    f"VectorStore: Collection '{collection}' not found, returning empty results"
                )
                return []
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

            # Invalidate cache for this collection since results changed
            self.invalidate_cache(collection)

            return True
        except Exception as e:
            # Handle "table not found" errors gracefully
            error_str = str(e).lower()
            if "table not found" in error_str or "not found" in error_str:
                logger.debug(f"VectorStore: Collection '{collection}' not found for add operation")
                return False
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

            # Invalidate cache for this collection since results changed
            self.invalidate_cache(collection)

            return True
        except Exception as e:
            # Handle "table not found" errors gracefully
            error_str = str(e).lower()
            if "table not found" in error_str or "not found" in error_str:
                logger.debug(
                    f"VectorStore: Collection '{collection}' not found for delete operation"
                )
                return False
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
            # Handle "table not found" errors gracefully - return 0
            error_str = str(e).lower()
            if "table not found" in error_str or "not found" in error_str:
                return 0
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

    def invalidate_cache(self, collection: str | None = None) -> int:
        """Invalidate search cache entries.

        Args:
            collection: Optional collection name to invalidate.
                       If None, clears all cache entries.

        Returns:
            Number of cache entries cleared.
        """
        if collection is None:
            return self._search_cache.clear()
        else:
            # Clear entries matching the collection prefix
            keys_to_remove = [
                key for key in self._search_cache._cache.keys() if key.startswith(f"{collection}:")
            ]
            for key in keys_to_remove:
                del self._search_cache._cache[key]
            return len(keys_to_remove)

    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics.
        """
        return self._search_cache.stats()


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
