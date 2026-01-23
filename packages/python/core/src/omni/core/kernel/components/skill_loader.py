"""
kernel/components/skill_loader.py - Skill Loader

Loads skill scripts and extracts @skill_command functions.
Supports Trinity Architecture: scripts/*.py + @skill_command decorator.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger(__name__)


async def load_skill_scripts(skill_name: str, scripts_dir: Path) -> dict[str, Any]:
    """Load Skill scripts and extract all @skill_command decorated functions.

    Args:
        skill_name: Skill name
        scripts_dir: Path to scripts/ directory

    Returns:
        Mapping of command names to functions
    """
    commands: dict[str, Any] = {}

    if not scripts_dir.exists():
        return commands

    # Set up package context for imports - use omni.skills for simplicity
    pkg_name = f"omni.skills.{skill_name}"
    scripts_pkg_name = f"{pkg_name}.scripts"

    # Ensure parent packages exist in sys.modules
    parent_pkgs = ["omni", "omni.skills"]
    for parent in parent_pkgs:
        if parent not in sys.modules:
            try:
                pkg = types.ModuleType(parent)
                sys.modules[parent] = pkg
            except Exception:
                pass

    # Register scripts package
    if scripts_pkg_name not in sys.modules:
        scripts_init = scripts_dir / "__init__.py"
        if scripts_init.exists():
            spec = importlib.util.spec_from_file_location(scripts_pkg_name, scripts_init)
            if spec:
                pkg = types.ModuleType(scripts_pkg_name)
                pkg.__path__ = [str(scripts_dir)]
                sys.modules[scripts_pkg_name] = pkg

    # Load each script file
    for script_path in scripts_dir.glob("*.py"):
        if script_path.name == "__init__.py":
            continue

        module_name = script_path.stem
        module_full_name = f"{scripts_pkg_name}.{module_name}"

        try:
            # Check if already loaded
            if module_full_name in sys.modules:
                module = sys.modules[module_full_name]
            else:
                # Load the module
                spec = importlib.util.spec_from_file_location(module_full_name, script_path)
                if spec and spec.loader:
                    module = types.ModuleType(module_full_name)
                    module.__package__ = scripts_pkg_name
                    module.__file__ = str(script_path)
                    sys.modules[module_full_name] = spec.loader.exec_module(module)

            # Extract @skill_command functions
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue

                obj = getattr(module, attr_name)
                if callable(obj) and hasattr(obj, "_is_skill_command"):
                    # Auto-generate command name if not set
                    config = getattr(obj, "_skill_config", {})
                    cmd_name = config.get("name", attr_name) if config else attr_name
                    commands[cmd_name] = obj

        except Exception as e:
            # Log but continue - individual script failures shouldn't break skill load
            logger.warning(f"Failed to load skill script {script_path}: {e}")

    return commands


def extract_tool_schema(func: Any) -> dict[str, Any]:
    """Extract MCP tool schema from @skill_command function.

    Args:
        func: Function decorated with @skill_command

    Returns:
        Tool definition dictionary
    """
    config = getattr(func, "_skill_config", {})
    if not config:
        return {}

    return {
        "name": config.get("name", func.__name__),
        "description": config.get("description", func.__doc__ or ""),
        "inputSchema": config.get("input_schema", {"type": "object"}),
    }
