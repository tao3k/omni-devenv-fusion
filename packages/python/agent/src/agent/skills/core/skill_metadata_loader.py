"""
agent/skills/core/skill_metadata_loader.py
Phase 33: SKILL.md Standardization - Pure SKILL.md Loader

Only supports SKILL.md format - no manifest.json backward compatibility.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import frontmatter

from .skill_metadata import (
    SkillMetadata,
    SkillDefinition,
    SkillMetadataModel,
    ExecutionMode,
    RoutingStrategy,
    SKILL_FILE,
)

# Lazy logger - defer structlog.get_logger() to avoid import overhead
_cached_logger: Any | None = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# =============================================================================
# Skill Metadata Loader
# =============================================================================


class SkillMetadataLoader:
    """
    Loader for SKILL.md format only.

    Parses YAML Frontmatter from SKILL.md files.
    """

    __slots__ = ()

    REQUIRED_FIELDS = {"name", "version"}

    def __init__(self) -> None:
        """Initialize the metadata loader."""
        pass

    # =========================================================================
    # File Detection
    # =========================================================================

    @staticmethod
    def skill_file_exists(skill_path: Path) -> bool:
        """Check if SKILL.md exists in skill directory."""
        return (skill_path / SKILL_FILE).exists()

    # =========================================================================
    # Metadata Loading
    # =========================================================================

    async def load_metadata(self, skill_path: Path) -> SkillMetadata | None:
        """
        Load skill metadata from SKILL.md.

        Args:
            skill_path: Path to skill directory

        Returns:
            SkillMetadata instance or None if loading failed
        """
        skill_file = skill_path / SKILL_FILE

        try:
            with open(skill_file, encoding="utf-8") as f:
                post = frontmatter.load(f)

            meta = post.metadata or {}

            # Validate required fields
            for field in self.REQUIRED_FIELDS:
                if field not in meta:
                    _get_logger().error(
                        "Missing required field in SKILL.md",
                        skill=skill_path.name,
                        field=field,
                        file=str(skill_file),
                    )
                    return None

            # Use Pydantic model for validation
            model = SkillMetadataModel.model_validate(meta)
            return model.to_metadata()

        except FileNotFoundError:
            _get_logger().error(
                "SKILL.md not found",
                skill=skill_path.name,
                file=str(skill_file),
            )
            return None
        except Exception as e:
            _get_logger().error(
                "Failed to parse SKILL.md",
                skill=skill_path.name,
                error=str(e),
                file=str(skill_file),
            )
            return None

    # =========================================================================
    # Full Definition Loading
    # =========================================================================

    async def load_definition(self, skill_path: Path) -> SkillDefinition | None:
        """
        Load complete skill definition from SKILL.md.

        Args:
            skill_path: Path to skill directory

        Returns:
            SkillDefinition instance or None if loading failed
        """
        metadata = await self.load_metadata(skill_path)
        if metadata is None:
            return None

        skill_file = skill_path / SKILL_FILE
        system_prompt = ""

        try:
            with open(skill_file, encoding="utf-8") as f:
                post = frontmatter.load(f)
            system_prompt = post.content.strip()
        except Exception as e:
            _get_logger().warning(
                "Failed to read SKILL.md content",
                skill=skill_path.name,
                error=str(e),
            )

        return SkillDefinition(
            metadata=metadata,
            system_prompt=system_prompt,
        )

    # =========================================================================
    # Version Utilities
    # =========================================================================

    @staticmethod
    def parse_version(version: str) -> tuple[int, int, int]:
        """Parse semantic version string to tuple."""
        parts = version.split(".")
        return (
            int(parts[0]) if len(parts) > 0 else 0,
            int(parts[1]) if len(parts) > 1 else 0,
            int(parts[2]) if len(parts) > 2 else 0,
        )

    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """Compare two semantic versions."""
        p1 = SkillMetadataLoader.parse_version(v1)
        p2 = SkillMetadataLoader.parse_version(v2)

        for a, b in zip(p1, p2):
            if a < b:
                return -1
            elif a > b:
                return 1

        return 0


# =============================================================================
# Singleton Instance
# =============================================================================

_loader: SkillMetadataLoader | None = None


def get_skill_metadata_loader() -> SkillMetadataLoader:
    """Get the global metadata loader instance."""
    global _loader
    if _loader is None:
        _loader = SkillMetadataLoader()
    return _loader


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "SkillMetadataLoader",
    "get_skill_metadata_loader",
]
