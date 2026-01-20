# parser.py - Rust-based SKILL.md Parser
#
# Phase 4: Data-Driven Implementation
# Uses Rust scanner for high-performance parsing.
#
# This module provides a unified interface for parsing SKILL.md files.
# It uses the Rust omni_core_rs bindings which use skills-scanner crate.

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from omni_core_rs import scan_skill, scan_skill_from_content, PySkillMetadata

    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
    PySkillMetadata = None  # type: ignore


def parse_skill_md(path: Path) -> Optional[Dict[str, Any]]:
    """Parse a SKILL.md file using Rust scanner.

    Args:
        path: Path to the skill directory (e.g., "assets/skills/git")

    Returns:
        Dictionary with parsed metadata, or None if not found.

    Raises:
        RuntimeError: If Rust bindings are not available.
    """
    if not _RUST_AVAILABLE:
        raise RuntimeError(
            "Rust bindings (omni_core_rs) not available. "
            "Please ensure the Rust extension is installed."
        )

    metadata = scan_skill(str(path))
    if metadata is None:
        return None

    return _py_to_dict(metadata)


def parse_skill_md_from_content(content: str, skill_name: str = "unknown") -> Dict[str, Any]:
    """Parse SKILL.md content directly using Rust scanner.

    Useful for testing or processing content from other sources.

    Args:
        content: Raw SKILL.md content including YAML frontmatter.
        skill_name: Name of the skill (used if not in frontmatter).

    Returns:
        Dictionary with parsed metadata.
    """
    if not _RUST_AVAILABLE:
        raise RuntimeError(
            "Rust bindings (omni_core_rs) not available. "
            "Please ensure the Rust extension is installed."
        )

    metadata = scan_skill_from_content(content, skill_name)
    return _py_to_dict(metadata)


def _py_to_dict(metadata: PySkillMetadata) -> Dict[str, Any]:
    """Convert PySkillMetadata to dictionary.

    Args:
        metadata: PySkillMetadata object from Rust.

    Returns:
        Dictionary representation with both 'name' and 'skill_name' for compatibility.
    """
    return {
        "name": metadata.skill_name,  # For backward compatibility
        "skill_name": metadata.skill_name,
        "version": metadata.version,
        "description": metadata.description,
        "routing_keywords": metadata.routing_keywords,
        "authors": metadata.authors,
        "intents": metadata.intents,
        "require_refs": metadata.require_refs,
        "repository": metadata.repository,
    }


def is_rust_available() -> bool:
    """Check if Rust bindings are available.

    Returns:
        True if Rust scanner is available.
    """
    return _RUST_AVAILABLE


__all__ = [
    "parse_skill_md",
    "parse_skill_md_from_content",
    "is_rust_available",
]
