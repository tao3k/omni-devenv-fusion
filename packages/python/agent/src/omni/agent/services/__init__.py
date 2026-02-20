"""Agent services - implementation layer for CLI and other callers.

CLI commands should only parse args and call these services; no business logic in CLI.
"""

from .reindex import (
    _build_relationship_graph_after_skills_reindex,
    ensure_embedding_index_compatibility,
    reindex_all,
    reindex_clear,
    reindex_knowledge,
    reindex_skills_only,
    reindex_status,
)
from .sync import (
    sync_all,
    sync_knowledge,
    sync_memory,
    sync_router_init,
    sync_skills,
    sync_symbols,
)

__all__ = [
    "_build_relationship_graph_after_skills_reindex",
    "ensure_embedding_index_compatibility",
    "reindex_all",
    "reindex_clear",
    "reindex_knowledge",
    "reindex_skills_only",
    "reindex_status",
    "sync_all",
    "sync_knowledge",
    "sync_memory",
    "sync_router_init",
    "sync_skills",
    "sync_symbols",
]
