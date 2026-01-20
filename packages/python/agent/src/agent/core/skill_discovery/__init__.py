"""
src/agent/core/skill_discovery/
 The Librarian - Vector-Based Skill Discovery

Atomic modules following ODF patterns:
- indexing.py: Vector-based skill discovery
- parser.py: Rust-based SKILL.md parsing (single source of truth)
- reconciliation.py: Index reconciliation

Usage:
    from agent.core.skill_discovery import (
        SkillDiscovery,
        parse_skill_md,
        is_rust_available,
    )
"""

# Vector-based skill discovery
from .indexing import (
    SkillDiscovery,
    reindex_skills_from_manifests,
    search_skills,
    SKILL_REGISTRY_COLLECTION,
)

# Rust-based parser (primary, single source of truth)
from .parser import (
    parse_skill_md,
    parse_skill_md_from_content,
    is_rust_available,
)

# Reconciliation
from .reconciliation import reconcile_index

__all__ = [
    # Discovery
    "SkillDiscovery",
    "reindex_skills_from_manifests",
    "search_skills",
    "SKILL_REGISTRY_COLLECTION",
    # Rust Parser (single source of truth)
    "parse_skill_md",
    "parse_skill_md_from_content",
    "is_rust_available",
    # Reconciliation
    "reconcile_index",
]
