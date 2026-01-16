"""
agent/core/loader.py
Unified Skill Loader Pipeline

This file is a backward compatibility wrapper.
The actual implementation is now in agent.core.loader package.

Complete pipeline: Discover → Validate → Install → Load → Register

Design:
- Single entry point for all skill operations
- Pluggable validators and security checks
- Structured concurrency for parallel loading

Usage:
    # Old import (still works)
    from agent.core.loader import SkillLoader, load_skills

    # New import (recommended)
    from agent.core.loader import SkillLoader, load_skills, quick_load
"""

from __future__ import annotations

# Re-export everything from the loader package for backward compatibility
from agent.core.loader import (
    # Configuration
    LoaderConfig,
    LoadResult,
    PipelineStats,
    # Stages
    DiscoveryStage,
    ValidationStage,
    SecurityStage,
    # Main loader
    SkillLoader,
    # Convenience functions
    load_skills,
    quick_load,
)

__all__ = [
    "LoaderConfig",
    "LoadResult",
    "PipelineStats",
    "DiscoveryStage",
    "ValidationStage",
    "SecurityStage",
    "SkillLoader",
    "load_skills",
    "quick_load",
]
