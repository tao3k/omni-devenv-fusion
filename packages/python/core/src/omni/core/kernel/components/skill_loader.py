"""
kernel/components/skill_loader.py - Skill Loader

Loads skill scripts and extracts @skill_command / @skill_resource functions.
Supports Trinity Architecture: scripts/*.py + decorator-driven discovery.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger(__name__)


def _ensure_skill_package(skill_name: str, scripts_dir: Path) -> str:
    """Set up Python package context for a skill's scripts directory.

    Returns the fully-qualified scripts package name.
    """
    pkg_name = f"omni.skills.{skill_name}"
    scripts_pkg_name = f"{pkg_name}.scripts"

    skills_parent = scripts_dir.parent.parent
    if str(skills_parent) not in sys.path:
        sys.path.insert(0, str(skills_parent))

    for parent in ("omni", "omni.skills"):
        if parent not in sys.modules:
            try:
                sys.modules[parent] = types.ModuleType(parent)
            except Exception:
                pass

    if scripts_pkg_name not in sys.modules:
        scripts_init = scripts_dir / "__init__.py"
        if scripts_init.exists():
            spec = importlib.util.spec_from_file_location(scripts_pkg_name, scripts_init)
            if spec:
                pkg = types.ModuleType(scripts_pkg_name)
                pkg.__path__ = [str(scripts_dir)]
                sys.modules[scripts_pkg_name] = pkg

    return scripts_pkg_name


def _load_modules(scripts_dir: Path, scripts_pkg_name: str):
    """Yield loaded modules from scripts directory."""
    for script_path in scripts_dir.glob("*.py"):
        if script_path.name == "__init__.py":
            continue

        module_full_name = f"{scripts_pkg_name}.{script_path.stem}"

        try:
            if module_full_name in sys.modules:
                yield sys.modules[module_full_name]
            else:
                spec = importlib.util.spec_from_file_location(module_full_name, script_path)
                if spec and spec.loader:
                    module = types.ModuleType(module_full_name)
                    module.__package__ = scripts_pkg_name
                    module.__file__ = str(script_path)
                    sys.modules[module_full_name] = module
                    try:
                        spec.loader.exec_module(module)
                    except Exception as e:
                        sys.modules.pop(module_full_name, None)
                        raise e
                    yield module
        except Exception as e:
            logger.warning(f"Failed to load skill script {script_path}: {e}")


async def load_skill_scripts(skill_name: str, scripts_dir: Path) -> dict[str, Any]:
    """Load Skill scripts and extract all @skill_command decorated functions.

    Args:
        skill_name: Skill name.
        scripts_dir: Path to scripts/ directory.

    Returns:
        Mapping of command names to functions.
    """
    commands: dict[str, Any] = {}

    if not scripts_dir.exists():
        return commands

    scripts_pkg_name = _ensure_skill_package(skill_name, scripts_dir)

    for module in _load_modules(scripts_dir, scripts_pkg_name):
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            if callable(obj) and hasattr(obj, "_is_skill_command"):
                config = getattr(obj, "_skill_config", {})
                cmd_name = config.get("name", attr_name) if config else attr_name
                commands[cmd_name] = obj

    return commands


async def load_skill_resources(skill_name: str, scripts_dir: Path) -> dict[str, Any]:
    """Load Skill scripts and extract all @skill_resource decorated functions.

    Args:
        skill_name: Skill name.
        scripts_dir: Path to scripts/ directory.

    Returns:
        Mapping of resource names to functions.
    """
    resources: dict[str, Any] = {}

    if not scripts_dir.exists():
        return resources

    scripts_pkg_name = _ensure_skill_package(skill_name, scripts_dir)

    for module in _load_modules(scripts_dir, scripts_pkg_name):
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            if callable(obj) and hasattr(obj, "_is_skill_resource"):
                config = getattr(obj, "_resource_config", {})
                res_name = config.get("name", attr_name) if config else attr_name
                resources[res_name] = obj

    return resources


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
