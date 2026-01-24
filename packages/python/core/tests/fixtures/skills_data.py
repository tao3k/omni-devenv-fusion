"""
Skill Data Fixtures

Factory fixtures for creating test skills dynamically.
Loaded automatically as pytest plugins.

Fixtures:
    - skill_factory: Create test skills dynamically
    - toxic_skill_factory: Create intentionally broken skills

Functions:
    - get_all_skill_paths: Get all valid skill directories
    - parse_skill_manifest: Parse SKILL.md frontmatter (using Rust scanner)
    - validate_python_syntax: Validate Python file syntax
"""

import ast
import shutil
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest

from omni.foundation.config.skills import get_all_skill_paths


def parse_skill_md(skill_path: Path) -> dict[str, Any] | None:
    """Parse SKILL.md frontmatter to extract manifest."""
    skill_md_path = skill_path / "SKILL.md"
    if not skill_md_path.exists():
        return None

    try:
        content = skill_md_path.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 3)
            if len(parts) >= 2:
                import yaml

                manifest = yaml.safe_load(parts[1])
                if isinstance(manifest, dict):
                    return manifest
    except Exception:
        pass

    return None


@pytest.fixture
def fixtures_skills_data_skill_factory(
    tmp_path: Path,
) -> Generator[Callable[..., Path]]:
    """Factory Fixture: Create test skills dynamically.

    Usage:
        def test_something(skill_factory):
            skill_dir = skill_factory("test_skill", content="# test code")
            assert (skill_dir / "tools.py").exists()

    Yields a function that creates skills in a temp directory.
    Cleanup is automatic after the test.
    """
    created: list[Path] = []

    def _create(
        name: str,
        content: str = "# Test skill\n\n@skill_command\ndef test_tool():\n    pass\n",
        manifest: dict | None = None,
    ) -> Path:
        """Create a skill directory with tools.py and optional manifest."""
        skill_dir = tmp_path / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Create tools.py
        tools_file = skill_dir / "tools.py"
        tools_file.write_text(content)

        # Create __init__.py
        (skill_dir / "__init__.py").touch()

        # Create SKILL.md with manifest
        manifest_data = manifest or {
            "name": name,
            "version": "0.1.0",
            "description": f"Test skill: {name}",
            "tools_module": f"omni.skills.{name}.tools",
        }

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(
            "---\n" + "\n".join(f"{k}: {v}" for k, v in manifest_data.items()) + "\n---\n"
        )

        created.append(skill_dir)
        return skill_dir

    yield _create

    # Cleanup after test
    for path in created:
        if path.exists():
            shutil.rmtree(path)


@pytest.fixture
def fixtures_skills_data_toxic_skill_factory(
    tmp_path: Path,
) -> Generator[Callable[..., Path]]:
    """Factory Fixture: Create intentionally broken skills for error handling tests.

    Usage:
        def test_handles_broken_skill(toxic_skill_factory):
            bad_skill = toxic_skill_factory("bad_skill", error_type="syntax_error")
            # Registry should handle this gracefully
    """
    created: list[Path] = []

    def _create(name: str, error_type: str = "syntax_error") -> Path:
        """Create a skill with a specific error type."""
        skill_dir = tmp_path / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        if error_type == "syntax_error":
            content = "def broken(\n    # Missing closing parenthesis\n"
        elif error_type == "import_error":
            content = "from nonexistent_module import stuff\n"
        elif error_type == "missing_tools":
            content = "# No tools defined\n"
        elif error_type == "invalid_manifest":
            content = "---\nname: invalid name with spaces\nversion: 1.0.0\n---\n"
        else:
            content = "# Unknown error type\n"

        (skill_dir / "tools.py").write_text(content)
        (skill_dir / "__init__.py").touch()

        # Create SKILL.md
        manifest = {
            "name": name,
            "version": "0.1.0",
            "description": f"Toxic skill: {error_type}",
        }
        (skill_dir / "SKILL.md").write_text(
            "---\n" + "\n".join(f"{k}: {v}" for k, v in manifest.items()) + "\n---\n"
        )

        created.append(skill_dir)
        return skill_dir

    yield _create

    # Cleanup
    for path in created:
        if path.exists():
            shutil.rmtree(path)


# Re-export for backward compatibility
get_all_skill_paths = get_all_skill_paths


def parse_skill_manifest(skill_dir: Path) -> dict:
    """Parse SKILL.md frontmatter into a dict using Rust scanner."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {}

    # Use Rust scanner for high-performance parsing
    data = parse_skill_md(skill_dir) or {}
    data["tools_module"] = f"omni.skills.{skill_dir.name}.tools"
    return data


def validate_python_syntax(file_path: Path) -> tuple[bool, str]:
    """Validate Python file syntax, return (is_valid, error_message)."""
    try:
        with open(file_path) as f:
            ast.parse(f.read())
        return True, ""
    except SyntaxError as e:
        return False, str(e)
