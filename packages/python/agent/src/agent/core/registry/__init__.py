"""
agent/core/registry/__init__.py
Phase 29: Skill Registry Module

Modular skill registry with separated concerns:
- core.py: Core registry class
- loader.py: Module loading
- context.py: Context building
- installer.py: Remote installation
- resolver.py: Version resolution
- jit.py: JIT acquisition
"""

from typing import Any

from .core import (
    SkillRegistry,
    get_skill_registry,
    _SKILL_COMMAND_MARKER,
)

from .loader import SkillLoader

from .context import ContextBuilder, get_combined_context

from .installer import RemoteInstaller, install_remote_skill, update_remote_skill

from .resolver import VersionResolver

from .jit import (
    jit_install_skill,
    security_scan_skill,
    discover_skills,
    suggest_skills_for_task,
    list_installed_skills,
)


def get_skill_tools(skill_name: str) -> dict[str, Any]:
    """
    Get all @skill_command decorated tools from a loaded skill.

    Phase 19: Enables ReAct loop to access dynamically loaded skill tools.
    """
    registry = get_skill_registry()
    return registry.get_skill_tools(skill_name)


__all__ = [
    # Core
    "SkillRegistry",
    "get_skill_registry",
    "_SKILL_COMMAND_MARKER",
    # Loader
    "SkillLoader",
    # Context
    "ContextBuilder",
    "get_combined_context",
    # Installer
    "RemoteInstaller",
    "install_remote_skill",
    "update_remote_skill",
    # Resolver
    "VersionResolver",
    # JIT
    "jit_install_skill",
    "security_scan_skill",
    "discover_skills",
    "suggest_skills_for_task",
    "list_installed_skills",
    # Utilities
    "get_skill_tools",
]
