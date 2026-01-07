"""
agent/core/registry/context.py
Phase 29: Context Builder

Build skill context (guide.md + prompts.md) with diff support.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agent.core.registry.core import SkillRegistry

logger = structlog.get_logger(__name__)


class ContextBuilder:
    """
    Build skill context from guide.md and prompts.md.

    Supports:
    - Full content retrieval
    - Git diff for token-efficient updates
    - Combined context from multiple skills
    """

    __slots__ = ("registry", "skill_name", "manifest", "skills_dir")

    def __init__(
        self, registry: "SkillRegistry", skill_name: str, manifest: dict[str, any]
    ) -> None:
        self.registry = registry
        self.skill_name = skill_name
        self.manifest = manifest
        self.skills_dir = registry.skills_dir

    def build(self, use_diff: bool = False) -> str:
        """Build complete context for a skill."""
        content = ""

        # Get guide content
        guide_file = self.manifest.get("guide_file", "guide.md")
        guide_path = self.skills_dir / self.skill_name / guide_file
        content += self._get_file_content(guide_path, "GUIDE", use_diff)

        # Get prompts content
        prompts_file = self.manifest.get("prompts_file")
        if prompts_file:
            prompts_path = self.skills_dir / self.skill_name / prompts_file
            content += self._get_file_content(prompts_path, "SYSTEM PROMPTS", use_diff)

        return content

    def _get_file_content(self, file_path: Path, file_label: str, use_diff: bool) -> str:
        """Get file content or git diff."""
        if not file_path.exists():
            return ""

        if use_diff:
            return self._get_diff(file_path, file_label)

        return self._get_full_content(file_path, file_label)

    def _get_full_content(self, file_path: Path, file_label: str) -> str:
        """Get full file content."""
        try:
            content = file_path.read_text(encoding="utf-8")
            return f"\n--- {self.skill_name.upper()} {file_label} ---\n{content}\n"
        except Exception as e:
            logger.warning("Failed to read file", path=str(file_path), error=str(e))
            return ""

    def _get_diff(self, file_path: Path, file_label: str) -> str:
        """Get git diff for a file."""
        try:
            result = subprocess.run(
                ["git", "diff", str(file_path)],
                cwd=str(self.registry.project_root),
                capture_output=True,
                text=True,
            )

            if result.returncode == 0 and result.stdout.strip():
                return (
                    f"\n--- {self.skill_name.upper()} {file_label} (CHANGED) ---\n{result.stdout}"
                )
            else:
                return (
                    f"\n--- {self.skill_name.upper()} {file_label} ---\n[Unchanged - not showing]\n"
                )

        except Exception:
            # Fallback to full content if git fails
            return self._get_full_content(file_path, file_label)


def get_combined_context(registry: "SkillRegistry") -> str:
    """
    Aggregate prompts.md from all loaded skills into a single context.
    """
    if not registry.loaded_skills:
        return "# No skills loaded\n\nActive skills will have their prompts.md aggregated here."

    combined = ["# 🧠 Active Skill Policies & Routing Rules"]
    combined.append(
        "The following skills are loaded and active. You MUST follow their routing logic.\n"
    )

    for skill_name in sorted(registry.loaded_skills.keys()):
        manifest = registry.loaded_skills[skill_name]
        prompts_file = (
            manifest.get("prompts_file")
            if isinstance(manifest, dict)
            else getattr(manifest, "prompts_file", None)
        )

        if prompts_file:
            prompts_path = registry.skills_dir / skill_name / prompts_file
            if prompts_path.exists():
                combined.append(f"\n## 📦 Skill: {skill_name.upper()}")
                combined.append(prompts_path.read_text(encoding="utf-8"))
                combined.append("\n---\n")

    return "\n".join(combined)
