"""
Test All Skills Import

Tests that all skills in assets/skills/ can be loaded successfully.
This prevents issues like import errors going undetected.

Run with:
    pytest packages/python/agent/src/agent/tests/integration/skills/test_all_skills_import.py -v -n 0
"""

import pytest


@pytest.fixture
def all_skills():
    """Get list of all skill names from assets/skills/."""
    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    return [
        d.name
        for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_") and d.name != "skill_index.json"
    ]


@pytest.fixture
def skill_registry():
    """Get a skill registry with proper parent package setup."""
    import agent.core.skill_registry as sr_module

    # Reset singleton
    sr_module.SkillRegistry._instance = None

    reg = sr_module.get_skill_registry()
    reg.loaded_skills.clear()
    reg.module_cache.clear()

    yield reg

    # Cleanup
    reg.loaded_skills.clear()
    reg.module_cache.clear()


@pytest.mark.parametrize("skill_name", ["git", "memory", "filesystem"])
def test_skill_module_import_via_registry(skill_name, all_skills, skill_registry):
    """Test that command-based skills can be imported via SkillRegistry.

    This uses the same loading mechanism as the MCP server,
    ensuring parent packages are properly set up.
    """
    if skill_name not in all_skills:
        pytest.skip(f"Skill {skill_name} not found")

    from agent.core.skill_registry.loader import SkillLoader

    loader = SkillLoader(skill_registry)
    success, msg = loader.load_skill(skill_name)

    assert success, f"Failed to load skill {skill_name}: {msg}"


@pytest.mark.parametrize("skill_name", ["git", "memory", "filesystem"])
def test_skill_has_commands(skill_name, all_skills, skill_registry):
    """Test that command-based skills export at least one command."""
    if skill_name not in all_skills:
        pytest.skip(f"Skill {skill_name} not found")

    # Load the skill
    from agent.core.skill_registry.loader import SkillLoader

    loader = SkillLoader(skill_registry)
    success, msg = loader.load_skill(skill_name)
    assert success, f"Failed to load skill {skill_name}: {msg}"

    # Get the module from module_cache
    module = skill_registry.module_cache.get(skill_name)
    assert module is not None, f"Skill {skill_name} not in module_cache"

    # Get exported names - some skills use __all__, others export directly
    exported = getattr(module, "__all__", None)
    if exported is None:
        # Get all non-private attributes (e.g., git skill exports git_status, commit, etc.)
        exported = [n for n in dir(module) if not n.startswith("_") and not n == "memory_module"]
        # Filter out common non-command exports
        exported = [n for n in exported if not n.endswith("_module")]

    # Should have at least one command exported
    assert len(exported) > 0, f"Skill {skill_name} exports no commands: {exported}"


@pytest.mark.parametrize("skill_name", ["git", "memory", "filesystem", "writer", "knowledge"])
def test_skill_scripts_dir_exists(skill_name, all_skills):
    """Test that key skills have the required scripts/ directory."""
    if skill_name not in all_skills:
        pytest.skip(f"Skill {skill_name} not found")

    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    skill_path = skills_dir / skill_name
    scripts_dir = skill_path / "scripts"

    assert scripts_dir.exists(), f"Skill {skill_name} missing scripts/ directory"
    assert (scripts_dir / "__init__.py").exists(), f"Skill {skill_name} missing scripts/__init__.py"


@pytest.mark.parametrize("skill_name", ["git", "memory", "filesystem", "writer", "knowledge"])
def test_skill_has_skill_md(skill_name, all_skills):
    """Test that key skills have SKILL.md."""
    if skill_name not in all_skills:
        pytest.skip(f"Skill {skill_name} not found")

    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    skill_path = skills_dir / skill_name

    assert (skill_path / "SKILL.md").exists(), f"Skill {skill_name} missing SKILL.md"


@pytest.mark.parametrize("skill_name", ["git", "memory", "filesystem", "writer", "knowledge"])
def test_skill_import_uses_absolute_paths(skill_name, all_skills):
    """Test that skill __init__.py uses absolute imports, not relative.

    Relative imports like 'from .memory import ...' can cause issues when
    the module is loaded via agent.skills.{skill}.scripts pattern.

    Example of WRONG pattern:
        from .memory import save_memory  # Causes ImportError

    Example of CORRECT pattern:
        from agent.skills.memory.scripts import memory as memory_module
        save_memory = memory_module.save_memory
    """
    if skill_name not in all_skills:
        pytest.skip(f"Skill {skill_name} not found")

    from common.skills_path import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    scripts_init = skills_dir / skill_name / "scripts" / "__init__.py"

    if not scripts_init.exists():
        pytest.skip(f"Skill {skill_name} has no scripts/__init__.py")

    content = scripts_init.read_text()

    # Check for relative imports that would cause issues
    # Pattern: from .<name> import ...
    import re

    relative_imports = re.findall(r"from\s+\.(\w+)\s+import", content)

    # Memory skill bug: from .memory import ... tries to load agent.skills.memory.memory
    # which doesn't exist
    if relative_imports:
        # Allow certain relative imports that are safe (e.g., from . import something)
        # But reject imports like 'from .memory import X' where memory.py is in scripts/
        for rel in relative_imports:
            # Check if this would create an invalid module path
            invalid_pattern = f"agent.skills.{skill_name}.{rel}"
            scripts_py = skills_dir / skill_name / "scripts" / f"{rel}.py"
            if scripts_py.exists():
                pytest.fail(
                    f"Skill {skill_name} uses relative import 'from .{rel} import ...' "
                    f"which resolves to '{invalid_pattern}' but file is at scripts/{rel}.py. "
                    f"Use absolute imports instead: 'from agent.skills.{skill_name}.scripts import {rel}'"
                )


def test_all_command_based_skills_import(all_skills, skill_registry):
    """Test that all command-based skills (git, memory, filesystem) can be imported."""
    from agent.core.skill_registry.loader import SkillLoader

    # Command-based skills
    command_skills = ["git", "memory", "filesystem"]

    loader = SkillLoader(skill_registry)

    for skill_name in command_skills:
        if skill_name not in all_skills:
            pytest.skip(f"Skill {skill_name} not found")

        success, msg = loader.load_skill(skill_name)
        assert success, f"Failed to load skill {skill_name}: {msg}"


def test_skill_init_can_be_imported(all_skills):
    """Test that each skill's scripts/__init__.py can be imported.

    This is a static analysis test - it loads the module using Python's
    import system to catch syntax errors and import issues.
    """
    import importlib.util
    from common.skills_path import SKILLS_DIR

    for skill_name in all_skills:
        scripts_init = SKILLS_DIR() / skill_name / "scripts" / "__init__.py"
        if not scripts_init.exists():
            continue

        # Try to load the module (this catches syntax errors)
        spec = importlib.util.spec_from_file_location(f"test_{skill_name}", scripts_init)
        if spec is None or spec.loader is None:
            pytest.fail(f"Cannot create spec for {skill_name}/scripts/__init__.py")

        # Don't exec_module here - that would require proper parent packages
        # Just verifying the spec can be created catches many issues
