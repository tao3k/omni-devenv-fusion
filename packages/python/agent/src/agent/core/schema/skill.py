# schema/skill.py
# Phase 13: Skill Architecture

from typing import List, Optional

from pydantic import BaseModel, Field


class SkillDependencies(BaseModel):
    """Skill dependency configuration (Manifest v2.0)."""

    skills: dict = Field(
        default_factory=dict, description="Skill dependencies with version constraints"
    )
    python: dict = Field(
        default_factory=dict, description="Python package dependencies with version constraints"
    )


class SkillManifest(BaseModel):
    """Metadata for a dynamically loadable skill (Manifest v2.0)."""

    model_config = {"extra": "allow"}  # Allow extra fields like routing_keywords

    # v2.0 new fields
    manifest_version: str = Field(default="1.0.0", description="Manifest version format")
    type: str = Field(default="skill", description="Component type: skill, agent, instruction")
    name: str = Field(..., description="Unique skill identifier (e.g., 'git')")
    version: str = Field(..., description="Semantic version")
    description: str = Field(..., description="What this skill does")
    author: str = Field(default="omni-dev-fusion", description="Skill author")
    license: str = Field(default="Apache-2.0", description="License identifier")

    repository: Optional[dict] = Field(
        None, description="Repository configuration with type, url, and directory"
    )

    # v1.x fields (kept for backward compatibility)
    routing_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords for semantic routing (e.g., ['git', 'commit', 'push'])",
    )
    intents: List[str] = Field(default_factory=list, description="Intent types this skill handles")

    # v2.0 dependencies (replaces v1.x List[str])
    dependencies: SkillDependencies = Field(
        default_factory=SkillDependencies, description="Dependencies configuration"
    )

    tools_module: str = Field(
        ..., description="Python module path containing the tool registration logic"
    )
    workflow_module: Optional[str] = Field(
        None, description="Workflow module path for skills with complex workflows"
    )
    state_module: Optional[str] = Field(
        None, description="State module path for skills with persistent state"
    )
    guide_file: str = Field(
        default="README.md", description="Path to the markdown guide file (relative to skill dir)"
    )
    prompts_file: Optional[str] = Field(
        None, description="Path to system prompts file (relative to skill dir)"
    )


# Rebuild models after all classes are defined
SkillDependencies.model_rebuild()
SkillManifest.model_rebuild()


__all__ = ["SkillDependencies", "SkillManifest"]
