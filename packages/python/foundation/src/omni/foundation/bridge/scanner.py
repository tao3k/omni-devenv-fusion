"""
scanner.py - Skill Index Reader

This module implements the "Reader" part of the Rust-First Indexing architecture.
It reads from LanceDB (Single Source of Truth) instead of scanning file system.

Migration Context:
- Source: LanceDB (populated by `omni skill sync`)
- Consumer: Python Kernel (via this module)
- Logic: Read-Only, Fast Startup
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Apply nest_asyncio patch early to allow nested event loops (needed for pytest)
try:
    import nest_asyncio

    nest_asyncio.apply()
except ImportError:
    pass

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.foundation.scanner")


class SnifferRule:
    """Represents a single sniffer rule loaded from the index."""

    def __init__(self, rule_type: str, pattern: str):
        self.rule_type = rule_type  # "file_exists" or "file_pattern"
        self.pattern = pattern

    def __repr__(self) -> str:
        return f"SnifferRule(type={self.rule_type}, pattern={self.pattern})"

    def to_dict(self) -> dict[str, str]:
        return {"type": self.rule_type, "pattern": self.pattern}


class DiscoveredSkillRules:
    """Rules and metadata for a skill loaded from the index."""

    def __init__(
        self,
        skill_name: str,
        skill_path: str,
        rules: list[SnifferRule] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.skill_name = skill_name
        self.skill_path = skill_path
        self.rules = rules or []
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"DiscoveredSkillRules({self.skill_name}, {len(self.rules)} rules)"

    def to_list_of_dicts(self) -> list[dict[str, str]]:
        return [rule.to_dict() for rule in self.rules]


class PythonSkillScanner:
    """
    Skill Index Reader.

    Reads from LanceDB (populated by Rust scanner).
    """

    async def scan_directory(self) -> list[DiscoveredSkillRules]:
        """
        Load skills from LanceDB.

        Returns:
            List of DiscoveredSkillRules with rules and metadata.
        """
        try:
            from omni.foundation.bridge import RustVectorStore
            from omni.foundation.config.dirs import get_vector_db_path

            # Use skills.lance specifically for tool registry
            skills_path = str(Path(get_vector_db_path()) / "skills.lance")
            store = RustVectorStore(skills_path)

            # Use await instead of asyncio.run
            tools = await store.list_all_tools()

            # Group tools by skill_name
            skills_by_name: dict[str, dict] = {}
            for tool in tools:
                skill_name = tool.get("skill_name", "unknown")
                file_path = tool.get("file_path", "")

                # Extract skill directory from file_path (e.g., "/path/to/skills/git/scripts/x.py" -> "assets/skills/git")
                if "/assets/skills/" in file_path:
                    # Full relative path from project root
                    skill_path = file_path.split("/assets/skills/")[-1].split("/")[0]
                    skill_path = f"assets/skills/{skill_path}"
                else:
                    # Fallback: use skill_name
                    skill_path = f"assets/skills/{skill_name}"

                if skill_name not in skills_by_name:
                    skills_by_name[skill_name] = {
                        "name": skill_name,
                        "path": skill_path,
                        "rules": [],
                        "metadata": {
                            "description": tool.get("description", ""),
                            "tools": [],
                        },
                    }
                # Add tool to metadata
                skills_by_name[skill_name]["metadata"]["tools"].append(
                    {
                        "name": tool.get("tool_name", ""),
                        "description": tool.get("description", ""),
                    }
                )

            # Convert to DiscoveredSkillRules
            skills = []
            for skill_data in skills_by_name.values():
                rules = [SnifferRule("file_pattern", skill_data["path"])]
                skills.append(
                    DiscoveredSkillRules(
                        skill_name=skill_data["name"],
                        skill_path=skill_data["path"],
                        rules=rules,
                        metadata=skill_data["metadata"],
                    )
                )

            logger.info(f"Loaded {len(skills)} skills from LanceDB")
            return skills

        except Exception as e:
            logger.error(f"Failed to load skills from LanceDB: {e}")
            return []

    async def parse_skill_metadata(self, skill_path: str) -> dict[str, Any]:
        """
        Retrieve metadata for a specific skill.

        Args:
            skill_path: Path to the skill directory.

        Returns:
            Metadata dict for the skill.
        """
        skills = await self.scan_directory()
        for skill in skills:
            if skill.skill_path == skill_path or skill.skill_path.endswith(skill_path):
                return skill.metadata
        return {"name": skill_path}


async def scan_skills_with_rules() -> list[DiscoveredSkillRules]:
    """Convenience function to load skills from LanceDB."""
    scanner = PythonSkillScanner()
    return await scanner.scan_directory()


__all__ = [
    "DiscoveredSkillRules",
    "PythonSkillScanner",
    "SnifferRule",
    "scan_skills_with_rules",
]
