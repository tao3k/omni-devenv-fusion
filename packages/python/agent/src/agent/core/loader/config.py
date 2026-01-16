# agent/core/loader/config.py
"""
Configuration for skill loading pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.core.protocols import SecurityAssessment
    from agent.core.skill_manager import Skill


@dataclass(slots=True)
class LoaderConfig:
    """Configuration for skill loading pipeline."""

    # Discovery options
    discover_patterns: tuple[str, ...] = ("SKILL.md",)

    # Security options
    security_enabled: bool = True
    trust_local_skills: bool = True

    # Performance options
    parallel_loading: bool = True
    max_concurrent: int = 4

    # Validation options
    require_manifest: bool = True
    require_tools: bool = True


@dataclass(slots=True)
class LoadResult:
    """Result of loading a skill."""

    success: bool
    skill_name: str
    skill_path: Path
    error: str | None = None
    assessment: "SecurityAssessment | None" = None
    loaded_skill: "Skill | None" = None


@dataclass(slots=True)
class PipelineStats:
    """Statistics for the loading pipeline."""

    discovered: int = 0
    loaded: int = 0
    failed: int = 0
    blocked: int = 0
    skipped: int = 0
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovered": self.discovered,
            "loaded": self.loaded,
            "failed": self.failed,
            "blocked": self.blocked,
            "skipped": self.skipped,
            "duration_ms": round(self.duration_ms, 2),
        }


__all__ = ["LoaderConfig", "LoadResult", "PipelineStats"]
