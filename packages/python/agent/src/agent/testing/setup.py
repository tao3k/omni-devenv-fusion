"""
Module context setup for skill testing.

Sets up package hierarchy in sys.modules to enable absolute imports like:
    from agent.skills.git.scripts import status
"""

import sys
import types
import importlib.util
from pathlib import Path
from common.skills_path import SKILLS_DIR


def _setup_skill_package_context(skill_name: str, skills_root: Path) -> None:
    """
    Set up the package hierarchy in sys.modules for a skill.

    This enables absolute imports like:
        from agent.skills.git.scripts import status

    Without this, relative imports would fail with:
        "ImportError: attempted relative import with no known parent package"
    """
    project_root = skills_root.parent.parent  # assets/skills -> project_root

    # Ensure 'agent' package exists
    if "agent" not in sys.modules:
        agent_src = project_root / "packages/python/agent/src/agent"
        agent_pkg = types.ModuleType("agent")
        agent_pkg.__path__ = [str(agent_src)]
        agent_pkg.__file__ = str(agent_src / "__init__.py")
        sys.modules["agent"] = agent_pkg

    # Ensure 'agent.skills' package exists
    if "agent.skills" not in sys.modules:
        skills_pkg = types.ModuleType("agent.skills")
        skills_pkg.__path__ = [str(skills_root)]
        skills_pkg.__file__ = str(skills_root / "__init__.py")
        sys.modules["agent.skills"] = skills_pkg

    # Ensure 'agent.skills.<skill_name>' package exists
    skill_pkg_name = f"agent.skills.{skill_name}"
    if skill_pkg_name not in sys.modules:
        skill_dir = skills_root / skill_name
        skill_pkg = types.ModuleType(skill_pkg_name)
        skill_pkg.__path__ = [str(skill_dir)]
        skill_pkg.__file__ = str(skill_dir / "__init__.py")
        sys.modules[skill_pkg_name] = skill_pkg

    # Ensure 'agent.skills.<skill_name>.scripts' package exists
    scripts_pkg_name = f"agent.skills.{skill_name}.scripts"
    if scripts_pkg_name not in sys.modules:
        scripts_dir = skills_root / skill_name / "scripts"
        scripts_pkg = types.ModuleType(scripts_pkg_name)
        scripts_pkg.__path__ = [str(scripts_dir)]
        scripts_pkg.__file__ = str(scripts_dir / "__init__.py")
        sys.modules[scripts_pkg_name] = scripts_pkg

    # Pre-load decorators module for @skill_command support
    decorators_name = "agent.skills.decorators"
    if decorators_name not in sys.modules:
        decorators_path = project_root / "packages/python/agent/src/agent/skills/decorators.py"
        if decorators_path.exists():
            spec = importlib.util.spec_from_file_location(decorators_name, str(decorators_path))
            if spec and spec.loader:
                decorators_mod = importlib.util.module_from_spec(spec)
                sys.modules[decorators_name] = decorators_mod
                spec.loader.exec_module(decorators_mod)


def _setup_agent_skills_core() -> None:
    """Manually set up agent.skills.core module if import fails.

    Uses SSOT pattern - no hardcoded paths.
    """
    skills_root = SKILLS_DIR()
    project_root = skills_root.parent
    agent_src = project_root / "packages/python/agent/src/agent"
    core_src = agent_src / "skills/core"

    # Ensure agent.skills.core is in sys.modules
    if "agent.skills.core" not in sys.modules:
        core_pkg = types.ModuleType("agent.skills.core")
        core_pkg.__path__ = [str(core_src)]
        core_pkg.__file__ = str(core_src / "__init__.py")
        sys.modules["agent.skills.core"] = core_pkg

        # Load the __init__.py module
        init_path = core_src / "__init__.py"
        if init_path.exists():
            spec = importlib.util.spec_from_file_location("agent.skills.core", str(init_path))
            if spec and spec.loader:
                init_mod = importlib.util.module_from_spec(spec)
                sys.modules["agent.skills.core"] = init_mod
                spec.loader.exec_module(init_mod)
