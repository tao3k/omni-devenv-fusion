"""
tests/utils/fixtures.py
Toxic Skill Fixtures - Centralized test fixture definitions.

Replaces if/elif chains with dictionary-based factory pattern.
"""

from pathlib import Path
from typing import Callable


# =============================================================================
# Toxic Skill Templates (Dictionary-based, no if/elif chains)
# =============================================================================

# Template for toxic skills - each key maps to a complete tools.py content
TOXIC_SKILL_TEMPLATES: dict[str, str] = {
    "syntax_error": """\
from agent.skills.decorators import skill_command

@skill_command(category='test', description='test')
def dummy_command():
    THIS IS NOT PYTHON CODE !!!
""",
    "import_error": """\
from agent.skills.decorators import skill_command
import non_existent_module_xyz_123

@skill_command(category='test', description='test')
def dummy_command():
    pass
""",
    "runtime_error": """\
from agent.skills.decorators import skill_command

@skill_command(category='test', description='test')
def dummy_command():
    raise ValueError('Boom! Toxic skill exploded!')
""",
    "missing_exposed": """\
# No @skill_command decorators!
def some_other_function():
    pass
""",
    "circular_import": """\
from agent.skills.decorators import skill_command
from {name} import circular

@skill_command(category='test', description='test')
def dummy_command():
    pass
""",
    "invalid_exposed_format": """\
from agent.skills.decorators import skill_command

# Invalid decorator usage
def dummy_command():
    pass
""",
}


def create_toxic_skill_factory(skills_dir: Path) -> Callable[[str, str], tuple[str, str]]:
    """
    Create a toxic skill factory function.

    Args:
        skills_dir: Base directory for skills (e.g., Path("assets/skills"))

    Returns:
        A factory function that creates toxic skills for testing.

    Usage:
        factory = create_toxic_skill_factory(Path("assets/skills"))
        name, module_name = factory("toxic_syntax", "syntax_error")
    """
    created_paths: list[Path] = []

    def _create(
        name: str, toxic_type: str, tools_module_path: str | None = None
    ) -> tuple[str, str]:
        """Create a toxic skill for testing.

        Args:
            name: Skill directory name (e.g., 'toxic_syntax')
            toxic_type: Type of toxicity - one of TOXIC_SKILL_TEMPLATES keys
            tools_module_path: Custom tools module path (defaults to assets.skills.{name}.tools)

        Returns:
            Tuple of (skill_name, module_name)
        """
        # Get template
        template = TOXIC_SKILL_TEMPLATES.get(toxic_type)
        if template is None:
            valid_types = ", ".join(sorted(TOXIC_SKILL_TEMPLATES.keys()))
            raise ValueError(f"Unknown toxic_type: {toxic_type!r}. Valid types: {valid_types}")

        # Create skill directory
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        created_paths.append(skill_dir)

        # Create manifest directory (separate for cleaner structure)
        manifest_dir = skill_dir
        manifest_dir.mkdir(parents=True, exist_ok=True)
        created_paths.append(manifest_dir)

        # Determine module name
        module_name = tools_module_path or f"assets.skills.{name}.tools"

        # Write SKILL.md (unified manifest format)
        skill_md_content = f'''\
---
name: "{name}"
version: "0.0.1"
description: "A toxic skill for testing"
routing_keywords: ["test"]
---

# Toxic Guide

This is a test skill.
'''
        (manifest_dir / "SKILL.md").write_text(skill_md_content)

        # Write README.md
        (manifest_dir / "README.md").write_text("# Toxic Guide\n\nThis is a test skill.")

        # Write tools.py with template
        tools_file = skill_dir / "tools.py"
        final_template = template.format(name=name) if "{name}" in template else template
        tools_file.write_text(final_template)

        # Create __init__.py files
        (skill_dir / "__init__.py").touch()
        (manifest_dir / "__init__.py").touch()

        return name, module_name

    def cleanup():
        """Cleanup all created skill directories."""
        import sys

        for path in created_paths:
            try:
                if path.exists():
                    import shutil

                    shutil.rmtree(path)
            except Exception:
                pass

        # Cleanup sys.modules
        for path in created_paths:
            if path.name.startswith("toxic_"):
                module_name = f"assets.skills.{path.name}.tools"
                if module_name in sys.modules:
                    del sys.modules[module_name]

    # Attach cleanup method to factory
    _create.cleanup = cleanup  # type: ignore

    return _create


# =============================================================================
# Skill Loader Utilities (Using common.skills_path)
# =============================================================================

# Use load_skill_module from common.skills_path instead of manual implementation
# This handles path resolution from settings.yaml and module loading automatically


def load_skill_module(skill_name: str):
    """
    Load a skill module using common.skills_path.

    Args:
        skill_name: Name of the skill to load

    Returns:
        The loaded module

    Raises:
        FileNotFoundError: If skill tools.py not found
    """
    from common.skills_path import load_skill_module as _load

    return _load(skill_name)


# =============================================================================
# Assertion Helpers
# =============================================================================


class TestAssertions:
    """Common assertion helpers for tests."""

    @staticmethod
    def contains(haystack: str, needle: str, msg: str = "") -> None:
        assert needle in haystack, f"{msg} Expected '{needle}' in '{haystack[:100]}...'"

    @staticmethod
    def not_contains(haystack: str, needle: str, msg: str = "") -> None:
        assert needle not in haystack, f"{msg} Unexpected '{needle}' in '{haystack[:100]}...'"

    @staticmethod
    def type(obj: object, expected_type: type, msg: str = "") -> None:
        assert isinstance(obj, expected_type), f"{msg} Expected {expected_type}, got {type(obj)}"

    @staticmethod
    def has_attr(obj: object, attr: str, msg: str = "") -> None:
        assert hasattr(obj, attr), f"{msg} Object missing attribute '{attr}'"

    @staticmethod
    def equal(actual: object, expected: object, msg: str = "") -> None:
        assert actual == expected, f"{msg} Expected {expected!r}, got {actual!r}"
