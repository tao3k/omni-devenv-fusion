"""
agent.skills - Skill modules package

This package contains:
- decorators.py: @skill_command decorator for defining skill commands
- core/: Core skill loading and management (skill_manifest_loader, test_framework, etc.)
- <skill_name>/: Individual skill implementations (git, filesystem, etc.)

Architecture:
- skills/<skill>/tools.py: Router layer (dispatch to scripts/)
- skills/<skill>/scripts/: Controller layer (atomic implementations)
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .decorators import skill_command, CommandResult

__all__ = [
    "skill_command",
    "CommandResult",
]


def _register_skills():
    """Dynamically register skills from assets/skills/ as subpackages.

    This allows imports like 'from agent.skills.git.scripts.prepare import ...'
    to work even though skills are in assets/skills/, not agent/skills/.
    """
    # Only run during actual imports, not type checking
    if TYPE_CHECKING:
        return

    try:
        from common.skills_path import SKILLS_DIR

        skills_path = SKILLS_DIR()
        if not skills_path.exists():
            return

        # Get the agent.skills module
        agent_skills_mod = sys.modules.get("agent.skills")
        if agent_skills_mod is None:
            return

        agent_skills_path = Path(agent_skills_mod.__file__).parent

        for skill_dir in skills_path.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_name = skill_dir.name

            # Skip private/dunder directories
            if skill_name.startswith("_"):
                continue

            # Check if skill has scripts directory
            scripts_dir = skill_dir / "scripts"
            if not scripts_dir.is_dir():
                continue

            # Create module path: agent.skills.<skill_name>
            skill_module_name = f"agent.skills.{skill_name}"

            # Skip if already registered
            if skill_module_name in sys.modules:
                continue

            # Add scripts dir to path and register the module
            scripts_path_str = str(scripts_dir)
            if scripts_path_str not in sys.path:
                sys.path.insert(0, scripts_path_str)

            # Create a module for the skill root (so agent.skills.git works)
            import types

            skill_mod = types.ModuleType(skill_module_name)
            skill_mod.__path__ = [str(skill_dir)]
            sys.modules[skill_module_name] = skill_mod

    except Exception:
        # Silently fail - skills registration is optional
        pass


# Register skills on module import
_register_skills()
