"""
omni.core.knowledge - Knowledge Management Subsystem

Modules:
- config: Configuration from references.yaml
- knowledge_types: Knowledge entry type definitions (from Rust omni-knowledge)
- librarian: Librarian main class

Usage:
    from omni.core.knowledge import Librarian, ChunkMode, get_knowledge_config
    from omni.core.knowledge.knowledge_types import KnowledgeEntry, KnowledgeCategory

Note:
    This module uses Rust bindings from omni-knowledge crate for
    high-performance knowledge management.
"""

from .config import KnowledgeConfig, get_knowledge_config, reset_config
from .librarian import Librarian, ChunkMode

# Re-export types from knowledge_types (which wraps Rust bindings)
from .knowledge_types import (
    KnowledgeCategory,
    KnowledgeEntry,
    KnowledgeSearchQuery,
    KnowledgeStats,
    _HAS_RUST_BINDINGS,
)

# Also export ZK entity reference extraction functions from Rust bindings
if _HAS_RUST_BINDINGS:
    try:
        from omni_core_rs import (
            zk_extract_entity_refs,
            zk_get_ref_stats,
            zk_count_refs,
            zk_is_valid_ref,
        )
    except ImportError:
        zk_extract_entity_refs = None
        zk_get_ref_stats = None
        zk_count_refs = None
        zk_is_valid_ref = None

__all__ = [
    "KnowledgeConfig",
    "get_knowledge_config",
    "reset_config",
    "Librarian",
    "ChunkMode",
    "KnowledgeCategory",
    "KnowledgeEntry",
    "KnowledgeSearchQuery",
    "KnowledgeStats",
    "zk_extract_entity_refs",
    "zk_get_ref_stats",
    "zk_count_refs",
    "zk_is_valid_ref",
    "_HAS_RUST_BINDINGS",
]
