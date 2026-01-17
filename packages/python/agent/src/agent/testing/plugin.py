"""
agent/testing/plugin.py - Pytest Plugin for Skill Tests

Phase 35.1: First-class Pytest plugin that automatically discovers
and registers skill fixtures.

Inspired by Prefect's test harness pattern - no conftest.py needed!

Usage:
    pytest_plugins = ["agent.testing.plugin"]

    def test_my_skill(git):  # 'git' fixture auto-injected
        assert git.status().success

    def test_integration(my_skill, git):  # Multiple skills work too
        my_skill.sync()
        assert git.status()
"""

import pytest
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


def pytest_configure(config):
    """
    Pytest hook: Auto-scan assets/skills and register skill fixtures.

    This runs once at pytest startup, registering all skills as fixtures.
    """
    skills_root = SKILLS_DIR()

    # Register base fixtures first
    _register_base_fixtures(skills_root)

    if not skills_root.exists():
        return

    # Scan all valid skill directories and register fixtures
    for item in skills_root.iterdir():
        if item.is_dir() and not item.name.startswith(("_", ".")):
            _register_skill_fixture(item.name, skills_root)


def _register_base_fixtures(skills_root: Path):
    """Register base fixtures: skills_root, project_root, skills_dir."""

    @pytest.fixture
    def skills_root_fixture() -> Path:
        """Skills root directory (assets/skills)."""
        return SKILLS_DIR()

    @pytest.fixture
    def project_root_fixture() -> Path:
        """Project root directory."""
        return SKILLS_DIR().parent

    @pytest.fixture
    def skills_dir_fixture() -> Path:
        """Alias for skills_root (for backward compatibility)."""
        return SKILLS_DIR()

    @pytest.fixture
    def skills_fixture(request: pytest.FixtureRequest) -> "SkillsContext":
        """
        Unified Skills Context for IDE type hints.

        Usage:
            def test_workflow(skills):  # IDE infers SkillsContext
                skills.git.init()
                skills.docker.run()
        """
        from agent.testing.context import SkillsContext

        return SkillsContext(request)

    # Register them globally
    setattr(sys.modules[__name__], "skills_root", skills_root_fixture)
    setattr(sys.modules[__name__], "project_root", project_root_fixture)
    setattr(sys.modules[__name__], "skills_dir", skills_dir_fixture)
    setattr(sys.modules[__name__], "skills", skills_fixture)


# Reserved pytest fixture names that skills should not override
RESERVED_FIXTURES = {
    # Core fixtures
    "request",
    "config",
    "cache",
    "session",
    "workerinput",
    "workeroutput",
    # IO fixtures
    "capsys",
    "capfd",
    "caplog",
    "pytestconfig",
    "record_testsuite_property",
    # Mocking fixtures
    "monkeypatch",
    "patch",
    "mock",
    "pytester",
    # Flow control
    "pytester",
    "testdir",
    "localpath",
    "tmp_path",
    "tmp_path_factory",
    "tmpdir",
    "tmpdir_factory",
    # Debugging
    "record_xml_property",
    "record_property",
}

# Pytest built-in fixtures (comprehensive list)
PYTEST_BUILTIN_FIXTURES = {
    "request",
    "pytestconfig",
    "cache",
    "testpath",
    "pytester",
    "capsys",
    "capfd",
    "caplog",
    "record_testsuite_property",
    "record_property",
    "monkeypatch",
    "patch",
    "mock",
    "pytester",
    "testdir",
    "localpath",
    "tmpdir",
    "tmpdir_factory",
    "tmp_path",
    "tmp_path_factory",
    "session",
    "workerinput",
    "workeroutput",
    "logging",
    "hookwrapper",
    "mark",
}


def _register_skill_fixture(skill_name: str, skills_root: Path):
    """
    Dynamically create and register a fixture for a skill.

    Phase 63+ only: Only supports scripts/*.py pattern with @skill_command decorators.
    Legacy tools.py pattern is no longer supported.

    Collision Detection:
        - Checks against RESERVED_FIXTURES and PYTEST_BUILTIN_FIXTURES
        - Logs warning if skill name conflicts with pytest built-ins
        - Skills with conflicting names still get registered via skills.git
    """
    # Collision detection
    if skill_name in RESERVED_FIXTURES or skill_name in PYTEST_BUILTIN_FIXTURES:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Skill '{skill_name}' conflicts with pytest fixture. "
            f"Use 'skills.{skill_name}' instead of '{skill_name}' fixture."
        )

    @pytest.fixture(name=skill_name, scope="function")
    def _skill_fixture():
        """Dynamic fixture that loads skill via SkillManager.

        Phase 63+ only: skills/*/scripts/*.py with @skill_command decorators.
        """
        scripts_path = skills_root / skill_name / "scripts"

        if not scripts_path.exists() or not any(scripts_path.glob("*.py")):
            pytest.skip(f"Skill '{skill_name}' has no scripts/*.py (tools.py pattern removed)")

        # Set up package context BEFORE loading (enables agent.skills.git.scripts imports)
        _setup_skill_package_context(skill_name, skills_root)

        # Phase 63+ mode: scripts/*.py with @skill_command
        from agent.core.skill_manager import get_skill_manager

        manager = get_skill_manager()
        skill = manager.skills.get(skill_name)
        if skill is None:
            pytest.skip(f"Skill '{skill_name}' failed to load")
        return skill

    # Register fixture globally
    setattr(sys.modules[__name__], skill_name, _skill_fixture)


# =============================================================================
# Utility Functions (for advanced users)
# =============================================================================


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
    skills_root = SKILLS_DIR()
    tools_path = skills_root / skill_name / "tools.py"
    if not tools_path.exists():
        return None

    module_name = f"_skill_{skill_name}_module"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, str(tools_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Export for convenience
__all__ = [
    "get_skills",
    "get_skill_module",
]
