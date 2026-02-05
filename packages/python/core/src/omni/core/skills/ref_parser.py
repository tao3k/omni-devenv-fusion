"""
ref_parser.py - Reference Parser

Parses required_refs from Rust-generated metadata only.
Rust scanner is the Single Source of Truth for skill metadata.

No Python fallback - if Rust is unavailable, references cannot be resolved.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RefParser:
    """Parse required_refs from Rust-generated metadata."""

    def parse(
        self,
        metadata: dict[str, Any],
        skill_md_content: str | None = None,  # noqa: ARG002 - Kept for API compatibility
    ) -> list[str]:
        """Extract reference list from Rust metadata.

        Args:
            metadata: Skill metadata from Rust index
            skill_md_content: Ignored (Rust is SSOT)

        Returns:
            List of relative file paths to reference, or empty list if unavailable
        """
        # Rust metadata is the only source of truth
        refs = self._extract_from_metadata(metadata)

        if refs is None:
            # Check if metadata is essentially empty (Rust unavailable or failed)
            if not metadata or all(v is None for v in metadata.values() if v != "name"):
                logger.warning(
                    "Rust metadata unavailable - required_refs cannot be resolved. "
                    "Ensure Rust scanner is properly initialized."
                )

        return refs if refs else []

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

    def normalize_ref(self, ref: str) -> str:
        """Normalize reference path for consistency."""
        # Remove leading ./ if present
        ref = ref.removeprefix("./")
        # Ensure forward slashes
        ref = ref.replace("\\", "/")
        return ref


__all__ = ["RefParser"]
