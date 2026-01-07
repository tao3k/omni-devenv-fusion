"""
agent/core/registry/loader.py
Phase 29: Skill Loader

Module loading with spec-based loading and hot-reload support.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from agent.core.module_loader import ModuleLoader

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = structlog.get_logger(__name__)

# Marker attribute for @skill_command decorated functions
_SKILL_COMMAND_MARKER = "_is_skill_command"


class SkillLoader:
    """
    Skill loader with spec-based module loading.

    Responsibilities:
    - Load modules from file paths
    - Handle hot-reload
    - Extract @skill_command decorated functions
    """

    __slots__ = ("registry",)

    def __init__(self, registry: "SkillRegistry") -> None:
        self.registry = registry

    def load_skill(self, skill_name: str, mcp: FastMCP) -> tuple[bool, str]:
        """
        Dynamically load a skill into the MCP server.
        Supports HOT RELOAD.
        """
        # Get manifest
        manifest = self.registry.get_skill_manifest(skill_name)
        if not manifest:
            return False, f"Skill '{skill_name}' not found or invalid."

        # Convert to dict for consistent access
        if hasattr(manifest, "model_dump"):
            manifest_dict = manifest.model_dump()
        else:
            manifest_dict = manifest

        # Check if already loaded (hot reload will override)
        if skill_name in self.registry.loaded_skills:
            # Still reload for hot-reload support
            pass

        # Resolve skill dependencies
        success, msg = self._resolve_dependencies(manifest, mcp)
        if not success:
            return False, msg

        # Locate the tools file
        tools_module = manifest_dict.get("tools_module", f"agent.skills.{skill_name}.tools")

        # Handle both "agent.skills" and "assets.skills" prefixes
        if tools_module.startswith("agent.skills."):
            tools_module = "assets.skills." + tools_module[len("agent.skills.") :]

        relative_path = tools_module.replace(".", "/") + ".py"
        source_path = self.registry.project_root / relative_path

        if not source_path.exists():
            return False, f"Source file not found: {source_path}"

        # Load the module
        try:
            module = self._load_module_from_path(tools_module, source_path)

            # Check for @skill_command decorated functions
            skill_commands = self._extract_commands(module)

            if not skill_commands:
                return False, f"Module has no @skill_command decorated functions."

            # Register (store as dict for compatibility)
            manifest_dict = manifest if isinstance(manifest, dict) else manifest.model_dump()
            self.registry.loaded_skills[skill_name] = manifest_dict
            self.registry.register_module(skill_name, module)

            logger.info("Skill loaded", skill=skill_name, commands=len(skill_commands))
            return True, f"Skill '{skill_name}' loaded via Hot Reload."

        except Exception as e:
            logger.error("Failed to load skill", skill=skill_name, error=str(e))
            return False, f"Load Error: {e}"

    def _resolve_dependencies(self, manifest: dict[str, Any], mcp: FastMCP) -> tuple[bool, str]:
        """Resolve skill dependencies."""
        # Convert to dict if needed
        if hasattr(manifest, "model_dump"):
            manifest_dict = manifest.model_dump()
        else:
            manifest_dict = manifest

        deps = manifest_dict.get("dependencies", {})

        # Skill dependencies
        skill_deps = deps.get("skills", {}) if isinstance(deps, dict) else {}
        if isinstance(deps, list):
            # v1.x format
            skill_deps = {d: "" for d in deps}

        for dep_name in skill_deps.keys():
            if dep_name not in self.registry.loaded_skills:
                success, msg = self.load_skill(dep_name, mcp)
                if not success:
                    return False, f"Dependency '{dep_name}' failed: {msg}"

        return True, ""

    def _load_module_from_path(self, module_name: str, file_path: Path) -> types.ModuleType:
        """
        Load a Python module from a file path without polluting sys.path.
        Enables hot reloading by re-executing the module code.
        """
        # Clear any existing module for hot reload
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Use ModuleLoader for clean parent package handling
        loader = ModuleLoader(self.registry.skills_dir)
        return loader.load_module(module_name, file_path, reload=True)

    def _extract_commands(self, module: types.ModuleType) -> list[str]:
        """Extract @skill_command decorated function names."""
        commands = []
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if callable(obj) and hasattr(obj, _SKILL_COMMAND_MARKER):
                commands.append(name)
        return commands

    def load_module(self, skill_name: str, source_path: Path) -> types.ModuleType:
        """Load a skill module from a specific path."""
        module_name = f"agent.skills.{skill_name}.tools"
        return self._load_module_from_path(module_name, source_path)
