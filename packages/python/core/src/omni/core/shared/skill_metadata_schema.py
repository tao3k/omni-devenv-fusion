"""Auto-generated Python types from shared schema.
Generated from: skill_metadata.schema
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """Parsed skill metadata from SKILL.md YAML frontmatter."""

    authors: list[str] = Field([], description="Authors who created or maintain this skill.")
    description: str = Field("", description="Human-readable description of the skill's purpose.")
    intents: list[str] = Field(
        [], description="Intents this skill can handle (for intent-based routing)."
    )
    permissions: list[str] = Field(
        [],
        description='Permissions required by this skill (e.g., "filesystem:read", "network:http")\nZero Trust: Empty permissions means NO access to any capabilities.',
    )
    repository: str = Field("", description="Repository URL for the skill source code.")
    require_refs: list[Referencepath] = Field(
        [], description="Paths to required reference files or skills."
    )
    routing_keywords: list[str] = Field(
        [], description="Keywords used for semantic routing and skill selection."
    )
    skill_name: str = Field("", description="Unique name identifying this skill.")
    version: str = Field("", description='Semantic version string (e.g., "1.0.0").')


Referencepath = str
