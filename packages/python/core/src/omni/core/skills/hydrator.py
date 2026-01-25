"""
hydrator.py - Context Hydrator

Assembles full LLM context from SKILL.md + required_refs.

The Magic Method:
    hydrate_skill_context(skill_name) -> str (full context for LLM)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from omni.foundation.config.logging import get_logger
from omni.foundation.runtime.gitops import get_project_root

from .file_cache import FileCache
from .ref_parser import RefParser

logger = get_logger("omni.core.skills.hydrator")


class ContextHydrator:
    """Assembles complete LLM context from skill + references."""

    def __init__(
        self,
        file_cache: FileCache | None = None,
        ref_parser: RefParser | None = None,
    ) -> None:
        self._file_cache = file_cache or FileCache()
        self._ref_parser = ref_parser or RefParser()

    def hydrate(
        self,
        skill_name: str,
        metadata: dict[str, Any],
        skill_md_path: Path,
    ) -> str:
        """Assemble full context for a skill.

        Args:
            skill_name: Name of the skill
            metadata: Skill metadata from Rust index
            skill_md_path: Path to SKILL.md

        Returns:
            Full context string for LLM
        """
        # 1. Load main skill protocol
        main_content = self._file_cache.read(skill_md_path)
        if not main_content or main_content.startswith("["):
            return f"Error: Skill '{skill_name}' not found"

        # 2. Extract references
        refs = self._ref_parser.parse(metadata, main_content)
        if not refs:
            return main_content

        # 3. Resolve and load references
        ref_contents = self._load_references(skill_md_path.parent, refs)

        # 4. Assemble final context
        return self._assemble_context(skill_name, main_content, ref_contents)

    def _load_references(
        self,
        skill_root: Path,
        refs: list[str],
    ) -> list[tuple[str, str]]:
        """Load referenced files.

        Args:
            skill_root: Base path for relative references
            refs: List of relative file paths

        Returns:
            List of (ref_path, content) tuples
        """
        results = []
        project_root = get_project_root()

        for ref in refs:
            # Normalize reference
            ref = self._ref_parser.normalize_ref(ref)

            # Try skill-relative path first
            ref_path = skill_root / ref

            # Try project-relative path (for assets/ references)
            if not ref_path.exists():
                ref_path = project_root / ref

            content = self._file_cache.read(ref_path)
            results.append((ref, content))

        return results

    def _assemble_context(
        self,
        skill_name: str,
        main_content: str,
        ref_contents: list[tuple[str, str]],
    ) -> str:
        """Build final context string.

        Args:
            skill_name: Name of the skill
            main_content: SKILL.md content
            ref_contents: List of (ref_path, content) tuples

        Returns:
            Assembled context string
        """
        parts: list[str] = []

        # Header
        parts.append(f"# Active Protocol: {skill_name}")
        parts.append(main_content)

        # References section
        if ref_contents:
            parts.append("\n\n# Required Knowledge Context")
            for ref_path, content in ref_contents:
                parts.append(f"\n### Reference: {ref_path}\n")
                parts.append(content)

        return "\n".join(parts)


__all__ = ["ContextHydrator"]
