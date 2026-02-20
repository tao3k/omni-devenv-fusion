"""Tests for kernel skill_loader recursive command discovery."""

from __future__ import annotations

import pytest

from omni.core.kernel.components.skill_loader import load_skill_scripts


@pytest.mark.asyncio
async def test_load_skill_scripts_discovers_nested_commands(tmp_path) -> None:
    """Nested scripts directories should be scanned for @skill_command tools."""
    scripts_dir = tmp_path / "skills" / "sample" / "scripts"
    nested_dir = scripts_dir / "nested"
    nested_dir.mkdir(parents=True)

    (nested_dir / "commands.py").write_text(
        "from omni.foundation.api.decorators import skill_command\n"
        '@skill_command(name="nested_cmd", description="nested command")\n'
        "def nested_cmd():\n"
        '    return {"status": "ok"}\n'
    )

    commands = await load_skill_scripts("sample", scripts_dir)
    assert "nested_cmd" in commands


@pytest.mark.asyncio
async def test_load_skill_scripts_supports_nested_relative_imports(tmp_path) -> None:
    """Nested modules using relative imports should load correctly."""
    scripts_dir = tmp_path / "skills" / "sample_rel" / "scripts"
    nested_dir = scripts_dir / "workflow"
    nested_dir.mkdir(parents=True)

    (nested_dir / "helpers.py").write_text("VALUE = 42\n")
    (nested_dir / "entry.py").write_text(
        "from .helpers import VALUE\n"
        "from omni.foundation.api.decorators import skill_command\n"
        '@skill_command(name="workflow_cmd", description="workflow command")\n'
        "def workflow_cmd():\n"
        '    return {"value": VALUE}\n'
    )

    commands = await load_skill_scripts("sample_rel", scripts_dir)
    assert "workflow_cmd" in commands
