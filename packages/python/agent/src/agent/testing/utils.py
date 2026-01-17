"""
Utility functions for skill testing.
"""

from pathlib import Path

from common.skills_path import SKILLS_DIR


def get_skills() -> list[str]:
    """List all available skills."""
    skills_root = SKILLS_DIR()
    if not skills_root.exists():
        return []
    return [
        item.name
        for item in skills_root.iterdir()
        if item.is_dir() and not item.name.startswith(("_", "."))
    ]


def get_skill_module(skill_name: str):
    """Get a skill module directly (without fixture)."""
    import importlib.util
    import sys

    skills_root = SKILLS_DIR()
    tools_path = skills_root / skill_name / "tools.py"
    if not tools_path.exists():
        return None

    module_name = f"_skill_{skill_name}_module"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, str(tools_path))
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    return None
