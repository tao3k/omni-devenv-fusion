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
from .task import script_task, is_script_task, get_task_metadata, run_script_as_cli

# test_framework requires pytest - lazy import to avoid runtime dependency
_test_exports = {
    "test",
    "test_skill",
    "fixture",
    "unwrap",
    "list_skills",
    "skills_root",
    "project_root",
}


def __getattr__(name):
    """Lazy import test_framework symbols to avoid pytest dependency at runtime."""
    if name in _test_exports:
        from . import test_framework

        return getattr(test_framework, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
