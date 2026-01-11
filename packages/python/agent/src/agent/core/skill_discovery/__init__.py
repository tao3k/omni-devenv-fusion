"""
src/agent/core/skill_discovery/
Phase 27: Skill Discovery Package

Atomic modules following ODF patterns:
- local.py: Legacy local index (SkillDiscovery)
- vector.py: Vector-based discovery (VectorSkillDiscovery)
- indexing.py: Index management functions
- reconciliation.py: Startup cleanup

Usage:
    from agent.core.skill_discovery import (
        SkillDiscovery,
        VectorSkillDiscovery,
        reindex_skills_from_manifests,
        index_single_skill,
        reconcile_index,
    )
"""

# Local discovery (legacy)
from .local import SkillDiscovery, KNOWN_SKILLS_INDEX, discover_skills, suggest_for_task

# Vector discovery (Phase 36)
from .vector import VectorSkillDiscovery, vector_search_skills, vector_suggest_for_task

# Index management
from .indexing import (
    reindex_skills_from_manifests,
    index_single_skill,
    remove_skill_from_index,
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
    "index_single_skill",
    "remove_skill_from_index",
    "SKILL_REGISTRY_COLLECTION",
    # Reconciliation
    "reconcile_index",
]
