"""
src/agent/core/skill_discovery/
 The Librarian - Vector-Based Skill Discovery

Atomic modules following ODF patterns:
- indexing.py: Vector-based skill discovery
- reconciliation.py: Index reconciliation

Usage:
    from agent.core.skill_discovery import (
        SkillDiscovery,
        reindex_skills_from_manifests,
        search_skills,
    )
"""

# Vector-based skill discovery
from .indexing import (
    SkillDiscovery,
    reindex_skills_from_manifests,
    search_skills,
    SKILL_REGISTRY_COLLECTION,
)

# Reconciliation
from .reconciliation import reconcile_index

__all__ = [
    # Discovery
    "SkillDiscovery",
    "reindex_skills_from_manifests",
    "search_skills",
    "SKILL_REGISTRY_COLLECTION",
    # Reconciliation
    "reconcile_index",
]
