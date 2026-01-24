"""
rust_scanner.py - Skill Scanner Implementation

Rust-powered skill discovery using skills-scanner crate.
Provides high-performance batch scanning for fast startup.
"""

from __future__ import annotations

import os
from typing import Any

from omni.foundation.config.logging import get_logger

try:
    import omni_core_rs as _rust

    RUST_AVAILABLE = True
except ImportError:
    _rust = None
    RUST_AVAILABLE = False

from .interfaces import SkillScannerProvider
from .types import SkillStructure

logger = get_logger("omni.bridge.scanner")


class RustSkillScanner(SkillScannerProvider):
    """Skill scanner implementation using Rust bindings."""

    def __init__(self):
        if not RUST_AVAILABLE:
            raise RuntimeError("Rust bindings not installed. Run: just build-rust-dev")

        logger.info("Initialized RustSkillScanner")

    def scan_skill(self, skill_path: str) -> SkillStructure:
        """Scan a skill directory and extract its structure."""
        try:
            metadata = _rust.scan_skill(skill_path)
            if metadata is None:
                return SkillStructure(
                    skill_name=skill_path.split("/")[-1],
                    skill_path=skill_path,
                )

            return SkillStructure(
                skill_name=metadata.skill_name,
                skill_path=skill_path,
                routing_keywords=getattr(metadata, "routing_keywords", []),
                metadata={
                    "version": getattr(metadata, "version", "1.0.0"),
                    "description": getattr(metadata, "description", ""),
                    "authors": getattr(metadata, "authors", []),
                    "intents": getattr(metadata, "intents", []),
                    "require_refs": getattr(metadata, "require_refs", []),
                    "repository": getattr(metadata, "repository", ""),
                },
            )
        except Exception as e:
            logger.error(f"Failed to scan skill {skill_path}: {e}")
            return SkillStructure(
                skill_name=skill_path.split("/")[-1],
                skill_path=skill_path,
            )

    def scan_all_skills(self, base_path: str) -> list[SkillStructure]:
        """Scan all skills in a base directory using Rust.

        This is the high-performance batch scanning method.
        Uses Rust's concurrent file traversal and YAML parsing.
        """
        if not os.path.isdir(base_path):
            logger.warning(f"Skill base path not found: {base_path}")
            return []

        skills = []

        try:
            # Use Rust's scan_skill_tools for batch scanning
            tool_records = _rust.scan_skill_tools(base_path)

            # Extract unique skill paths from tool records
            skill_paths_seen = set()
            for tool in tool_records:
                if tool.skill_name and tool.skill_name not in skill_paths_seen:
                    skill_paths_seen.add(tool.skill_name)
                    if tool.file_path:
                        parts = tool.file_path.split(os.sep)
                        try:
                            scripts_idx = parts.index("scripts")
                            full_skill_path = os.path.join(base_path, parts[scripts_idx - 1])
                            if os.path.isdir(full_skill_path):
                                skill = self.scan_skill(full_skill_path)
                                if skill.skill_name:
                                    skills.append(skill)
                        except (ValueError, IndexError):
                            pass

            # Also check for skills without scripts
            if os.path.isdir(base_path):
                for entry in os.listdir(base_path):
                    skill_dir = os.path.join(base_path, entry)
                    if os.path.isdir(skill_dir) and not any(
                        s.skill_path == skill_dir for s in skills
                    ):
                        skill = self.scan_skill(skill_dir)
                        if skill.skill_name:
                            skills.append(skill)

            logger.info(f"⚡ Scanned {len(skills)} skills in {base_path} (Rust)")
            return skills

        except Exception as e:
            logger.error(f"Rust batch scan failed: {e}, falling back to Python")
            return self._fallback_scan_all(base_path)

    def _fallback_scan_all(self, base_path: str) -> list[SkillStructure]:
        """Python fallback for scanning all skills."""
        skills = []
        if not os.path.isdir(base_path):
            return skills

        for entry in os.listdir(base_path):
            skill_dir = os.path.join(base_path, entry)
            if os.path.isdir(skill_dir):
                skill = self.scan_skill(skill_dir)
                if skill.skill_name:
                    skills.append(skill)

        logger.info(f"🔍 Scanned {len(skills)} skills in {base_path} (Python fallback)")
        return skills

    def parse_skill_metadata(self, skill_path: str) -> dict[str, Any]:
        """Parse the SKILL.md YAML frontmatter."""
        metadata = self.scan_skill(skill_path)
        return metadata.metadata

    def extract_scripts(self, skill_path: str) -> list[str]:
        """Extract Python scripts from the skill's scripts directory."""
        scripts_dir = os.path.join(skill_path, "scripts")
        if not os.path.isdir(scripts_dir):
            return []
        return [f[:-3] for f in os.listdir(scripts_dir) if f.endswith(".py") and f != "__init__.py"]

    def find_skill_references(self, skill_path: str) -> list[str]:
        """Find all references mentioned in the skill."""
        metadata = self.scan_skill(skill_path)
        return metadata.metadata.get("require_refs", [])


__all__ = [
    "RUST_AVAILABLE",
    "RustSkillScanner",
]
