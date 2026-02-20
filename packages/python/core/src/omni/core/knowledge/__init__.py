"""
omni.core.knowledge - Knowledge Management Subsystem

Modules:
- config: Configuration from references.yaml
- knowledge_types: Knowledge entry type definitions (from Rust xiuxian-wendao)
- librarian: Librarian main class

Usage:
    from omni.core.knowledge import Librarian, ChunkMode, get_knowledge_config
    from omni.core.knowledge.knowledge_types import KnowledgeEntry, KnowledgeCategory

Note:
    This module uses Rust bindings from xiuxian-wendao crate for
    high-performance knowledge management.
"""

from contextlib import suppress

from .config import KnowledgeConfig, get_knowledge_config, reset_config

# Re-export types from knowledge_types (which wraps Rust bindings)
from .knowledge_types import (
    _HAS_RUST_BINDINGS,
    KnowledgeCategory,
    KnowledgeEntry,
    KnowledgeSearchQuery,
    KnowledgeStats,
)
from .librarian import ChunkMode, Librarian

# Also export LinkGraph entity reference extraction functions from Rust bindings
link_graph_extract_entity_refs = None
link_graph_get_ref_stats = None
link_graph_count_refs = None
link_graph_is_valid_ref = None

if _HAS_RUST_BINDINGS:
    with suppress(ImportError):
        from omni_core_rs import (
            link_graph_count_refs,
            link_graph_extract_entity_refs,
            link_graph_get_ref_stats,
            link_graph_is_valid_ref,
        )

__all__ = [
    "_HAS_RUST_BINDINGS",
    "ChunkMode",
    "KnowledgeCategory",
    "KnowledgeConfig",
    "KnowledgeEntry",
    "KnowledgeSearchQuery",
    "KnowledgeStats",
    "Librarian",
    "get_knowledge_config",
    "link_graph_count_refs",
    "link_graph_extract_entity_refs",
    "link_graph_get_ref_stats",
    "link_graph_is_valid_ref",
    "reset_config",
]
