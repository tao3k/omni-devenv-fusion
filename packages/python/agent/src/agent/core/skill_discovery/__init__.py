"""
src/agent/core/skill_discovery/
Phase 66: The Librarian - Simplified VectorMemory Adapter

Atomic modules following ODF patterns:
- indexing.py: Lightweight adapter for Rust-backed VectorMemory
- local.py: Legacy local index (still used for some orchestration)

Usage:
    from agent.core.skill_discovery import (
        SkillDiscovery,
        reindex_skills_from_manifests,
        vector_search_skills,
    )
"""

# Local discovery (legacy - still used by some components)
from .local import SkillDiscovery, KNOWN_SKILLS_INDEX, discover_skills, suggest_for_task

# Vector discovery (Phase 36 - ChromaDB-based, still used by some components)
from .vector import VectorSkillDiscovery, vector_search_skills, vector_suggest_for_task

# Index management - Phase 66: Rust-backed adapter
from .indexing import (
    reindex_skills_from_manifests,
    SKILL_REGISTRY_COLLECTION,
)

# Reconciliation (Phase 36.6)
from .reconciliation import reconcile_index

__all__ = [
    # Local discovery
    "SkillDiscovery",
    "KNOWN_SKILLS_INDEX",
    "discover_skills",
    "suggest_for_task",
    # Vector discovery
    "VectorSkillDiscovery",
    "vector_search_skills",
    "vector_suggest_for_task",
    # Index management
    "reindex_skills_from_manifests",
    "SKILL_REGISTRY_COLLECTION",
    # Reconciliation
    "reconcile_index",
]
