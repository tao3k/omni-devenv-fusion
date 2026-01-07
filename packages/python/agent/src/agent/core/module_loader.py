"""
agent/core/module_loader.py
Phase 29: Clean Module Loader

Context manager for pollution-free module loading.
Eliminates complex sys.modules manipulation with a clean interface.
"""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import structlog

logger = structlog.get_logger(__name__)


@contextmanager
def module_loader(skills_dir: Path) -> Generator["ModuleLoader", None, None]:
    """
    Context manager for loading skill modules without polluting sys.modules.

    Usage:
        with module_loader(skills_dir) as loader:
            module = loader.load_module("agent.skills.git.tools", tools_path)

    This ensures:
    - Parent packages are created if needed
    - Decorators module is pre-loaded
    - Modules are properly cleaned up on exit (optional)
    """
    loader = ModuleLoader(skills_dir)
    try:
        # Ensure parent packages exist
        loader._ensure_parent_packages()
        # Pre-load decorators if available
        loader._preload_decorators()
        yield loader
    except Exception as e:
        logger.error("Module loading failed", error=str(e))
        raise


class ModuleLoader:
    """
    Handles pollution-free module loading for skills.

    Responsibilities:
    - Create parent packages in sys.modules for relative imports
    - Pre-load decorators module for @skill_command support
    - Load modules with proper __package__ set
    - Support hot-reload by clearing existing modules
    """

    __slots__ = ("skills_dir", "project_root")

    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir
        self.project_root = skills_dir.parent.parent  # assets/skills -> project_root

    def _ensure_parent_packages(self) -> None:
        """Create parent packages for skill modules."""
        # Ensure 'agent' package exists
        if "agent" not in sys.modules:
            agent_src = self.project_root / "packages/python/agent/src/agent"
            agent_pkg = types.ModuleType("agent")
            agent_pkg.__path__ = [str(agent_src)]
            agent_pkg.__file__ = str(agent_src / "__init__.py")
            sys.modules["agent"] = agent_pkg
            logger.debug("Created 'agent' package in sys.modules")

        # Ensure 'agent.skills' package exists
        if "agent.skills" not in sys.modules:
            skills_pkg = types.ModuleType("agent.skills")
            skills_pkg.__path__ = [str(self.skills_dir)]
            skills_pkg.__file__ = str(self.skills_dir / "__init__.py")
            sys.modules["agent.skills"] = skills_pkg
            sys.modules["agent"].skills = skills_pkg
            logger.debug("Created 'agent.skills' package in sys.modules")

    def _preload_decorators(self) -> None:
        """Pre-load the decorators module for @skill_command support."""
        from importlib import util

        decorators_path = self.project_root / "packages/python/agent/src/agent/skills/decorators.py"

        if "agent.skills.decorators" in sys.modules:
            return  # Already loaded

        if not decorators_path.exists():
            logger.warning("decorators.py not found at expected path")
            return

        try:
            spec = util.spec_from_file_location("agent.skills.decorators", decorators_path)
            if spec is None or spec.loader is None:
                logger.error("Could not create spec for decorators.py")
                return

            module = util.module_from_spec(spec)
            sys.modules["agent.skills.decorators"] = module
            sys.modules["agent.skills"].decorators = module
            spec.loader.exec_module(module)
            logger.debug("Pre-loaded agent.skills.decorators")
        except Exception as e:
            logger.error("Failed to preload decorators", error=str(e))

    def load_module(
        self,
        module_name: str,
        file_path: Path,
        *,
        reload: bool = True,
    ) -> types.ModuleType:
        """
        Load a module from a file path without polluting sys.modules.

        Args:
            module_name: Full module name (e.g., 'agent.skills.git.tools')
            file_path: Path to the .py file
            reload: If True, clear existing module for hot-reload

        Returns:
            The loaded module
        """
        import importlib.util

        # Clear existing module for hot-reload
        if reload and module_name in sys.modules:
            del sys.modules[module_name]

        # Clear parent package too
        parent_name = module_name.rsplit(".", 1)[0] if "." in module_name else ""
        if parent_name and parent_name in sys.modules:
            del sys.modules[parent_name]

        # Create spec and module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create spec for {file_path}")

        module = importlib.util.module_from_spec(spec)

        # Set __package__ for relative imports
        if "." in module_name:
            module.__package__ = module_name.rsplit(".", 1)[0]
        else:
            module.__package__ = ""

        # Register and execute
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
            logger.debug("Loaded module", module=module_name)
        except Exception:
            if module_name in sys.modules:
                del sys.modules[module_name]
            raise

        return module

    def unload_module(self, module_name: str) -> None:
        """Unload a module and its children from sys.modules."""
        # Unload the module
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Unload children (e.g., 'agent.skills.git.tools' -> 'agent.skills.git')
        parent_name = module_name.rsplit(".", 1)[0] if "." in module_name else ""
        if parent_name and parent_name in sys.modules:
            del sys.modules[parent_name]

        logger.debug("Unloaded module", module=module_name)


# =============================================================================
# Convenience Functions
# =============================================================================


def get_decorators_module() -> types.ModuleType | None:
    """Get the pre-loaded decorators module."""
    return sys.modules.get("agent.skills.decorators")


def clear_skill_modules(skill_name: str) -> None:
    """Clear all modules related to a skill."""
    prefix = f"agent.skills.{skill_name}"
    modules_to_remove = [k for k in sys.modules if k.startswith(prefix)]

    for mod in modules_to_remove:
        del sys.modules[mod]

    logger.debug("Cleared skill modules", skill=skill_name, count=len(modules_to_remove))


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "module_loader",
    "ModuleLoader",
    "get_decorators_module",
    "clear_skill_modules",
]
