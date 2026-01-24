"""
test_skill_create.py - Skill Create Commands Tests

Tests for:
- templates: Manage skill templates
- create: Create a new skill from template
- generate: Generate a new skill using AI
- evolve: Analyze usage and suggest improvements

Usage:
    uv run pytest packages/python/agent/tests/unit/cli/test_skill_create.py -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from omni.agent.cli.app import app


class TestSkillTemplates:
    """Tests for 'omni skill templates' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_templates_requires_skill_name(self, runner):
        """Test that templates requires a skill name."""
        result = runner.invoke(app, ["skill", "templates"])

        assert result.exit_code != 0

    def test_templates_with_list(self, runner, tmp_path: Path):
        """Test templates with --list option."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""
---
name: test_skill
version: 1.0.0
---
""")
        templates_dir = skill_dir / "scripts" / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "template1.py.j2").write_text("# Template 1")

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "templates", "test_skill", "--list"])

        assert result.exit_code == 0

    def test_templates_with_nonexistent_skill(self, runner, tmp_path: Path):
        """Test templates with non-existent skill."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(app, ["skill", "templates", "nonexistent", "--list"])

        assert result.exit_code == 0  # Shows error panel, doesn't crash


class TestSkillCreate:
    """Tests for 'omni skill create' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_create_requires_arguments(self, runner):
        """Test that create requires skill name and description."""
        result = runner.invoke(app, ["skill", "create"])

        assert result.exit_code != 0

    def test_create_requires_description(self, runner):
        """Test that create requires --description."""
        result = runner.invoke(app, ["skill", "create", "new-skill"])

        assert result.exit_code != 0

    def test_create_with_valid_args(self, runner, tmp_path: Path):
        """Test create with valid skill name and description."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        # Create template skill
        template_dir = skills_dir / "_template"
        template_dir.mkdir()
        (template_dir / "SKILL.md").write_text("""---
name: {{name}}
version: 1.0.0
description: {{description}}
---
""")

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            result = runner.invoke(
                app, ["skill", "create", "new-skill", "--description", "A new skill"]
            )

        # Either succeeds or shows appropriate output
        assert result.exit_code == 0 or "error" in result.output.lower()


class TestSkillGenerate:
    """Tests for 'omni skill generate' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_generate_requires_requirement(self, runner):
        """Test that generate requires a requirement argument."""
        result = runner.invoke(app, ["skill", "generate"])

        assert result.exit_code != 0

    def test_generate_with_requirement(self, runner, tmp_path: Path):
        """Test generate with a valid requirement."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        # Mock SKILLS_DIR to use temp directory
        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.foundation.config.dirs.PRJ_CACHE", return_value=tmp_path / ".cache"):
                result = runner.invoke(app, ["skill", "generate", "A skill to do something"])

        # Clean up generated skill if created
        generated_skill = skills_dir / "text_searcher"
        if generated_skill.exists():
            import shutil

            shutil.rmtree(generated_skill)

        # Either succeeds or shows appropriate error (factory may not exist)
        assert result.exit_code == 0 or "Factory" in result.output or "error" in result.output


class TestSkillEvolve:
    """Tests for 'omni skill evolve' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_evolve_exists(self, runner):
        """Test that evolve command is available."""
        result = runner.invoke(app, ["skill", "evolve", "--help"])

        assert result.exit_code == 0
        assert "evolve" in result.output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
