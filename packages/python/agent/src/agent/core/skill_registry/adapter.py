"""
agent/core/registry/adapter.py
 Unified Manifest Adapter - SKILL.md Enhancement

Extends the existing SkillManifestLoader with:
- Smart default injection for Omni-specific fields
- Enhanced error diagnostics
- Format detection utilities

ODF-EP v6.0 Compliance:
- Pydantic Shield for strict type validation
- Context-Aware Observability with structlog
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...skills.core.skill_metadata import (
    ExecutionMode,
    RoutingStrategy,
    SkillMetadata,
)
from ...skills.core.skill_metadata_loader import SkillMetadataLoader

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
# Default Keywords Registry (for smart injection)
# =============================================================================

# Common routing keywords for known skill types
_SKILL_TYPE_KEYWORDS: dict[str, list[str]] = {
    "git": ["version_control", "repo", "commit", "push", "branch", "merge"],
    "file": ["read", "write", "edit", "directory", "filesystem", "path"],
    "search": ["find", "query", "web", "internet", "browse"],
    "shell": ["bash", "command", "terminal", "exec", "run"],
    "code": ["programming", "code", "file", "edit", "refactor"],
    "test": ["test", "unit", "coverage", "assert", "verify"],
    "review": ["review", "audit", "check", "analyze", "critique"],
    "debug": ["debug", "troubleshoot", "error", "log", "trace"],
    "web": ["http", "request", "api", "url", "fetch"],
    "data": ["data", "transform", "csv", "json", "parse"],
}


def _get_default_keywords(skill_name: str) -> list[str]:
    """Get default routing keywords for a skill based on its name."""
    keywords = [skill_name]

    # Check for known skill types
    skill_lower = skill_name.lower()
    for key, defaults in _SKILL_TYPE_KEYWORDS.items():
        if key in skill_lower:
            keywords.extend(defaults)
            break

    return list(set(keywords))  # Remove duplicates


# =============================================================================
# Unified Manifest Adapter
# =============================================================================


class UnifiedManifestAdapter:
    """
    Enhanced adapter for loading SKILL.md manifests.

    Extends SkillManifestLoader with:
    - Smart default injection for Omni routing
    - Enhanced error diagnostics
    - Seamless integration with existing loader

    ODF-EP v6.0: Pydantic Shield & Context-Aware Observability
    """

    __slots__ = ("_loader",)

    def __init__(self) -> None:
        """Initialize the unified adapter."""
        self._loader = SkillMetadataLoader()

    # =========================================================================
    # File Detection
    # =========================================================================

    def skill_file_exists(self, skill_path: Path) -> bool:
        """Check if SKILL.md exists in skill directory."""
        return (skill_path / "SKILL.md").exists()

    # =========================================================================
    # Metadata Loading (Enhanced)
    # =========================================================================

    async def load_metadata(self, skill_path: Path) -> SkillMetadata | None:
        """
        Load skill metadata from SKILL.md with enhanced defaults.

        Args:
            skill_path: Path to skill directory

        Returns:
            SkillMetadata instance or None if loading failed
        """
        log = _get_logger().bind(skill=skill_path.name, source="SKILL.md")

        # Use existing SkillManifestLoader (async)
        metadata = await self._loader.load_metadata(skill_path)

        if metadata is None:
            log.error("No valid SKILL.md found")
            return None

        # Inject Omni-specific defaults
        metadata = self._inject_omni_defaults(metadata, skill_path.name)
        # No debug log for successful load - only errors matter

        return metadata

    async def load_definition(self, skill_path: Path) -> tuple[SkillMetadata, str] | None:
        """
        Load complete skill definition (metadata + system prompt).

        Args:
            skill_path: Path to skill directory

        Returns:
            Tuple of (SkillMetadata, system_prompt) or None if loading failed
        """
        definition = await self._loader.load_definition(skill_path)

        if definition is None:
            return None

        metadata = self._inject_omni_defaults(definition.metadata, skill_path.name)
        return (metadata, definition.system_prompt)

    # =========================================================================
    # Smart Default Injection
    # =========================================================================

    def _inject_omni_defaults(self, metadata: SkillMetadata, skill_name: str) -> SkillMetadata:
        """
        Inject Omni-specific defaults into metadata.

        Preserves Omni's advanced routing capabilities:
        - Ensures routing_keywords are never empty
        - Sets sensible defaults for execution_mode
        - Enables semantic routing for all skills

        Note: SkillMetadata uses @dataclass(slots=True), so we use
        dataclasses.asdict() or field access instead of __dict__.
        """
        needs_injection = False
        new_routing_keywords = (
            list(metadata.routing_keywords) if metadata.routing_keywords else None
        )
        new_execution_mode = metadata.execution_mode
        new_routing_strategy = metadata.routing_strategy

        # Inject routing_keywords if not specified
        if not metadata.routing_keywords:
            new_routing_keywords = _get_default_keywords(skill_name)
            needs_injection = True
            _get_logger().debug(
                "Injected default routing keywords",
                skill=skill_name,
                keywords=new_routing_keywords,
            )

        # Ensure execution_mode has a value (handle empty string)
        if not metadata.execution_mode or metadata.execution_mode == "":
            new_execution_mode = ExecutionMode.LIBRARY
            needs_injection = True

        # Ensure routing_strategy has a value (handle empty string)
        if not metadata.routing_strategy or metadata.routing_strategy == "":
            new_routing_strategy = RoutingStrategy.KEYWORD
            needs_injection = True

        if not needs_injection:
            return metadata

        # Create new SkillMetadata with injected values
        return SkillMetadata(
            name=metadata.name,
            version=metadata.version,
            description=metadata.description,
            authors=list(metadata.authors),
            execution_mode=new_execution_mode,
            routing_strategy=new_routing_strategy,
            routing_keywords=new_routing_keywords or [],
            intents=list(metadata.intents),
            dependencies=dict(metadata.dependencies),
            permissions=dict(metadata.permissions),
        )

    # =========================================================================
    # Diagnostic Utilities
    # =========================================================================

    def validate_skill(self, skill_path: Path) -> dict[str, Any]:
        """
        Validate a skill and return diagnostic information.

        Args:
            skill_path: Path to skill directory

        Returns:
            Dict with validation results
        """
        result: dict[str, Any] = {
            "path": str(skill_path),
            "valid": False,
            "errors": [],
            "warnings": [],
            "metadata": None,
        }

        # Check SKILL.md exists
        if not self.skill_file_exists(skill_path):
            result["errors"].append("SKILL.md not found")
            return result

        # Load metadata
        metadata = self.load_metadata(skill_path)
        if metadata is None:
            result["errors"].append("Failed to parse SKILL.md")
            return result

        result["metadata"] = metadata.to_dict()

        # Check for common issues
        if not metadata.routing_keywords:
            result["warnings"].append("No routing keywords defined")

        if not metadata.description:
            result["warnings"].append("No description provided")

        if not metadata.execution_mode:
            result["warnings"].append("No execution mode specified")

        result["valid"] = len(result["errors"]) == 0
        return result


# =============================================================================
# Singleton Instance
# =============================================================================


_adapter: UnifiedManifestAdapter | None = None


def get_unified_adapter() -> UnifiedManifestAdapter:
    """Get the global unified adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = UnifiedManifestAdapter()
    return _adapter


# =============================================================================
# Export
# =============================================================================


__all__ = [
    "UnifiedManifestAdapter",
    "get_unified_adapter",
    "_get_default_keywords",
]
