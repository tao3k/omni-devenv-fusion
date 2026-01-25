"""
ref_parser.py - Reference Parser

Parses required_refs from:
1. Rust-generated metadata (priority)
2. SKILL.md YAML frontmatter (fallback)

Supports both camelCase and snake_case key formats.
"""

from __future__ import annotations

import re
from typing import Any

import yaml


class RefParser:
    """Parse required_refs from metadata or SKILL.md."""

    def parse(
        self,
        metadata: dict[str, Any],
        skill_md_content: str | None = None,
    ) -> list[str]:
        """Extract reference list from metadata or fallback.

        Args:
            metadata: Skill metadata from Rust index
            skill_md_content: Raw SKILL.md content for fallback

        Returns:
            List of relative file paths to reference
        """
        # 1. Try Rust metadata first (priority)
        refs = self._extract_from_metadata(metadata)
        if refs:
            return refs

        # 2. Fallback to YAML frontmatter parsing
        if skill_md_content:
            refs = self._extract_from_frontmatter(skill_md_content)
            if refs:
                return refs

        return []

    def _extract_from_metadata(self, metadata: dict[str, Any]) -> list[str] | None:
        """Extract from Rust-generated metadata.

        Supports both camelCase and snake_case keys.
        """
        # Try camelCase first (Rust JSON standard)
        refs = metadata.get("requireRefs")
        if refs is not None:
            return refs if isinstance(refs, list) else None

        # Try snake_case (Python convention)
        refs = metadata.get("require_refs")
        if refs is not None:
            return refs if isinstance(refs, list) else None

        return None

    def _extract_from_frontmatter(self, content: str) -> list[str]:
        """Extract from SKILL.md YAML frontmatter.

        Falls back to regex for malformed YAML.
        """
        # Parse YAML frontmatter
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            try:
                fm = yaml.safe_load(match.group(1))
                if fm:
                    # Try both key formats
                    refs = fm.get("required_refs") or fm.get("requireRefs")
                    if refs and isinstance(refs, list):
                        return refs
            except yaml.YAMLError:
                pass

        return []

    def normalize_ref(self, ref: str) -> str:
        """Normalize reference path for consistency."""
        # Remove leading ./ if present
        ref = ref.removeprefix("./")
        # Ensure forward slashes
        ref = ref.replace("\\", "/")
        return ref


__all__ = ["RefParser"]
