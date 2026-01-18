"""
agent/core/registry/core.py
 SkillRegistry Core

Core registry class - handles initialization, discovery, and state management.
Pure MCP Server compatible.
"""

from __future__ import annotations

import json
import logging
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

from common.gitops import get_project_root
from common.config.settings import get_setting

# Pre-load agent.skills.core for pytest-xdist compatibility
# This ensures the module is available in all test workers
import agent.skills.core  # noqa: F401

if TYPE_CHECKING:
    from mcp.server import Server

# Lazy logger - defer structlog.get_logger() to avoid ~100ms import cost
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily to avoid import-time overhead."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


# Marker attribute for @skill_command decorated functions
_SKILL_COMMAND_MARKER = "_is_skill_command"


class SkillRegistry:
    """
    Central skill registry.

    Responsibilities:
    - Skill discovery and listing
    - Manifest parsing
    - Module caching
    - State management
    """

    __slots__ = (
        "project_root",
        "skills_dir",
        "loaded_skills",
        "module_cache",
        "skill_tools",
        "_initialized",
    )

    _instance: "SkillRegistry | None" = None

    def __new__(cls) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        from common.skills_path import SKILLS_DIR

        self.project_root = get_project_root()
        self.skills_dir = SKILLS_DIR()
        self.loaded_skills: dict[str, Any] = {}
        self.module_cache: dict[str, types.ModuleType] = {}
        self.skill_tools: dict[str, list[str]] = {}
        self._initialized = True

        self.skills_dir.mkdir(parents=True, exist_ok=True)
        _get_logger().debug("SkillRegistry initialized", path=str(self.skills_dir))

    # =========================================================================
    # Discovery
    # =========================================================================

    def list_available_skills(self) -> list[str]:
        """Scan the skills directory for valid skills."""
        if not self.skills_dir.exists():
            return []

        skills = [
            item.name
            for item in self.skills_dir.iterdir()
            if item.is_dir() and (item / "SKILL.md").exists()
        ]
        return sorted(skills)

    def list_loaded_skills(self) -> list[str]:
        """List currently loaded skills."""
        return list(self.loaded_skills.keys())

    def is_loaded(self, skill_name: str) -> bool:
        """Check if a skill is loaded."""
        return skill_name in self.loaded_skills

    # =========================================================================
    # Manifest
    # =========================================================================

    def get_skill_manifest(self, skill_name: str) -> "SkillManifest | None":
        """Read and parse a skill's manifest from SKILL.md."""
        from agent.core.schema import SkillManifest, SkillDependencies

        # Robust import for pytest-xdist compatibility
        # Sometimes the module is not found in sys.modules due to test worker isolation
        try:
            from agent.skills.core.skill_metadata_loader import get_skill_metadata_loader
        except ModuleNotFoundError:
            # Force reload the module
            import importlib
            import sys

            # Ensure parent package exists
            if "agent.skills" not in sys.modules:
                import agent.skills
            if "agent.skills.core" not in sys.modules:
                import agent.skills.core
            # Now import the function
            skill_metadata_loader = importlib.import_module(
                "agent.skills.core.skill_metadata_loader"
            )
            get_skill_metadata_loader = skill_metadata_loader.get_skill_metadata_loader

        skill_path = self.skills_dir / skill_name
        if not skill_path.exists():
            return None

        import asyncio
        import concurrent.futures

        loader = get_skill_metadata_loader()

        # Run in thread to avoid event loop conflicts with async tests
        def _load():
            return asyncio.run(loader.load_metadata(skill_path))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            metadata = executor.submit(_load).result()

        if metadata is None:
            return None

        # Convert SkillMetadata to SkillManifest
        return SkillManifest(
            name=metadata.name,
            version=metadata.version,
            description=metadata.description,
            author=metadata.authors[0] if metadata.authors else "unknown",
            routing_keywords=metadata.routing_keywords,
            intents=metadata.intents,
            dependencies=SkillDependencies(python=metadata.dependencies.get("python", {})),
            tools_module=f"agent.skills.{skill_name}.tools",
        )

    # =========================================================================
    # Module Management
    # =========================================================================

    def register_module(self, skill_name: str, module: types.ModuleType) -> None:
        """Register a loaded module."""
        self.module_cache[skill_name] = module

        # Extract tool names
        tools = []
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if callable(obj) and hasattr(obj, _SKILL_COMMAND_MARKER):
                tools.append(name)
        self.skill_tools[skill_name] = tools

    def get_module(self, skill_name: str) -> types.ModuleType | None:
        """Get a loaded module."""
        return self.module_cache.get(skill_name)

    def unregister_module(self, skill_name: str) -> None:
        """Unregister a module."""
        self.module_cache.pop(skill_name, None)
        self.skill_tools.pop(skill_name, None)
        self.loaded_skills.pop(skill_name, None)

    def get_skill_tools(self, skill_name: str) -> dict[str, Any]:
        """Get all @skill_command decorated tools from a skill."""
        module = self.get_module(skill_name)
        if not module:
            return {}

        tools = {}
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if callable(obj) and hasattr(obj, _SKILL_COMMAND_MARKER):
                tools[name] = obj

        return tools

    # =========================================================================
    # Preloading
    # =========================================================================

    def get_preload_skills(self) -> list[str]:
        """Get list of skills to preload from settings."""
        return get_setting("skills.preload", [])

    def preload_all(self, mcp: "Server") -> tuple[int, list[str]]:
        """Load all preload skills from settings."""
        from agent.core.skill_registry.loader import SkillLoader

        preload_skills = self.get_preload_skills()
        loader = SkillLoader(self)
        loaded = []
        failed = []

        for skill in preload_skills:
            if skill in self.loaded_skills:
                continue
            success, msg = loader.load_skill(skill, mcp)
            if success:
                loaded.append(skill)
            else:
                failed.append(skill)
                _get_logger().warning(f"Failed to preload skill ({skill}): {msg}")

        return len(loaded), loaded

    def load_skill(self, skill_name: str, mcp: "Server | None" = None) -> tuple[bool, str]:
        """
        Load a skill (convenience method - delegates to SkillLoader).

        This method exists for backward compatibility.
        New code should use SkillLoader directly.
        """
        from agent.core.skill_registry.loader import SkillLoader

        loader = SkillLoader(self)
        return loader.load_skill(skill_name, mcp)

    # =========================================================================
    # Context
    # =========================================================================

    def get_skill_context(self, skill_name: str, use_diff: bool = False) -> str:
        """Get skill definition (SKILL.md) for a skill."""
        from agent.core.skill_registry.context import ContextBuilder

        manifest = self.loaded_skills.get(skill_name)
        if manifest is None:
            manifest_model = self.get_skill_manifest(skill_name)
            if manifest_model is None:
                return ""
            manifest = manifest_model.model_dump()

        return ContextBuilder(self, skill_name, manifest).build(use_diff=use_diff)

    def get_combined_context(self) -> str:
        """Aggregate prompts.md from all loaded skills."""
        from agent.core.skill_registry.context import ContextBuilder

        if not self.loaded_skills:
            return "# No skills loaded"

        combined = ["# 🧠 Active Skill Policies & Routing Rules"]
        combined.append("The following skills are loaded and active.\n")

        for skill_name in sorted(self.loaded_skills.keys()):
            manifest = self.loaded_skills[skill_name]
            prompts_file = (
                manifest.get("prompts_file")
                if isinstance(manifest, dict)
                else getattr(manifest, "prompts_file", None)
            )

            if prompts_file:
                prompts_path = self.skills_dir / skill_name / prompts_file
                if prompts_path.exists():
                    combined.append(f"\n## 📦 Skill: {skill_name.upper()}")
                    combined.append(prompts_path.read_text(encoding="utf-8"))
                    combined.append("\n---\n")

        return "\n".join(combined)

    # =========================================================================
    # Remote Installation
    # =========================================================================

    def install_remote_skill(
        self,
        skill_name: str,
        repo_url: str,
        version: str = "main",
        install_deps: bool = True,
    ) -> tuple[bool, str]:
        """Install a skill from a remote Git repository."""
        from agent.core.skill_registry.installer import RemoteInstaller

        target_dir = self.skills_dir / skill_name
        if target_dir.exists():
            return False, f"Skill '{skill_name}' already exists locally."

        installer = RemoteInstaller(self)

        try:
            success, msg = installer.install(target_dir, repo_url, version)

            if success and install_deps:
                installer.install_python_deps(target_dir)

            _get_logger().info("Installed remote skill", skill=skill_name, url=repo_url)
            return success, msg

        except Exception as e:
            _get_logger().error("Failed to install remote skill", skill=skill_name, error=str(e))
            return False, f"Installation failed: {e}"

    def update_remote_skill(
        self,
        skill_name: str,
        strategy: str = "stash",
    ) -> tuple[bool, str]:
        """Update an already installed skill."""
        from agent.core.skill_registry.installer import RemoteInstaller

        target_dir = self.skills_dir / skill_name
        if not target_dir.exists():
            return False, f"Skill '{skill_name}' not found locally."

        installer = RemoteInstaller(self)

        try:
            success, msg = installer.update(target_dir, strategy)
            _get_logger().info("Updated skill", skill=skill_name)
            return success, msg

        except Exception as e:
            _get_logger().error("Failed to update skill", skill=skill_name, error=str(e))
            return False, f"Update failed: {e}"

    # =========================================================================
    # Version Resolution
    # =========================================================================

    def _resolve_skill_version(self, skill_path: Path) -> str:
        """Resolve skill version (for backward compatibility)."""
        from agent.core.skill_registry.resolver import VersionResolver

        return VersionResolver.resolve_version(skill_path)

    def get_skill_revision(self, skill_name: str) -> str | None:
        """Get the current revision of an installed skill."""
        from agent.core.skill_registry.resolver import VersionResolver

        target_dir = self.skills_dir / skill_name
        if not target_dir.exists():
            return None

        return VersionResolver.resolve_revision(target_dir)

    def get_skill_version(self, skill_name: str) -> str:
        """Get the version string for a skill."""
        from agent.core.skill_registry.resolver import VersionResolver

        target_dir = self.skills_dir / skill_name
        return VersionResolver.resolve_version(target_dir)

    def get_skill_info(self, skill_name: str) -> dict[str, Any]:
        """Get detailed information about an installed skill."""
        from agent.core.skill_registry.resolver import VersionResolver

        target_dir = self.skills_dir / skill_name
        if not target_dir.exists():
            return {"error": f"Skill '{skill_name}' not found"}

        version = VersionResolver.resolve_version(target_dir)
        revision = VersionResolver.resolve_revision(target_dir)
        is_dirty = VersionResolver.is_dirty(target_dir)

        info = {
            "name": skill_name,
            "version": version,
            "revision": revision,
            "path": str(target_dir),
            "is_dirty": is_dirty,
        }

        # Read SKILL.md frontmatter (YAML metadata)
        skill_md_path = target_dir / "SKILL.md"
        if skill_md_path.exists():
            try:
                import frontmatter

                with open(skill_md_path) as f:
                    post = frontmatter.load(f)
                manifest = post.metadata or {}
                # Extract frontmatter fields
                info.update(
                    {
                        "manifest": manifest,
                        "description": manifest.get("description", ""),
                        "routing_keywords": manifest.get("routing_keywords", []),
                        "intents": manifest.get("intents", []),
                        "authors": manifest.get("authors", []),
                    }
                )
            except Exception as e:
                info["manifest_error"] = str(e)

        # Read lockfile
        lockfile_path = target_dir / ".omni-lock.json"
        if lockfile_path.exists():
            try:
                info["lockfile"] = json.loads(lockfile_path.read_text())
            except Exception as e:
                info["lockfile_error"] = str(e)

        return info


# =============================================================================
# Global Singleton
# =============================================================================

_registry: "SkillRegistry | None" = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry instance."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
