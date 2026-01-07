"""
agent/core/protocols.py
Phase 29: Unified Skill Protocols

Provides type-safe abstractions for the skill system.
All skill components implement these protocols for interchangeability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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

if TYPE_CHECKING:
    from agent.core.schemas import SkillManifest


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
# Data Transfer Objects (Slots-optimized)
# =============================================================================


@dataclass(slots=True)
class SkillCommandConfig:
    """Configuration for a skill command."""

    name: str
    func: Callable[..., Any]
    description: str = ""
    category: SkillCategory = SkillCategory.GENERAL
    inject_root: bool = False
    inject_settings: tuple[str, ...] = ()


@dataclass(slots=True)
class SkillInfo:
    """Lightweight skill metadata for listing."""

    name: str
    version: str
    description: str
    command_count: int = 0
    category: SkillCategory = SkillCategory.GENERAL
    execution_mode: ExecutionMode = ExecutionMode.LIBRARY


@dataclass(slots=True)
class ExecutionResult:
    """Result of command execution."""

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


@dataclass(slots=True)
class SecurityAssessment:
    """Complete security assessment result."""

    decision: SecurityDecision
    score: int
    findings_count: int
    is_trusted: bool = False
    reason: str = ""
    details: dict = field(default_factory=dict)


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
