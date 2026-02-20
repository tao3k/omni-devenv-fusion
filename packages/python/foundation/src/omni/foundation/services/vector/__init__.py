"""
omni.foundation.services.vector - Vector store namespace

Submodules:
- constants: Error codes and limits
- models: SearchResult
- search: Query embed (timeout/fallback) + semantic search
- hybrid: Hybrid (vector + keyword) search
- crud: Add, delete, count, index, schema operations
- store: VectorStoreClient singleton and get_vector_store
- knowledge: search_knowledge, add_knowledge
"""

from __future__ import annotations

from .constants import (
    ERROR_BINDING_API_MISSING,
    ERROR_HYBRID_PAYLOAD_VALIDATION,
    ERROR_HYBRID_RUNTIME,
    ERROR_HYBRID_TABLE_NOT_FOUND,
    ERROR_PAYLOAD_VALIDATION,
    ERROR_REQUEST_VALIDATION,
    ERROR_RUNTIME,
    ERROR_TABLE_NOT_FOUND,
    MAX_SEARCH_RESULTS,
)
from .search import (
    SEARCH_EMBED_TIMEOUT,
    search_embed_timeout,
)
from .knowledge import add_knowledge, search_knowledge
from .models import SearchResult
from .store import (
    VectorStoreClient,
    evict_all_vector_stores,
    evict_knowledge_store_after_use,
    get_vector_store,
)

# Legacy names for callers that use leading-underscore names
_search_embed_timeout = search_embed_timeout

__all__ = [
    "ERROR_BINDING_API_MISSING",
    "ERROR_HYBRID_PAYLOAD_VALIDATION",
    "ERROR_HYBRID_RUNTIME",
    "ERROR_HYBRID_TABLE_NOT_FOUND",
    "ERROR_PAYLOAD_VALIDATION",
    "ERROR_REQUEST_VALIDATION",
    "ERROR_RUNTIME",
    "ERROR_TABLE_NOT_FOUND",
    "MAX_SEARCH_RESULTS",
    "SEARCH_EMBED_TIMEOUT",
    "SearchResult",
    "VectorStoreClient",
    "add_knowledge",
    "evict_all_vector_stores",
    "evict_knowledge_store_after_use",
    "get_vector_store",
    "search_embed_timeout",
    "search_knowledge",
]
