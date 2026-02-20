"""
kernel/components/skill_loader.py - Skill Loader

Loads skill scripts and extracts @skill_command / @skill_resource functions.
Supports Trinity Architecture: scripts/*.py + decorator-driven discovery.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from typing import TYPE_CHECKING, Any

from omni.foundation.config.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

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

    namespace_packages: list[tuple[str, Path | None]] = [
        ("omni", None),
        ("omni.skills", None),
        (pkg_name, scripts_dir.parent),
        (scripts_pkg_name, scripts_dir),
    ]
    for module_name, module_path in namespace_packages:
        mod = sys.modules.get(module_name)
        if mod is None:
            mod = types.ModuleType(module_name)
            sys.modules[module_name] = mod
        if module_path is not None and not hasattr(mod, "__path__"):
            mod.__path__ = [str(module_path)]

    return scripts_pkg_name


def _iter_script_paths(scripts_dir: Path) -> list[Path]:
    """Return all skill script files in deterministic order (recursive)."""
    candidates = []
    for script_path in scripts_dir.rglob("*.py"):
        if "__pycache__" in script_path.parts:
            continue
        if script_path.name == "__init__.py":
            continue
        candidates.append(script_path)
    return sorted(candidates, key=lambda p: (len(p.relative_to(scripts_dir).parts), str(p)))


def _ensure_nested_package_namespaces(
    scripts_dir: Path,
    scripts_pkg_name: str,
    script_path: Path,
) -> None:
    """Create namespace package chain for nested script modules."""
    rel_parts = script_path.relative_to(scripts_dir).parts[:-1]
    package_name = scripts_pkg_name
    package_path = scripts_dir
    for part in rel_parts:
        package_name = f"{package_name}.{part}"
        package_path = package_path / part
        mod = sys.modules.get(package_name)
        if mod is None:
            mod = types.ModuleType(package_name)
            sys.modules[package_name] = mod
        if not hasattr(mod, "__path__"):
            mod.__path__ = [str(package_path)]


def _module_name_for_script(scripts_dir: Path, scripts_pkg_name: str, script_path: Path) -> str:
    rel_module_path = script_path.relative_to(scripts_dir).with_suffix("")
    return f"{scripts_pkg_name}.{'.'.join(rel_module_path.parts)}"


def _load_modules(scripts_dir: Path, scripts_pkg_name: str):
    """Yield loaded modules from scripts directory (recursive)."""
    for script_path in _iter_script_paths(scripts_dir):
        module_full_name = _module_name_for_script(scripts_dir, scripts_pkg_name, script_path)
        _ensure_nested_package_namespaces(scripts_dir, scripts_pkg_name, script_path)
        module_package = module_full_name.rpartition(".")[0]
        try:
            if module_full_name in sys.modules:
                yield sys.modules[module_full_name]
            else:
                spec = importlib.util.spec_from_file_location(module_full_name, script_path)
                if spec and spec.loader:
                    module = types.ModuleType(module_full_name)
                    module.__package__ = module_package
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
