"""Tests for scanner fixtures modernization."""

from __future__ import annotations

from pathlib import Path

from omni.test_kit.fixtures.scanner import SkillTestBuilder, SkillTestSuite


def test_skill_test_builder_creates_skill_layout(tmp_path: Path) -> None:
    builder = SkillTestBuilder("demo_skill")
    builder.with_metadata(description="demo")
    builder.with_script("tool.py", "def tool():\n    return 'ok'\n")

    skill_path = Path(builder.create(str(tmp_path)))

    assert (skill_path / "SKILL.md").exists()
    assert (skill_path / "scripts" / "tool.py").exists()


def test_skill_test_suite_create_multi_skill_uses_single_base_dir(tmp_path: Path) -> None:
    suite = SkillTestSuite(tmp_path)
    suite.create_multi_skill(
        [
            {"name": "skill_one", "description": "one"},
            {"name": "skill_two", "description": "two"},
        ],
        add_invalid=True,
    )

    assert (tmp_path / "skill_one" / "SKILL.md").exists()
    assert (tmp_path / "skill_two" / "SKILL.md").exists()
    assert (tmp_path / "invalid_skill").exists()
