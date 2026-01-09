"""
agent/skills/core - Core skill loading and management

Module contents:
- skill_manifest_loader: SKILL.md parsing and metadata extraction
- skill_manifest: Pydantic models for skill metadata
- test_framework: Pytest plugin for dynamic skill fixture generation
- task: @script_task decorator for atomic script implementations

This package provides pure SKILL.md support and skill testing utilities.
"""

from .skill_manifest_loader import get_manifest_loader, SkillManifestLoader
from .skill_manifest import SkillManifestModel, SkillMetadata, ExecutionMode
from .test_framework import (
    test,
    test_skill,  # alias
    fixture,
    unwrap,
    list_skills,
    skills_root,
    project_root,
)
from .task import script_task, is_script_task, get_task_metadata, run_script_as_cli

__all__ = [
    "get_manifest_loader",
    "SkillManifestLoader",
    "SkillManifestModel",
    "SkillMetadata",
    "ExecutionMode",
    "test",
    "test_skill",
    "fixture",
    "unwrap",
    "list_skills",
    "skills_root",
    "project_root",
    "script_task",
    "is_script_task",
    "get_task_metadata",
    "run_script_as_cli",
]
