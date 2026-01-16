# agent/core/loader/__init__.py
"""
Unified Skill Loader Pipeline Package.

Complete pipeline: Discover → Validate → Install → Load → Register

Design:
- Single entry point for all skill operations
- Pluggable validators and security checks
- Structured concurrency for parallel loading

Usage:
    from agent.core.loader import SkillLoader, load_skills, quick_load

    # Load all skills
    results, stats = load_skills()

    # Quick load single skill
    result = quick_load("git")
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

# Re-export configuration classes
from .config import (
    LoaderConfig,
    LoadResult,
    PipelineStats,
)

# Re-export stages
from .stages import (
    DiscoveryStage,
    ValidationStage,
    SecurityStage,
)

# Re-export main loader
from .pipeline import SkillLoader


# =============================================================================
# Convenience Functions
# =============================================================================


def load_skills(
    skills_dir: Path | None = None,
    *,
    parallel: bool = True,
    security: bool = True,
    on_progress: Callable[[LoadResult], None] | None = None,
) -> tuple[list[LoadResult], PipelineStats]:
    """
    Convenience function to load all skills.

    Usage:
        results, stats = load_skills()

        for result in results:
            if result.success:
                print(f"✓ {result.skill_name}")
            else:
                print(f"✗ {result.skill_name}: {result.error}")
    """
    config = LoaderConfig(
        parallel_loading=parallel,
        security_enabled=security,
    )

    loader = SkillLoader(config=config)
    return loader.load_all(skills_dir, on_progress=on_progress)


def quick_load(skill_name: str, skills_dir: Path | None = None) -> LoadResult:
    """
    Quickly load a single skill by name.

    Usage:
        result = quick_load("git")
        if result.success:
            print(f"Loaded {result.skill_name}")
    """
    from common.skills_path import SKILLS_DIR

    if skills_dir is None:
        skills_dir = SKILLS_DIR()

    skill_path = skills_dir / skill_name
    if not skill_path.exists():
        return LoadResult(
            success=False,
            skill_name=skill_name,
            skill_path=skill_path,
            error="Skill directory not found",
        )

    loader = SkillLoader()
    return loader.load(skill_path)


__all__ = [
    # Configuration
    "LoaderConfig",
    "LoadResult",
    "PipelineStats",
    # Stages
    "DiscoveryStage",
    "ValidationStage",
    "SecurityStage",
    # Main loader
    "SkillLoader",
    # Convenience functions
    "load_skills",
    "quick_load",
]
