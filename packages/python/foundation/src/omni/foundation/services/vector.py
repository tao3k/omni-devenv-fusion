"""
omni.foundation.vector_store - Foundation Vector Store

Centralized access to omni-vector (LanceDB).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel, ValidationError

from omni.foundation.config.dirs import PRJ_CACHE
from omni.foundation.services.embedding import get_embedding_service
from omni.foundation.services.vector_schema import (
    build_search_options_json,
    parse_hybrid_payload,
    parse_vector_payload,
)

if TYPE_CHECKING:
    from omni.core.router.cache import SearchCache

logger = structlog.get_logger(__name__)
MAX_SEARCH_RESULTS = 1000
ERROR_REQUEST_VALIDATION = "VECTOR_REQUEST_VALIDATION"
ERROR_BINDING_API_MISSING = "VECTOR_BINDING_API_MISSING"
ERROR_PAYLOAD_VALIDATION = "VECTOR_PAYLOAD_VALIDATION"
ERROR_TABLE_NOT_FOUND = "VECTOR_TABLE_NOT_FOUND"
ERROR_RUNTIME = "VECTOR_RUNTIME_ERROR"
ERROR_HYBRID_PAYLOAD_VALIDATION = "VECTOR_HYBRID_PAYLOAD_VALIDATION"
ERROR_HYBRID_TABLE_NOT_FOUND = "VECTOR_HYBRID_TABLE_NOT_FOUND"
ERROR_HYBRID_RUNTIME = "VECTOR_HYBRID_RUNTIME_ERROR"

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
    score: float | None = None
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

    @staticmethod
    def _log_error(message: str, error_code: str, cause: str, error: str, **context: Any) -> None:
        logger.error(message, error_code=error_code, cause=cause, error=error, **context)

    @staticmethod
    def _is_table_not_found(error: Exception) -> bool:
        error_str = str(error).lower()
        return "table not found" in error_str or "not found" in error_str

    def __new__(cls) -> VectorStoreClient:
        if cls._instance is None:
            from omni.core.router.cache import SearchCache

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
                    # Pass True to enable auto-creation/read-write mode
                    self._store = create_store(str(self._cache_path), dim, True)
                    logger.info("VectorStore initialized", path=str(self._cache_path))
                except Exception as e:
                    logger.error("VectorStore init failed", error=str(e))
        return self._store

    @property
    def path(self) -> Path:
        """Get the path to the vector store data."""
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
        if n_results < 1 or n_results > MAX_SEARCH_RESULTS:
            self._log_error(
                "Search failed",
                error_code=ERROR_REQUEST_VALIDATION,
                cause="request_validation",
                error=f"n_results must be between 1 and {MAX_SEARCH_RESULTS}",
            )
            return []

        if not collection:
            self._log_error(
                "Search failed",
                error_code=ERROR_REQUEST_VALIDATION,
                cause="request_validation",
                error="collection must be a non-empty string",
            )
            return []

        store = self.store
        if not store:
            logger.warning("VectorStore not available, returning empty results")
            return []

        # Build cache key from query parameters
        options_cache = {
            "where_filter": where_filter,
            "batch_size": batch_size,
            "fragment_readahead": fragment_readahead,
            "batch_readahead": batch_readahead,
            "scan_limit": scan_limit,
        }
        cache_key = f"{collection}:{query}:{n_results}:{json.dumps(options_cache, sort_keys=True, default=str)}"

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

            options: dict[str, Any] = {}
            if where_filter is not None:
                if isinstance(where_filter, dict):
                    options["where_filter"] = json.dumps(where_filter)
                else:
                    options["where_filter"] = where_filter
            if batch_size is not None:
                options["batch_size"] = int(batch_size)
            if fragment_readahead is not None:
                options["fragment_readahead"] = int(fragment_readahead)
            if batch_readahead is not None:
                options["batch_readahead"] = int(batch_readahead)
            if scan_limit is not None:
                options["scan_limit"] = int(scan_limit)

            # Unified path: require optimized scanner API.
            if not hasattr(store, "search_optimized"):
                self._log_error(
                    "VectorStore binding missing required API: search_optimized",
                    error_code=ERROR_BINDING_API_MISSING,
                    cause="binding_contract",
                    error="search_optimized unavailable",
                    collection=collection,
                )
                return []

            options_json = build_search_options_json(options)
            results_json = store.search_optimized(collection, vector, n_results, options_json)

            # Parse results through canonical payload contract
            results: list[SearchResult] = []
            for raw in results_json:
                payload = parse_vector_payload(raw)
                result_id, content, metadata, distance = payload.to_search_result_fields()
                score = payload.score
                if score is None:
                    score = 1.0 / (1.0 + max(distance, 0.0))
                results.append(
                    SearchResult(
                        content=content,
                        metadata=metadata,
                        distance=distance,
                        score=score,
                        id=result_id,
                    )
                )

            # Cache the results
            if use_cache:
                self._search_cache.set(cache_key, results)

            return results
        except (ValidationError, ValueError) as e:
            self._log_error(
                "Search failed",
                error_code=ERROR_PAYLOAD_VALIDATION,
                cause="payload_validation",
                error=str(e),
                collection=collection,
            )
            return []
        except Exception as e:
            # Handle "table not found" errors gracefully - return empty results
            if self._is_table_not_found(e):
                logger.debug(
                    "VectorStore collection not found",
                    collection=collection,
                    error_code=ERROR_TABLE_NOT_FOUND,
                )
                return []
            self._log_error(
                "Search failed",
                error_code=ERROR_RUNTIME,
                cause="runtime",
                error=str(e),
                collection=collection,
            )
            return []

    async def search_hybrid(
        self,
        query: str,
        n_results: int = 5,
        collection: str = "knowledge",
        keywords: list[str] | None = None,
        use_cache: bool = True,
    ) -> list[SearchResult]:
        """Run Rust-backed hybrid search with canonical payload validation."""
        store = self.store
        if not store:
            logger.warning("VectorStore not available, returning empty hybrid results")
            return []

        kw = sorted(keywords) if keywords else [query]
        kw_key = ",".join(kw)
        cache_key = f"hybrid:{collection}:{query}:{kw_key}:{n_results}"
        if use_cache:
            cached = self._search_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Hybrid cache hit for query: {query[:50]}...")
                return cached

        try:
            service = get_embedding_service()
            vector = service.embed(query)[0]
            results_json = store.search_hybrid(collection, vector, kw, n_results)

            parsed: list[SearchResult] = []
            for raw in results_json:
                payload = parse_hybrid_payload(raw)
                result_id, content, metadata, score = payload.to_search_result_fields()

                parsed.append(
                    SearchResult(
                        content=content,
                        metadata=metadata,
                        distance=max(0.0, 1.0 - score),
                        score=score,
                        id=result_id,
                    )
                )

            if use_cache:
                self._search_cache.set(cache_key, parsed)
            return parsed
        except (ValidationError, ValueError) as e:
            self._log_error(
                "Hybrid search failed",
                error_code=ERROR_HYBRID_PAYLOAD_VALIDATION,
                cause="payload_validation",
                error=str(e),
                collection=collection,
            )
            return []
        except Exception as e:
            if self._is_table_not_found(e):
                logger.debug(
                    "VectorStore hybrid collection not found",
                    collection=collection,
                    error_code=ERROR_HYBRID_TABLE_NOT_FOUND,
                )
                return []
            self._log_error(
                "Hybrid search failed",
                error_code=ERROR_HYBRID_RUNTIME,
                cause="runtime",
                error=str(e),
                collection=collection,
            )
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

            # Use add_documents for better consistency/table creation
            import uuid

            doc_id = str(uuid.uuid4())

            # Prepare batch of size 1
            ids = [doc_id]
            vectors = [vector]
            contents = [content]
            metadatas = [json.dumps(metadata or {})]

            store.add_documents(collection, ids, vectors, contents, metadatas)

            # Invalidate cache for this collection since results changed
            self.invalidate_cache(collection)

            return True
        except Exception as e:
            # Handle "table not found" errors gracefully
            if self._is_table_not_found(e):
                logger.debug(f"VectorStore: Collection '{collection}' not found for add operation")
                return False
            logger.error("Add failed", error=str(e))
            return False

    async def add_batch(
        self,
        chunks: list[str],
        metadata: list[dict[str, Any]],
        collection: str = "knowledge",
        batch_size: int = 32,
    ) -> int:
        """Batch add content to the vector store.

        Optimized for large batches by:
        1. Pre-computing all embeddings in a single batch
        2. Using Rust's add_documents for bulk insert

        Args:
            chunks: List of text chunks to embed and store.
            metadata: List of metadata dicts for each chunk.
            collection: Collection name.
            batch_size: Batch size for embedding (default: 32).

        Returns:
            Number of successfully stored chunks.
        """
        store = self.store
        if not store:
            return 0

        if not chunks:
            return 0

        chunks_stored = 0

        try:
            import uuid

            service = get_embedding_service()

            # Process in batches for embedding efficiency
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i : i + batch_size]
                batch_meta = metadata[i : i + batch_size]

                # Get embeddings for entire batch at once
                embeddings = service.embed_batch(batch_chunks)

                # Prepare batch data
                ids = [str(uuid.uuid4()) for _ in batch_chunks]
                vectors = embeddings
                contents = batch_chunks
                metadatas = [json.dumps(m or {}) for m in batch_meta]

                # Single Rust call for bulk insert
                store.add_documents(collection, ids, vectors, contents, metadatas)
                chunks_stored += len(batch_chunks)

                logger.info(
                    "Batch stored",
                    batch=i // batch_size + 1,
                    stored=chunks_stored,
                    total=len(chunks),
                )

            # Invalidate cache once after all batches
            self.invalidate_cache(collection)

            return chunks_stored

        except Exception as e:
            if self._is_table_not_found(e):
                logger.debug(f"VectorStore: Collection '{collection}' not found for batch add")
                return chunks_stored
            logger.error("Batch add failed", error=str(e))
            return chunks_stored

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
            if self._is_table_not_found(e):
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
            if self._is_table_not_found(e):
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

    async def get_table_info(self, collection: str = "knowledge") -> dict[str, Any] | None:
        """Get table metadata from the underlying vector store."""
        store = self.store
        if not store:
            return None

        try:
            raw = store.get_table_info(collection)
            return json.loads(raw) if raw else None
        except Exception as e:
            if self._is_table_not_found(e):
                return None
            logger.error("Get table info failed", error=str(e))
            return None

    async def list_versions(self, collection: str = "knowledge") -> list[dict[str, Any]]:
        """List historical versions for a collection."""
        store = self.store
        if not store:
            return []

        try:
            raw = store.list_versions(collection)
            return json.loads(raw) if raw else []
        except Exception as e:
            if self._is_table_not_found(e):
                return []
            logger.error("List versions failed", error=str(e))
            return []

    async def get_fragment_stats(self, collection: str = "knowledge") -> list[dict[str, Any]]:
        """Get fragment-level stats for a collection."""
        store = self.store
        if not store:
            return []

        try:
            raw = store.get_fragment_stats(collection)
            return json.loads(raw) if raw else []
        except Exception as e:
            if self._is_table_not_found(e):
                return []
            logger.error("Get fragment stats failed", error=str(e))
            return []

    async def add_columns(
        self, collection: str, columns: list[dict[str, Any]], invalidate_cache: bool = True
    ) -> bool:
        """Add columns using schema evolution."""
        store = self.store
        if not store:
            return False

        try:
            payload = json.dumps({"columns": columns})
            store.add_columns(collection, payload)
            if invalidate_cache:
                self.invalidate_cache(collection)
            return True
        except Exception as e:
            logger.error("Add columns failed", error=str(e))
            return False

    async def alter_columns(
        self, collection: str, alterations: list[dict[str, Any]], invalidate_cache: bool = True
    ) -> bool:
        """Alter columns using schema evolution."""
        store = self.store
        if not store:
            return False

        try:
            payload = json.dumps({"alterations": alterations})
            store.alter_columns(collection, payload)
            if invalidate_cache:
                self.invalidate_cache(collection)
            return True
        except Exception as e:
            logger.error("Alter columns failed", error=str(e))
            return False

    async def drop_columns(
        self, collection: str, columns: list[str], invalidate_cache: bool = True
    ) -> bool:
        """Drop columns using schema evolution."""
        store = self.store
        if not store:
            return False

        try:
            store.drop_columns(collection, columns)
            if invalidate_cache:
                self.invalidate_cache(collection)
            return True
        except Exception as e:
            logger.error("Drop columns failed", error=str(e))
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
                key for key in self._search_cache._cache if key.startswith(f"{collection}:")
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
