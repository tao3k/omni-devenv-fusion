"""
Vector store client: singleton, store resolution, cache, and facade methods.

Delegates semantic search, hybrid search, and CRUD to vector.search, vector.hybrid, vector.crud.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omni.foundation.config.dirs import PRJ_CACHE

from .crud import (
    add as crud_add,
    add_batch as crud_add_batch,
    add_columns as crud_add_columns,
    alter_columns as crud_alter_columns,
    count as crud_count,
    create_index as crud_create_index,
    delete as crud_delete,
    delete_by_metadata_source as crud_delete_by_metadata_source,
    drop_columns as crud_drop_columns,
    get_fragment_stats as crud_get_fragment_stats,
    get_table_info as crud_get_table_info,
    list_versions as crud_list_versions,
)
from .hybrid import run_hybrid_search
from .models import SearchResult
from .search import run_semantic_search


def _get_search_cache():
    from omni.core.router.cache import SearchCache

    return SearchCache(max_size=200, ttl=300)


class VectorStoreClient:
    """Foundation-level Vector Store Client. Single factory for LanceDB-backed stores."""

    _instance: VectorStoreClient | None = None
    _cache_path: Path
    _search_cache: Any
    _store: Any | None = None
    _knowledge_store: Any | None = None

    @staticmethod
    def _log_error(message: str, error_code: str, cause: str, error: str, **context: Any) -> None:
        import structlog

        structlog.get_logger(__name__).error(
            message, error_code=error_code, cause=cause, error=error, **context
        )

    @staticmethod
    def _is_table_not_found(error: Exception) -> bool:
        s = str(error).lower()
        return "table not found" in s or "not found" in s

    def __new__(cls) -> VectorStoreClient:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache_path = Path(PRJ_CACHE("omni-vector"))
            cls._instance._cache_path.mkdir(parents=True, exist_ok=True)
            cls._instance._search_cache = _get_search_cache()
            cls._instance._store = None
            cls._instance._knowledge_store = None
        return cls._instance

    def _get_store_for_collection(self, collection: str) -> Any | None:
        if collection == "knowledge_chunks":
            if self._knowledge_store is not None:
                return self._knowledge_store
            try:
                from omni.foundation.bridge.rust_vector import get_vector_store
                from omni.foundation.config.database import get_database_path

                path = get_database_path("knowledge")
                return get_vector_store(str(path))
            except Exception as e:
                import structlog

                structlog.get_logger(__name__).debug("VectorStore unavailable for knowledge: %s", e)
                return None
        if self._store is not None:
            return self._store
        try:
            from omni.foundation.bridge.rust_vector import get_vector_store

            return get_vector_store(str(self._cache_path))
        except Exception as e:
            import structlog

            structlog.get_logger(__name__).debug("VectorStore unavailable: %s", e)
            return None

    def get_store_for_collection(self, collection: str) -> Any | None:
        return self._get_store_for_collection(collection)

    @property
    def store(self) -> Any | None:
        if self._store is not None:
            return self._store
        try:
            from omni.foundation.bridge.rust_vector import get_vector_store

            return get_vector_store(str(self._cache_path))
        except Exception as e:
            import structlog

            structlog.get_logger(__name__).debug("VectorStore unavailable: %s", e)
            return None

    @property
    def path(self) -> Path:
        return self._cache_path

    async def search(
        self,
        query: str,
        n_results: int = 5,
        collection: str = "knowledge",
        use_cache: bool = True,
        where_filter: str | dict[str, Any] | None = None,
        batch_size: int | None = None,
        fragment_readahead: int | None = None,
        batch_readahead: int | None = None,
        scan_limit: int | None = None,
        projection: list[str] | None = None,
    ) -> list[SearchResult]:
        return await run_semantic_search(
            self,
            query,
            n_results,
            collection,
            use_cache,
            where_filter=where_filter,
            batch_size=batch_size,
            fragment_readahead=fragment_readahead,
            batch_readahead=batch_readahead,
            scan_limit=scan_limit,
            projection=projection,
        )

    async def search_hybrid(
        self,
        query: str,
        n_results: int = 5,
        collection: str = "knowledge",
        keywords: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[SearchResult]:
        return await run_hybrid_search(self, query, n_results, collection, keywords, use_cache)

    async def add(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        collection: str = "knowledge",
    ) -> bool:
        return await crud_add(self, content, metadata, collection)

    async def add_batch(
        self,
        chunks: list[str],
        metadata: list[dict[str, Any]],
        collection: str = "knowledge",
        batch_size: int = 32,
        max_concurrent_embed_batches: int = 1,
    ) -> int:
        return await crud_add_batch(
            self, chunks, metadata, collection, batch_size, max_concurrent_embed_batches
        )

    async def delete(self, id: str, collection: str = "knowledge") -> bool:
        return await crud_delete(self, id, collection)

    async def delete_by_metadata_source(self, collection: str, source: str) -> int:
        """Delete rows whose metadata.source equals or ends with source. Returns count deleted."""
        return await crud_delete_by_metadata_source(self, collection, source)

    async def count(self, collection: str = "knowledge") -> int:
        return await crud_count(self, collection)

    async def create_index(self, collection: str = "knowledge") -> bool:
        return await crud_create_index(self, collection)

    async def get_table_info(self, collection: str = "knowledge") -> dict[str, Any] | None:
        return await crud_get_table_info(self, collection)

    async def list_versions(self, collection: str = "knowledge") -> list[dict[str, Any]]:
        return await crud_list_versions(self, collection)

    async def get_fragment_stats(self, collection: str = "knowledge") -> list[dict[str, Any]]:
        return await crud_get_fragment_stats(self, collection)

    async def add_columns(
        self, collection: str, columns: list[dict[str, Any]], invalidate_cache: bool = True
    ) -> bool:
        return await crud_add_columns(self, collection, columns, invalidate_cache)

    async def alter_columns(
        self, collection: str, alterations: list[dict[str, Any]], invalidate_cache: bool = True
    ) -> bool:
        return await crud_alter_columns(self, collection, alterations, invalidate_cache)

    async def drop_columns(
        self, collection: str, columns: list[str], invalidate_cache: bool = True
    ) -> bool:
        return await crud_drop_columns(self, collection, columns, invalidate_cache)

    def invalidate_cache(self, collection: str | None = None) -> int:
        if collection is None:
            return self._search_cache.clear()
        keys_to_remove = [k for k in self._search_cache._cache if k.startswith(f"{collection}:")]
        for k in keys_to_remove:
            del self._search_cache._cache[k]
        return len(keys_to_remove)

    def cache_stats(self) -> dict[str, Any]:
        return self._search_cache.stats()


def get_vector_store() -> VectorStoreClient:
    return VectorStoreClient()


def evict_knowledge_store_after_use() -> None:
    """Evict the knowledge vector store, KG cache, and run GC (query-release lifecycle).

    Called after each tool run so the long-lived MCP process does not retain
    LanceDB or knowledge-graph memory. We evict from the process caches so the
    next use opens fresh. See docs/reference/lancedb-query-release-lifecycle.md.
    """
    import gc

    from omni.foundation.bridge.rust_vector import evict_vector_store_cache
    from omni.foundation.config.database import get_database_path

    path = get_database_path("knowledge")
    evict_vector_store_cache(path)
    try:
        from omni_core_rs import invalidate_kg_cache

        invalidate_kg_cache(path)
    except Exception:
        pass
    if VectorStoreClient._instance is not None:
        VectorStoreClient._instance.invalidate_cache()
        VectorStoreClient._instance._knowledge_store = None
        VectorStoreClient._instance._store = None
    gc.collect()


def evict_all_vector_stores() -> None:
    """Evict all vector stores from the process cache and run GC.

    Use at process or session teardown (e.g. test session) so the OS can reclaim
    memory. Normal runtime uses evict_knowledge_store_after_use() after each tool.
    """
    import gc

    from omni.foundation.bridge.rust_vector import evict_vector_store_cache

    evict_vector_store_cache(None)
    if VectorStoreClient._instance is not None:
        VectorStoreClient._instance.invalidate_cache()
        VectorStoreClient._instance._knowledge_store = None
        VectorStoreClient._instance._store = None
    gc.collect()
