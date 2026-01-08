"""
agent/skills/core - Core skill loading and management

Module contents:
- skill_manifest_loader: SKILL.md parsing and metadata extraction
- skill_manifest: Pydantic models for skill metadata

This package provides pure SKILL.md support.
"""

from .skill_manifest_loader import get_manifest_loader, SkillManifestLoader
from .skill_manifest import SkillManifestModel, SkillMetadata, ExecutionMode

__all__ = [
    "get_manifest_loader",
    "SkillManifestLoader",
    "SkillManifestModel",
    "SkillMetadata",
    "ExecutionMode",
]
