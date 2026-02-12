"""
schemas.py - Skill Evolution Data Models

Pydantic models for structured skill crystallization pipeline.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CandidateSkill(BaseModel):
    """
    Represents a skill proposed by the Harvester, ready for the Factory.

    This is the "middle state" between raw execution trace and executable skill.
    It captures the refined logic extracted from traces.
    Supports XML Q&A Augmentation for better LLM comprehension and tool usage.
    """

    suggested_name: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description="snake_case skill name, e.g., 'batch_image_convert'",
    )

    description: str = Field(
        ...,
        min_length=10,
        max_length=200,
        description="One line summary of what the skill does",
    )

    category: str = Field(
        default="automation",
        description="Skill category, e.g., 'git', 'system', 'data', 'file'",
    )

    nushell_script: str = Field(
        ...,
        description="The optimized Nushell script to execute",
    )

    parameters: dict[str, str] = Field(
        ...,
        description="Parameter definitions: {name: type_description}",
    )

    # XML Q&A Augmentation Data (Claude Cookbook best practice)
    usage_scenarios: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of {'input': '...', 'reasoning': '...'} for XML scenarios",
    )

    faq_items: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of {'q': '...', 'a': '...'} for XML FAQ",
    )

    # Metadata
    original_task: str = Field(
        ...,
        description="Original task description from the trace",
    )

    trace_id: str = Field(
        ...,
        description="Source trace ID for provenance",
    )

    reasoning: str = Field(
        ...,
        description="Why this should be a skill: frequency, complexity, utility",
    )

    # Metadata for lifecycle management
    confidence_score: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Harvester confidence in the extraction quality",
    )

    estimated_complexity: str = Field(
        default="low",
        description="Complexity assessment: low, medium, high",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "suggested_name": "batch_file_rename",
                "description": "Rename multiple files matching a pattern with new extension",
                "category": "file",
                "nushell_script": "for f in (glob $pattern) { mv $f ($f | str replace -r $old_ext $new_ext) }",
                "parameters": {
                    "pattern": "Glob pattern for files (e.g., '*.txt')",
                    "old_ext": "Extension to replace (e.g., '.txt')",
                    "new_ext": "New extension (e.g., '.md')",
                },
                "usage_scenarios": [
                    {
                        "input": "pattern='*.txt', old_ext='.txt', new_ext='.md'",
                        "reasoning": "Convert text files to markdown",
                    },
                    {
                        "input": "pattern='*.bak', old_ext='.bak', new_ext=''",
                        "reasoning": "Remove backup extension",
                    },
                ],
                "faq_items": [
                    {
                        "q": "What if no files match the pattern?",
                        "a": "The script runs safely with zero iterations",
                    },
                    {
                        "q": "Can I use regex in the extension?",
                        "a": "Yes, the -r flag enables regex matching",
                    },
                ],
                "original_task": "Rename all .txt files to .md",
                "trace_id": "20260130_120000_task_abc123_0",
                "reasoning": "Executed 5 times with 100% success rate. Common file management task.",
                "confidence_score": 0.95,
                "estimated_complexity": "low",
            }
        }
    )


class SkillTemplateContext(BaseModel):
    """Context for rendering skill templates."""

    skill_name: str
    skill_description: str
    category: str
    nushell_script: str
    parameters: dict[str, str]
    original_task: str
    trace_id: str
    reasoning: str

    def to_template_vars(self) -> dict[str, Any]:
        """Convert to template variables."""
        return {
            "skill_name": self.skill_name,
            "skill_description": self.skill_description,
            "category": self.category,
            "nushell_script": self.nushell_script,
            "parameters": self.parameters,
            "param_names": list(self.parameters.keys()),
            "original_task": self.original_task,
            "trace_id": self.trace_id,
            "reasoning": self.reasoning,
        }


class CrystallizationResult(BaseModel):
    """Result of a skill crystallization attempt."""

    success: bool
    skill_path: str | None = None
    skill_name: str | None = None
    error: str | None = None
    files_created: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "skill_path": "/project/assets/skills/learned/batch_file_rename",
                "skill_name": "batch_file_rename",
                "error": None,
                "files_created": ["SKILL.md", "scripts/batch_file_rename.py", "README.md"],
            }
        }
    )


class HarvesterAnalysisResult(BaseModel):
    """Result of harvester trace analysis."""

    trace_id: str
    is_worthy: bool
    candidate: CandidateSkill | None = None
    skip_reason: str | None = None
    confidence: float = 0.0


__all__ = [
    "CandidateSkill",
    "SkillTemplateContext",
    "CrystallizationResult",
    "HarvesterAnalysisResult",
]
