"""
Skill Manifest and Structure Integration Tests

Parametrized tests for validating all skills in the skills directory.
Each skill is tested independently with clear failure reporting.
Uses Rust scanner for SKILL.md parsing.

Run with:
    pytest integration/skills/test_manifest_structure.py -v
"""

import ast
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from agent.core.skill_discovery import parse_skill_md
from common.skills_path import SKILLS_DIR, get_all_skill_paths


# Get all valid skill directories once at module load
_SKILLS_PATH = SKILLS_DIR()
_ALL_SKILLS = get_all_skill_paths(_SKILLS_PATH)


def _get_registry():
    """Get a fresh registry instance."""
    import agent.core.skill_registry as sr_module

    sr_module.SkillRegistry._instance = None
    reg = sr_module.get_skill_registry()
    reg.loaded_skills.clear()
    reg.module_cache.clear()
    return reg


def _get_real_mcp():
    """Create a mock MCP server."""
    return MagicMock()


# =============================================================================
# Parametrized Manifest Tests
# =============================================================================


@pytest.mark.parametrize(
    "skill_dir",
    _ALL_SKILLS,
    ids=[p.name for p in _ALL_SKILLS],
)
def test_skill_has_valid_manifest(skill_dir: Path):
    """Every skill must have a valid SKILL.md with required fields."""
    skill_md = skill_dir / "SKILL.md"
    assert skill_md.exists(), f"{skill_dir.name}: SKILL.md not found"

    # Use Rust scanner for high-performance parsing
    data = parse_skill_md(skill_dir) or {}
    assert "name" in data, f"{skill_dir.name}: 'name' field missing"
    assert "version" in data, f"{skill_dir.name}: 'version' field missing"
    assert "description" in data, f"{skill_dir.name}: 'description' field missing"


@pytest.mark.parametrize(
    "skill_dir",
    _ALL_SKILLS,
    ids=[p.name for p in _ALL_SKILLS],
)
def test_skill_manifest_name_matches_directory(skill_dir: Path):
    """SKILL.md name field must match the skill directory name."""
    skill_md = skill_dir / "SKILL.md"

    # Use Rust scanner for high-performance parsing
    data = parse_skill_md(skill_dir) or {}
    manifest_name = data.get("name", "")
    assert manifest_name == skill_dir.name, (
        f"{skill_dir.name}: SKILL.md name '{manifest_name}' doesn't match directory"
    )


@pytest.mark.parametrize(
    "skill_dir",
    _ALL_SKILLS,
    ids=[p.name for p in _ALL_SKILLS],
)
def test_skill_manifest_version_format(skill_dir: Path):
    """SKILL.md version should follow semver format (x.y.z)."""
    # Use Rust scanner for high-performance parsing
    data = parse_skill_md(skill_dir) or {}
    version = data.get("version", "")
    parts = version.split(".")

    assert len(parts) >= 2, f"{skill_dir.name}: version '{version}' format invalid"
    for part in parts[:3]:  # Check major.minor.patch
        assert part.isdigit(), f"{skill_dir.name}: version '{version}' contains non-digits"


# =============================================================================
# Parametrized Structure Tests
# =============================================================================


@pytest.mark.parametrize(
    "skill_dir",
    _ALL_SKILLS,
    ids=[p.name for p in _ALL_SKILLS],
)
def test_skill_has_tools_py(skill_dir: Path):
    """Every skill must have a scripts/ directory with Python files."""
    scripts_dir = skill_dir / "scripts"
    # Check for scripts/ directory with at least one .py file (excluding __init__.py)
    has_scripts = scripts_dir.exists() and any(
        f.suffix == ".py" and f.name != "__init__.py" for f in scripts_dir.iterdir()
    )
    assert has_scripts, f"{skill_dir.name}: scripts/*.py not found (Phase 63: scripts/ required)"


@pytest.mark.parametrize(
    "skill_dir",
    _ALL_SKILLS,
    ids=[p.name for p in _ALL_SKILLS],
)
def test_skill_directory_not_empty(skill_dir: Path):
    """Skill directory should not be empty."""
    files = list(skill_dir.iterdir())
    assert len(files) > 0, f"{skill_dir.name}: directory is empty"


# =============================================================================
# Parametrized Code Quality Tests
# =============================================================================


@pytest.mark.parametrize(
    "skill_dir",
    _ALL_SKILLS,
    ids=[p.name for p in _ALL_SKILLS],
)
def test_skill_tools_py_valid_python(skill_dir: Path):
    """scripts/*.py files should be valid Python syntax."""
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for script_file in scripts_dir.glob("*.py"):
            if script_file.name != "__init__.py":
                with open(script_file) as f:
                    content = f.read()
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    pytest.fail(
                        f"{skill_dir.name}/scripts/{script_file.name} has syntax error: {e}"
                    )


# =============================================================================
# Registry Integration Tests
# =============================================================================


@pytest.mark.parametrize(
    "skill_name",
    ["git", "filesystem"],
    ids=["git", "filesystem"],
)
def test_registry_loads_skill(skill_name: str):
    """Registry should be able to load core skills."""
    registry = _get_registry()
    real_mcp = _get_real_mcp()

    success, message = registry.load_skill(skill_name, real_mcp)
    assert success, f"Failed to load {skill_name}: {message}"
    assert skill_name in registry.loaded_skills


@pytest.mark.parametrize(
    "skill_dir",
    _ALL_SKILLS,
    ids=[p.name for p in _ALL_SKILLS],
)
def test_registry_discovers_all_skills(skill_dir: Path):
    """All skills should be discoverable by the registry."""
    registry = _get_registry()
    available = registry.list_available_skills()

    assert skill_dir.name in available, f"{skill_dir.name} not in discovered skills"
