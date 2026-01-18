"""
agent/core/registry/loader.py
 Skill Loader with scripts/ support

Module loading with spec-based loading and hot-reload support.
Supports both legacy tools.py and new scripts/__init__.py patterns.
Pure MCP Server compatible.
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
    from mcp.server import Server

logger = structlog.get_logger(__name__)

# Marker attributes for @skill_command and @skill_command decorated functions
_SKILL_COMMAND_MARKER = "_is_skill_command"
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

    def load_skill(self, skill_name: str, mcp: "Server | None" = None) -> tuple[bool, str]:
        """
        Dynamically load a skill into the MCP server.
        Supports HOT RELOAD.
         Supports both scripts/__init__.py and tools.py.
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

        #  Support scripts/ directory (preferred) and tools.py (legacy)
        scripts_dir = self.registry.skills_dir / skill_name / "scripts"
        tools_path = self.registry.skills_dir / skill_name / "tools.py"

        if scripts_dir.exists() and (scripts_dir / "__init__.py").exists():
            # New scripts/ pattern (+)
            source_path = scripts_dir / "__init__.py"
            tools_module = f"agent.skills.{skill_name}.scripts"
        elif tools_path.exists():
            # Legacy tools.py pattern
            source_path = tools_path
            tools_module = f"agent.skills.{skill_name}.tools"
        else:
            return False, f"No scripts/__init__.py or tools.py found for {skill_name}"

        # Load the module
        try:
            module = self._load_module_from_path(tools_module, source_path)

            # Check for @skill_command or @skill_command decorated functions
            skill_commands = self._extract_commands(module)

            if not skill_commands:
                return False, f"Module has no @skill_command or @skill_command decorated functions."

            # Register (store as dict for compatibility)
            manifest_dict = manifest if isinstance(manifest, dict) else manifest.model_dump()
            self.registry.loaded_skills[skill_name] = manifest_dict
            self.registry.register_module(skill_name, module)

            # No debug log for successful load - only errors matter
            return True, f"Skill '{skill_name}' loaded via Hot Reload."

        except Exception as e:
            logger.error("Failed to load skill", skill=skill_name, error=str(e))
            return False, f"Load Error: {e}"

    def _resolve_dependencies(
        self, manifest: dict[str, Any], mcp: "Server | None"
    ) -> tuple[bool, str]:
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
        """Extract @skill_command or @skill_command decorated function names."""
        commands = []
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if callable(obj) and (
                hasattr(obj, _SKILL_COMMAND_MARKER) or hasattr(obj, _SKILL_COMMAND_MARKER)
            ):
                commands.append(name)
        return commands

    def load_module(self, skill_name: str, source_path: Path) -> types.ModuleType:
        """Load a skill module from a specific path.

        Determines module name based on path type.
        """
        if "scripts" in str(source_path):
            module_name = f"agent.skills.{skill_name}.scripts"
        else:
            module_name = f"agent.skills.{skill_name}.tools"
        return self._load_module_from_path(module_name, source_path)
