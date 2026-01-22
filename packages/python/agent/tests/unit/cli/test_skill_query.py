"""
test_skill_query.py - Skill Query Commands Tests

Tests for:
- list: List installed and loaded skills
- info: Show information about a skill
- discover: Discover skills from remote index [DEPRECATED]
- search: Search skills [DEPRECATED]

Usage:
    uv run pytest packages/python/agent/tests/unit/cli/test_skill_query.py -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from omni.agent.cli.app import app


class TestSkillList:
    """Tests for 'omni skill list' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_list_shows_skills(self, runner, tmp_path: Path):
        """Test that list command shows installed skills."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""
---
name: test_skill
version: 1.0.0
description: A test skill
---
""")

        mock_ctx = MagicMock()
        mock_ctx.list_skills.return_value = ["test_skill"]
        mock_ctx.get_skill.return_value = MagicMock(list_commands=lambda: ["cmd1", "cmd2"])

        mock_kernel = MagicMock()
        mock_kernel.skill_context = mock_ctx

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.core.kernel.get_kernel", return_value=mock_kernel):
                result = runner.invoke(app, ["skill", "list"])

        assert result.exit_code == 0
        assert "test_skill" in result.output

    def test_list_handles_empty_skills_dir(self, runner, tmp_path: Path):
        """Test list with no skills installed."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        mock_ctx = MagicMock()
        mock_ctx.list_skills.return_value = []

        mock_kernel = MagicMock()
        mock_kernel.skill_context = mock_ctx

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.core.kernel.get_kernel", return_value=mock_kernel):
                result = runner.invoke(app, ["skill", "list"])

        assert result.exit_code == 0


class TestSkillInfo:
    """Tests for 'omni skill info' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_info_shows_skill_details(self, runner, tmp_path: Path):
        """Test that info command shows skill details."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test_skill
version: 1.0.0
description: A test skill
authors: ["Test Author"]
routing_keywords: ["test", "example"]
---
This is a test skill.
""")

        mock_ctx = MagicMock()
        mock_ctx.get_skill.return_value = MagicMock(list_commands=lambda: ["cmd1"])

        mock_kernel = MagicMock()
        mock_kernel.skill_context = mock_ctx

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.core.kernel.get_kernel", return_value=mock_kernel):
                result = runner.invoke(app, ["skill", "info", "test_skill"])

        assert result.exit_code == 0
        assert "test_skill" in result.output

    def test_info_handles_missing_skill(self, runner, tmp_path: Path):
        """Test info with non-existent skill."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "info", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestSkillDiscoverDeprecated:
    """Tests for deprecated 'omni skill discover' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_discover_shows_deprecated(self, runner):
        """Test that discover command shows deprecation message."""
        result = runner.invoke(app, ["skill", "discover", "test"])

        assert result.exit_code == 0
        assert "Deprecated" in result.output or "deprecated" in result.output.lower()


class TestSkillSearchDeprecated:
    """Tests for deprecated 'omni skill search' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_search_shows_deprecated(self, runner):
        """Test that search command shows deprecation message."""
        result = runner.invoke(app, ["skill", "search", "test"])

        assert result.exit_code == 0
        assert "Deprecated" in result.output or "deprecated" in result.output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
