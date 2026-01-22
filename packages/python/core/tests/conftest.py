"""omni.core tests configuration and fixtures."""

from __future__ import annotations

import pytest
import asyncio
from pathlib import Path
from typing import Any, Generator


# Compute skills root using PRJ_DIRS (or fallback to path calculation)
def _compute_skills_root() -> Path:
    """Compute skills root using PRJ_DIRS with fallback."""
    try:
        from omni.foundation.config.dirs import PRJ_DIRS

        return PRJ_DIRS("skills", category="data")
    except ImportError:
        # Fallback: conftest is at packages/python/core/tests/conftest.py
        # Need 3 parent levels to reach packages/python, then /assets/skills
        return Path(__file__).resolve().parents[3] / "assets" / "skills"


SKILLS_ROOT = _compute_skills_root()


# =============================================================================
# Centralized Fixtures (shared with agent/tests)
# =============================================================================


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory using git toplevel."""
    from omni.foundation.runtime.gitops import get_project_root

    root = get_project_root()
    assert root.exists(), f"Project root not found: {root}"
    return root


@pytest.fixture
def skills_root() -> Path:
    """Get the skills root directory (assets/skills).

    Uses SKILLS_DIR from omni.foundation.config.skills which correctly
    resolves to assets/skills relative to project root.
    """
    from omni.foundation.config.skills import SKILLS_DIR

    skills = SKILLS_DIR()
    assert skills.exists(), f"Skills directory not found: {skills}"
    return skills


@pytest.fixture
def config_dir() -> Path:
    """Get the config directory (PRJ_CONFIG_HOME)."""
    from omni.foundation.config.dirs import PRJ_DIRS

    return PRJ_DIRS.config_home


class SkillProxy:
    """Proxy object that exposes skill commands as direct methods."""

    def __init__(self, skill_name: str, commands: dict[str, Any]):
        self._skill_name = skill_name
        self._commands = commands

    def __getattr__(self, name: str):
        """Expose commands as methods."""
        if name in self._commands:
            return self._commands[name]
        raise AttributeError(f"Skill '{self._skill_name}' has no command '{name}'")

    def __repr__(self):
        return f"SkillProxy({self._skill_name})"


# Cache for loaded skills
_skill_cache: dict[str, SkillProxy] = {}


def _load_skill_commands(skill_name: str) -> dict[str, Any]:
    """Load skill commands using UniversalScriptSkill."""
    from omni.core.skills import UniversalScriptSkill

    async def load():
        skill = UniversalScriptSkill(skill_name, str(SKILLS_ROOT / skill_name))
        await skill.load({"cwd": str(SKILLS_ROOT)})
        return skill._script_loader.commands if skill._script_loader else {}

    try:
        return asyncio.run(load())
    except Exception:
        return {}


def _ensure_skills_loaded():
    """Load all skills on first use."""
    global _skill_cache
    if _skill_cache:
        return

    if not SKILLS_ROOT.exists():
        return

    for skill_path in SKILLS_ROOT.iterdir():
        if not skill_path.is_dir():
            continue
        if skill_path.name.startswith(("_", ".")):
            continue

        commands = _load_skill_commands(skill_path.name)
        if commands:
            _skill_cache[skill_path.name] = SkillProxy(skill_path.name, commands)


# Skill fixtures - pytest discovers these at module level


@pytest.fixture(scope="function")
def git():
    """Git skill fixture."""
    _ensure_skills_loaded()
    return _skill_cache.get("git")


@pytest.fixture(scope="function")
def knowledge():
    """Knowledge skill fixture."""
    _ensure_skills_loaded()
    return _skill_cache.get("knowledge")


@pytest.fixture(scope="function")
def memory():
    """Memory skill fixture."""
    _ensure_skills_loaded()
    return _skill_cache.get("memory")


@pytest.fixture(scope="function")
def skill():
    """Skill management fixture."""
    _ensure_skills_loaded()
    return _skill_cache.get("skill")


@pytest.fixture(scope="function")
def skills():
    """All skills as a dictionary fixture."""
    _ensure_skills_loaded()
    return _skill_cache


# Import shared fixtures and plugins from the new locations
from .plugins.seed_manager import pytest_configure  # noqa: F401 - Register seed plugin
from .fixtures.core_fixtures import *  # noqa: F401, F403


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def skills_path(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary skills directory structure."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    # Create a sample skill structure
    sample_skill = skills_dir / "sample"
    sample_skill.mkdir()
    (sample_skill / "SKILL.md").write_text("""---
name: sample
version: 1.0.0
description: A sample skill for testing
""")
    scripts_dir = sample_skill / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")

    yield skills_dir


@pytest.fixture
def git_skill_path(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a git skill directory for testing."""
    skills_dir = tmp_path / "skills"
    git_dir = skills_dir / "git"
    git_dir.mkdir()

    # SKILL.md
    (git_dir / "SKILL.md").write_text("""---
name: git
version: 1.0.0
description: Git operations skill
""")

    # scripts/
    scripts_dir = git_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "__init__.py").write_text("")

    # status.py
    (scripts_dir / "status.py").write_text('''"""Git status command."""

def git_status():
    """Get git status."""
    return "Clean"

__all__ = ["git_status"]
''')

    # commit_state.py
    (scripts_dir / "commit_state.py").write_text('''"""Commit state factory."""

def create_initial_state(project_root: str = ".", workflow_id: str = "") -> dict:
    """Create initial commit state."""
    return {
        "project_root": project_root,
        "workflow_id": workflow_id,
        "staged_files": [],
        "status": "pending",
    }

__all__ = ["create_initial_state"]
''')

    yield git_dir
