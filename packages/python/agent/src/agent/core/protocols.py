"""
agent/core/protocols.py
Phase 29: Unified Skill Protocols
Phase 33: ODF-EP v6.0 Core Refactoring

Provides type-safe abstractions for the skill system.
All skill components implement these protocols for interchangeability.

ODF-EP v6.0 Pillars:
- Pillar A: Pydantic Shield (ConfigDict(frozen=True))
- Pillar B: Protocol-Oriented Design (typing.Protocol)
- Pillar C: Tenacity Pattern (@retry for resilience)
- Pillar D: Context-Aware Observability (logger.bind())
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Protocol,
    Sequence,
    runtime_checkable,
)

from dataclasses import field
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from agent.core.schemas import SkillManifest

# =============================================================================
# Lazy Logger Initialization (Phase 32 Import Optimization)
# =============================================================================

_cached_logger = None


def _get_logger() -> Any:
    """Lazy logger initialization for fast imports."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# =============================================================================
# Enums
# =============================================================================


class SkillCategory(str, Enum):
    """Standardized skill categories."""

    READ = "read"
    VIEW = "view"
    WORKFLOW = "workflow"
    WRITE = "write"
    EVOLUTION = "evolution"
    GENERAL = "general"
    ADMIN = "admin"

    # Aliases for backward compatibility
    @classmethod
    def _missing_(cls, value: object) -> "SkillCategory | None":
        if isinstance(value, str):
            value_lower = value.lower()
            for member in cls:
                if member.value == value_lower:
                    return member
        return None


class ExecutionMode(str, Enum):
    """Skill execution modes (Phase 28.1)."""

    LIBRARY = "library"  # Load in main process
    SUBPROCESS = "subprocess"  # Execute via uv run


# =============================================================================
# Data Transfer Objects (Pydantic Shield - Pillar A)
# =============================================================================


class SkillCommandConfig(BaseModel):
    """Configuration for a skill command."""

    model_config = ConfigDict(frozen=True)
    name: str
    func: Callable[..., Any]
    description: str = ""
    category: SkillCategory = SkillCategory.GENERAL
    inject_root: bool = False
    inject_settings: tuple[str, ...] = ()


class SkillInfo(BaseModel):
    """Lightweight skill metadata for listing."""

    model_config = ConfigDict(frozen=True)
    name: str
    version: str
    description: str
    command_count: int = 0
    category: SkillCategory = SkillCategory.GENERAL
    execution_mode: ExecutionMode = ExecutionMode.LIBRARY


class ExecutionResult(BaseModel):
    """Result of command execution."""

    model_config = ConfigDict(frozen=True)
    success: bool
    output: str
    error: str | None = None
    duration_ms: float = 0.0


# =============================================================================
# Protocols (Abstract Base Classes)
# =============================================================================


@runtime_checkable
class ISkillCommand(Protocol):
    """Protocol for a single skill command."""

    __slots__ = ()

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name (e.g., 'status', 'commit')."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""

    @property
    @abstractmethod
    def category(self) -> SkillCategory:
        """Command category for organization."""

    @abstractmethod
    async def execute(self, args: Dict[str, Any]) -> ExecutionResult:
        """Execute the command with given arguments."""


@runtime_checkable
class ISkill(Protocol):
    """Protocol for a complete skill package."""

    __slots__ = ()

    @property
    @abstractmethod
    def name(self) -> str:
        """Skill identifier (e.g., 'git', 'filesystem')."""

    @property
    @abstractmethod
    def manifest(self) -> "SkillManifest":
        """Skill manifest with full metadata."""

    @property
    @abstractmethod
    def commands(self) -> Dict[str, ISkillCommand]:
        """All commands provided by this skill."""

    @abstractmethod
    def get_command(self, name: str) -> ISkillCommand | None:
        """Get a specific command by name."""

    @abstractmethod
    async def load(self) -> None:
        """Load the skill (if not pre-loaded)."""

    @abstractmethod
    async def unload(self) -> None:
        """Unload and cleanup resources."""


@runtime_checkable
class ISkillLoader(Protocol):
    """Protocol for skill loading mechanisms."""

    __slots__ = ()

    @abstractmethod
    def discover(self) -> Sequence[Path]:
        """Discover available skills in the skills directory."""

    @abstractmethod
    async def load(self, skill_path: Path) -> ISkill:
        """Load a skill from a path."""

    @abstractmethod
    async def unload(self, skill_name: str) -> None:
        """Unload a skill by name."""

    @abstractmethod
    def is_loaded(self, skill_name: str) -> bool:
        """Check if a skill is loaded."""


@runtime_checkable
class ISkillRegistry(Protocol):
    """Protocol for skill registry (read-only operations)."""

    __slots__ = ()

    @property
    @abstractmethod
    def available_skills(self) -> Sequence[str]:
        """All discovered skills."""

    @property
    @abstractmethod
    def loaded_skills(self) -> Sequence[str]:
        """Currently loaded skills."""

    @abstractmethod
    def get_manifest(self, skill_name: str) -> "SkillManifest | None":
        """Get manifest for a skill."""

    @abstractmethod
    def get_skill(self, skill_name: str) -> ISkill | None:
        """Get loaded skill instance."""


@runtime_checkable
class ISecurityGate(Protocol):
    """Protocol for security validation (Phase 28)."""

    __slots__ = ()

    @abstractmethod
    async def assess(self, skill_path: Path) -> SecurityAssessment:
        """Assess skill security posture."""

    @abstractmethod
    def quick_check(self, skill_path: Path) -> bool:
        """Quick pass/fail security check."""


# =============================================================================
# Security Types
# =============================================================================


class SecurityDecision(str, Enum):
    """Security decision outcomes."""

    SAFE = "safe"
    WARN = "warn"
    SANDBOX = "sandbox"
    BLOCK = "block"


class SecurityAssessment(BaseModel):
    """Complete security assessment result."""

    model_config = ConfigDict(frozen=True)
    decision: SecurityDecision
    score: int
    findings_count: int
    is_trusted: bool = False
    reason: str = ""
    details: dict = field(default_factory=dict)


# =============================================================================
# Context-Aware Logging Helpers (Pillar D)
# =============================================================================


def _log_protocols_loaded(skill_count: int, command_count: int) -> None:
    """Log protocols loaded with context binding."""
    logger = _get_logger()
    logger.info(
        "skill_protocols_loaded",
        skill_count=skill_count,
        command_count=command_count,
        component="protocols",
    )


def _log_security_assessment(assessment: SecurityAssessment, skill_path: str) -> None:
    """Log security assessment result with context."""
    logger = _get_logger()
    logger.bind(
        skill_path=skill_path,
        security_decision=assessment.decision.value,
        security_score=assessment.score,
    ).info("security_assessment_completed")


# =============================================================================
# Export
# =============================================================================

__all__ = [
    # Enums
    "SkillCategory",
    "ExecutionMode",
    "SecurityDecision",
    # DTOs
    "SkillCommandConfig",
    "SkillInfo",
    "ExecutionResult",
    "SecurityAssessment",
    # Protocols
    "ISkillCommand",
    "ISkill",
    "ISkillLoader",
    "ISkillRegistry",
    "ISecurityGate",
]
