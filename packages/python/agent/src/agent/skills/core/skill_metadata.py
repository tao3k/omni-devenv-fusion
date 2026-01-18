"""
agent/skills/core/skill_metadata.py
Phase 33: SKILL.md Standardization - Data Models (Pure SKILL.md)

Defines the canonical data structures for skill metadata.
Only supports SKILL.md format - no manifest.json backward compatibility.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field
from dataclasses import dataclass

if TYPE_CHECKING:
    pass

# =============================================================================
# Type Aliases (PEP 695)
# =============================================================================

type SkillName = str
type SkillVersion = str
type FilePath = str


# =============================================================================
# Enums
# =============================================================================


class ExecutionMode(StrEnum):
    """Execution mode for a skill."""

    LIBRARY = "library"  # Load as Python module in-process
    SUBPROCESS = "subprocess"  # Execute in isolated subprocess


class RoutingStrategy(StrEnum):
    """Strategy for routing requests to a skill."""

    KEYWORD = "keyword"  # Match on routing_keywords
    INTENT = "intent"  # Match on intents
    HYBRID = "hybrid"  # Combine both strategies


# =============================================================================
# Data Models
# =============================================================================


@dataclass(slots=True, frozen=True)
class SkillMetadata:
    """
    Skill metadata extracted from YAML Frontmatter.

    This is the "State" component of Trinity Architecture.
    """

    name: SkillName
    version: SkillVersion
    description: str = ""
    authors: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.LIBRARY
    routing_strategy: RoutingStrategy = RoutingStrategy.KEYWORD
    routing_keywords: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    dependencies: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "authors": self.authors,
            "execution_mode": self.execution_mode.value,
            "routing_strategy": self.routing_strategy.value,
            "routing_keywords": self.routing_keywords,
            "intents": self.intents,
            "dependencies": self.dependencies,
            "permissions": self.permissions,
        }


@dataclass(slots=True, frozen=True)
class SkillDefinition:
    """
    Complete skill definition from SKILL.md.

    Combines metadata (State) with system prompt (Context).
    """

    metadata: SkillMetadata
    system_prompt: str = ""  # Markdown content after frontmatter


class SkillMetadataModel(BaseModel):
    """
    Pydantic model for metadata validation from SKILL.md frontmatter.
    """

    model_config = ConfigDict(frozen=True, strict=False)  # Allow string to enum coercion

    # Required fields
    name: SkillName
    version: SkillVersion

    # Optional fields with defaults
    description: str = ""
    authors: list[str] = Field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.LIBRARY
    routing_strategy: RoutingStrategy = RoutingStrategy.KEYWORD
    routing_keywords: list[str] = Field(default_factory=list)
    intents: list[str] = Field(default_factory=list)
    dependencies: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)

    def to_metadata(self) -> SkillMetadata:
        """Convert to SkillMetadata dataclass."""
        return SkillMetadata(
            name=self.name,
            version=self.version,
            description=self.description,
            authors=self.authors,
            execution_mode=self.execution_mode,
            routing_strategy=self.routing_strategy,
            routing_keywords=self.routing_keywords,
            intents=self.intents,
            dependencies=self.dependencies,
            permissions=self.permissions,
        )


# =============================================================================
# Constants
# =============================================================================

SKILL_FILE = "SKILL.md"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "SkillName",
    "SkillVersion",
    "FilePath",
    "ExecutionMode",
    "RoutingStrategy",
    "SkillMetadata",
    "SkillDefinition",
    "SkillMetadataModel",
    "SKILL_FILE",
]
