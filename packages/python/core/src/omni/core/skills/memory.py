"""
omni.core.skills.memory - Skill Memory (Rust-Native)

Context Hydration Engine - The Brain's Librarian.

Responsibilities:
1. Loading Skill Metadata (from LanceDB - Single Source of Truth)
2. Hydrating Context (Merging SKILL.md + required_refs content)
3. Providing caching and safe file access.

Architecture:
    LanceDB ──────▶ SkillIndexLoader ──▶ Metadata O(1) Lookup
                            │
                            ▼
                    ContextAssembler (Rust) ──▶ Full LLM Context
                            │
                            ▼
                      FileCache (caching)

Usage:
    from omni.core.skills import get_skill_memory

    memory = get_skill_memory()
    context = memory.hydrate_skill_context("researcher")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omni_core_rs import ContextAssembler
from omni.foundation.config.logging import get_logger
from omni.foundation.config.skills import SKILLS_DIR

from .file_cache import FileCache
from .index_loader import SkillIndexLoader
from .ref_parser import RefParser

logger = get_logger("omni.core.skills.memory")


class SkillMemory:
    """The Brain's Librarian - unified interface for skill context hydration.

    Single source of truth: LanceDB (Rust/LanceDB)
    Uses Rust ContextAssembler for parallel I/O + templating + token counting.
    """

    def __init__(
        self,
        index_loader: SkillIndexLoader | None = None,
        file_cache: FileCache | None = None,
    ) -> None:
        self._index_loader = index_loader or SkillIndexLoader()
        self._file_cache = file_cache or FileCache()
        self._assembler = ContextAssembler()

    # =====================================================================
    # Metadata Operations (O(1) Lookup)
    # =====================================================================

    def get_skill_metadata(self, skill_name: str) -> dict[str, Any] | None:
        """O(1) lookup for skill metadata from Rust index."""
        return self._index_loader.get_metadata(skill_name)

    def list_skills(self) -> list[str]:
        """Get all registered skill names."""
        return self._index_loader.list_skills()

    def reload(self) -> None:
        """Force reload index (useful for dev hot-reload)."""
        self._index_loader.reload()
        self._file_cache.clear()
        logger.info("SkillMemory: Index and cache reloaded")

    # =====================================================================
    # Context Hydration (The Magic Method)
    # =====================================================================

    def hydrate_skill_context(self, skill_name: str) -> str:
        """★★★ The Magic Method ★★★

        Assembles full LLM context for a skill:
        - SKILL.md content
        - All required_refs files merged

        Uses Rust ContextAssembler for parallel I/O + templating + token counting.

        Args:
            skill_name: Name of the skill

        Returns:
            Full context string for LLM system prompt
        """
        metadata = self._index_loader.get_metadata(skill_name)
        if not metadata:
            return f"Error: Skill '{skill_name}' not found in registry"

        # Get skill path from metadata
        skill_path_str = metadata.get("path")
        skill_path = SKILLS_DIR(skill_name) if not skill_path_str else Path(skill_path_str)

        # Get paths
        skill_md_path = str(skill_path / "SKILL.md")

        # Build ref paths from required_refs
        ref_paths = []
        for ref in metadata.get("required_refs", []):
            ref_paths.append(str(skill_path / ref))

        logger.debug(
            f"SkillMemory: Hydrating context for '{skill_name}'",
            main_file=skill_md_path,
            ref_files=ref_paths,
        )

        # Use Rust ContextAssembler for parallel I/O + templating
        variables = json.dumps({"skill": skill_name})
        content, token_count, missing = self._assembler.assemble(
            skill_md_path, ref_paths, variables
        )

        logger.debug(
            f"SkillMemory: Context hydrated for '{skill_name}'",
            tokens=token_count,
            chars=len(content),
            missing_refs=[str(m) for m in missing] if missing else [],
        )

        if missing:
            logger.warning(f"SkillMemory: Missing refs for {skill_name}: {missing}")

        return content

    def hydrate_skill_context_raw(
        self,
        skill_name: str,
        skill_md_content: str,
    ) -> str:
        """Hydrate context with raw SKILL.md content (for dev mode).

        Used when data is not yet in LanceDB.
        """
        metadata = self._index_loader.get_metadata(skill_name) or {}

        # Create a temporary ref parser
        ref_parser = RefParser()
        refs = ref_parser.parse(metadata, skill_md_content)

        if not refs:
            return skill_md_content

        # Load references
        skill_path = SKILLS_DIR(skill_name)
        ref_contents = []
        for ref in refs:
            ref = ref_parser.normalize_ref(ref)
            ref_path = skill_path / ref
            content = self._file_cache.read(ref_path)
            ref_contents.append((ref, content))

        # Assemble
        parts = [f"# Active Protocol: {skill_name}", skill_md_content]
        if ref_contents:
            parts.append("\n\n# Required Knowledge Context")
            for ref_path, content in ref_contents:
                parts.append(f"\n### Reference: {ref_path}\n")
                parts.append(content)

        return "\n".join(parts)

    # =====================================================================
    # Cache Management
    # =====================================================================

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._file_cache.clear()
        logger.debug("SkillMemory: Cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._file_cache.stats()


# =====================================================================
# Singleton Pattern
# =====================================================================

_memory_instance: SkillMemory | None = None


def get_skill_memory() -> SkillMemory:
    """Get the singleton SkillMemory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = SkillMemory()
    return _memory_instance


__all__ = ["SkillMemory", "get_skill_memory"]
