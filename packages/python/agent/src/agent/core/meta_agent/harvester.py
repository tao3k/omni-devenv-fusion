"""
agent/core/meta_agent/harvester.py
Phase 64: The Meta-Agent - Skill Harvester

Analyzes session notes to identify frequently-used patterns
and suggests/creates reusable skills.

Usage:
    from agent.core.meta_agent.harvester import SkillHarvester

    harvester = SkillHarvester()
    suggestions = await harvester.analyze_sessions()
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import structlog

from common.config_paths import get_project_root
from common.skills_path import SKILLS_DIR

logger = structlog.get_logger(__name__)


# =============================================================================
# Pattern Extractors
# =============================================================================

# Common tool combinations to detect
TOOL_PATTERNS = [
    (r"(?:git|filesystem)\.(?:read_file|write_file)", "file_operations"),
    (r"(?:search|grep|find)", "search_operations"),
    (r"(?:code_insight|analyze)", "code_analysis"),
    (r"(?:test|pytest)", "testing"),
    (r"(?:commit|push|pull)", "version_control"),
    (r"(?:memory|note|knowledge)", "memory_operations"),
]


# =============================================================================
# Skill Harvester
# =============================================================================


class SkillHarvester:
    """
    Phase 64: Skill Harvester.

    Analyzes session notes to identify patterns that should be
    extracted into reusable skills.
    """

    def __init__(self, sessions_dir: Path | None = None):
        """
        Initialize the harvester.

        Args:
            sessions_dir: Directory containing session notes (defaults to .data/knowledge/sessions)
        """
        if sessions_dir is None:
            # Sessions are runtime data, stored in .data/ (git-ignored)
            self.sessions_dir = get_project_root() / ".data" / "knowledge" / "sessions"
        else:
            self.sessions_dir = sessions_dir

        self._pattern_cache: dict[str, list[dict[str, Any]]] = {}

    async def analyze_sessions(
        self,
        min_frequency: int = 2,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Analyze session notes and identify reusable skill patterns.

        Args:
            min_frequency: Minimum pattern frequency to suggest a skill
            limit: Maximum number of suggestions to return

        Returns:
            List of skill suggestions with metadata
        """
        # Step 1: Collect all session content
        sessions = self._collect_sessions()
        if not sessions:
            logger.info("no_sessions_found", path=str(self.sessions_dir))
            return []

        # Step 2: Extract tool patterns
        patterns = self._extract_tool_patterns(sessions)

        # Step 3: Build suggestions from frequent patterns
        suggestions = []
        for pattern, count in patterns.items():
            if count >= min_frequency:
                suggestion = self._build_suggestion(pattern, count, sessions)
                if suggestion:
                    suggestions.append(suggestion)

        # Sort by frequency
        suggestions.sort(key=lambda x: x.get("frequency", 0), reverse=True)

        logger.info(
            "patterns_analyzed",
            sessions=len(sessions),
            patterns_found=len(patterns),
            suggestions=len(suggestions[:limit]),
        )

        return suggestions[:limit]

    def _collect_sessions(self) -> list[dict[str, str]]:
        """Collect all session notes."""
        sessions = []

        if not self.sessions_dir.exists():
            return sessions

        for md_file in self.sessions_dir.glob("*.md"):
            try:
                content = md_file.read_text()
                sessions.append(
                    {
                        "path": str(md_file),
                        "name": md_file.stem,
                        "content": content,
                    }
                )
            except Exception as e:
                logger.warning("session_read_failed", path=str(md_file), error=str(e))

        return sessions

    def _extract_tool_patterns(
        self,
        sessions: list[dict[str, str]],
    ) -> dict[str, int]:
        """Extract tool usage patterns from sessions."""
        pattern_counts: dict[str, int] = Counter()

        for session in sessions:
            content = session.get("content", "")

            # Look for decision patterns
            decisions = re.findall(
                r"(?:choice|decision|selected|used)\s*[:\s]+([^\n]+)",
                content,
                re.IGNORECASE,
            )

            for decision in decisions:
                # Extract tool names from decisions
                for pattern, name in TOOL_PATTERNS:
                    if re.search(pattern, decision, re.IGNORECASE):
                        pattern_counts[name] += 1

            # Look for repeated action sequences
            file_ops = re.findall(r"(?:read|write|modify|edit)\s+([^\n,]+)", content)
            if len(file_ops) >= 3:
                pattern_counts["multi_file_operation"] += 1

        return dict(pattern_counts)

    def _build_suggestion(
        self,
        pattern: str,
        frequency: int,
        sessions: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        """Build a skill suggestion from a pattern."""
        suggestion_templates = {
            "file_operations": {
                "name": "file-utility",
                "description": "Common file read/write operations",
                "commands": ["read_file", "write_file", "list_files"],
            },
            "search_operations": {
                "name": "search-utility",
                "description": "Unified search across files and content",
                "commands": ["search_text", "search_files", "grep"],
            },
            "code_analysis": {
                "name": "code-analyzer",
                "description": "Code understanding and analysis",
                "commands": ["analyze_code", "find_symbol", "get_dependencies"],
            },
            "testing": {
                "name": "test-utility",
                "description": "Testing utilities and helpers",
                "commands": ["run_tests", "check_coverage", "generate_tests"],
            },
            "version_control": {
                "name": "git-utility",
                "description": "Common Git operations",
                "commands": ["commit", "push", "pull", "status"],
            },
            "memory_operations": {
                "name": "memory-utility",
                "description": "Memory and knowledge operations",
                "commands": ["save_note", "search_notes", "get_context"],
            },
            "multi_file_operation": {
                "name": "batch-file-operator",
                "description": "Batch file operations across multiple files",
                "commands": ["batch_read", "batch_write", "transform_files"],
            },
        }

        template = suggestion_templates.get(pattern)
        if not template:
            return None

        # Check if skill already exists
        existing_skills = self._get_existing_skill_names()
        if template["name"] in existing_skills:
            logger.debug("skill_already_exists", name=template["name"])
            return None

        return {
            "name": template["name"],
            "description": template["description"],
            "pattern": pattern,
            "frequency": frequency,
            "commands": template["commands"],
            "source_sessions": len(sessions),
        }

    def _get_existing_skill_names(self) -> set[str]:
        """Get set of existing skill names."""
        skills_dir = SKILLS_DIR()
        if not skills_dir.exists():
            return set()

        return {p.name for p in skills_dir.iterdir() if p.is_dir()}

    async def harvest_and_create(
        self,
        skill_name: str,
        description: str,
        commands: list[str],
    ) -> dict[str, Any]:
        """
        Harvest a pattern and create a new skill.

        Args:
            skill_name: Name of the new skill
            description: Description of the skill
            commands: List of command names to generate

        Returns:
            Dict with creation result
        """
        from agent.core.skill_generator import SkillGenerator

        # Create the skill using template
        generator = SkillGenerator()
        skills_dir = SKILLS_DIR()

        try:
            skill_path = generator.generate(
                skill_name=skill_name,
                description=description,
                output_dir=skills_dir,
                author="harvester",
                keywords=[skill_name],
            )
        except Exception as e:
            logger.error("skill_creation_failed", error=str(e))
            return {"success": False, "skill_name": skill_name, "error": str(e)}

        # Generate basic command implementations
        scripts_init = skill_path / "scripts" / "__init__.py"
        init_content = scripts_init.read_text() if scripts_init.exists() else ""

        for cmd in commands:
            cmd_func = self._generate_command_stub(cmd)
            init_content += cmd_func

        scripts_init.write_text(init_content)

        logger.info(
            "skill_harvested",
            skill_name=skill_name,
            path=str(skill_path),
            commands=len(commands),
        )

        return {
            "success": True,
            "skill_name": skill_name,
            "description": description,
            "commands": commands,
            "path": str(skill_path),
        }

    def _generate_command_stub(self, command_name: str) -> str:
        """Generate a stub command implementation."""
        func_name = command_name.replace("-", "_")

        return f'''

def {func_name}(**kwargs) -> dict[str, Any]:
    """
    {command_name.replace("-", " ").title()} command.

    Args:
        **kwargs: Command arguments
    """
    # TODO: Implement based on harvested pattern
    return {{
        "success": True,
        "data": {{}},
        "error": "",
    }}
'''


async def harvest_skill_patterns(
    min_frequency: int = 2,
    limit: int = 5,
    auto_create: bool = False,
) -> list[dict[str, Any]]:
    """
    Convenience function to harvest skill patterns from sessions.

    Args:
        min_frequency: Minimum pattern frequency
        limit: Maximum suggestions
        auto_create: Whether to auto-create suggested skills

    Returns:
        List of skill suggestions or created skills
    """
    harvester = SkillHarvester()
    suggestions = await harvester.analyze_sessions(min_frequency, limit)

    if auto_create:
        created = []
        for suggestion in suggestions:
            result = await harvester.harvest_and_create(
                skill_name=suggestion["name"],
                description=suggestion["description"],
                commands=suggestion.get("commands", []),
            )
            if result.get("success"):
                created.append(result)
        return created

    return suggestions


__all__ = [
    "SkillHarvester",
    "harvest_skill_patterns",
]
