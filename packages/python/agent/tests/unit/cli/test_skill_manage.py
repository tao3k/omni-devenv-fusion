"""
test_skill_manage.py - Skill Management Commands Tests

Tests for:
- run: Execute a skill command
- test: Test skills using the testing framework
- check: Validate skill structure
- install: Install a skill from a remote repository [DEPRECATED]
- update: Update an installed skill [DEPRECATED]

Usage:
    uv run pytest packages/python/agent/tests/unit/cli/test_skill_manage.py -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from omni.agent.cli.app import app


class TestSkillRun:
    """Tests for 'omni skill run' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_run_requires_command(self, runner):
        """Test that run requires a command argument."""
        result = runner.invoke(app, ["skill", "run"])

        assert result.exit_code != 0

    def test_run_with_command_format(self, runner):
        """Test run with skill.command format."""
        result = runner.invoke(app, ["skill", "run", "nonexistent.command"])

        # Should not be a usage error
        assert "requires" not in result.output.lower()


class TestSkillTest:
    """Tests for 'omni skill test' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_test_no_args_shows_usage(self, runner, tmp_path: Path):
        """Test test without arguments shows usage."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "test"])

        assert result.exit_code == 0
        assert "Specify" in result.output or "usage" in result.output.lower()

    def test_test_missing_skill(self, runner, tmp_path: Path):
        """Test test with non-existent skill."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "test", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_test_skill_without_tests(self, runner, tmp_path: Path):
        """Test test with skill that has no tests directory."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        skill_dir = skills_dir / "no_tests"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""
---
name: no_tests
version: 1.0.0
---
""")

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "test", "no_tests"])

        assert result.exit_code == 1
        assert "No tests" in result.output or "not found" in result.output


class TestSkillCheck:
    """Tests for 'omni skill check' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_check_valid_skill(self, runner, tmp_path: Path):
        """Test check with a valid skill structure."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        skill_dir = skills_dir / "valid_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""
---
name: valid_skill
version: 1.0.0
description: A valid skill
---
""")

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "check", "valid_skill"])

        assert result.exit_code == 0
        assert "Valid" in result.output or "valid_skill" in result.output

    def test_check_missing_skill(self, runner, tmp_path: Path):
        """Test check with non-existent skill."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "check", "nonexistent"])

        assert (
            "not found" in result.output.lower()
            or "Invalid" in result.output
            or result.exit_code == 0
        )

    def test_check_all_skills(self, runner, tmp_path: Path):
        """Test check with all skills."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        for skill_name in ["skill1", "skill2"]:
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"""
---
name: {skill_name}
version: 1.0.0
description: A skill
---
""")

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "check"])

        assert result.exit_code == 0
        assert "Skill Structure Check" in result.output


class TestSkillInstallDeprecated:
    """Tests for deprecated 'omni skill install' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_install_shows_deprecated(self, runner):
        """Test that install command shows deprecation message."""
        result = runner.invoke(app, ["skill", "install", "https://github.com/example/skill"])

        assert result.exit_code == 0
        assert "Deprecated" in result.output or "deprecated" in result.output.lower()


class TestSkillUpdateDeprecated:
    """Tests for deprecated 'omni skill update' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_update_shows_deprecated(self, runner):
        """Test that update command shows deprecation message."""
        result = runner.invoke(app, ["skill", "update", "some_skill"])

        assert result.exit_code == 0
        assert "Deprecated" in result.output or "deprecated" in result.output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
