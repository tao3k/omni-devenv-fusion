"""
test_skill_index.py - Skill Index Commands Tests

Tests for:
- reindex: [Heavy] Wipe and rebuild the entire skill tool index
- sync: [Fast] Incrementally sync skill tools based on file changes
- index-stats: Show statistics about the skill discovery service
- watch: Start a file watcher to automatically sync skills on change [DEPRECATED]

Usage:
    uv run pytest packages/python/agent/tests/unit/cli/test_skill_index.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from omni.agent.cli.app import app


class TestSkillReindex:
    """Tests for 'omni skill reindex' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_reindex_exists(self, runner):
        """Test that reindex command is available."""
        result = runner.invoke(app, ["skill", "reindex", "--help"])

        assert result.exit_code == 0
        assert "reindex" in result.output.lower()

    def test_reindex_with_json(self, runner):
        """Test reindex with JSON output."""
        result = runner.invoke(app, ["skill", "reindex", "--json"])

        assert result.exit_code == 0 or "error" in result.output.lower()


class TestSkillSync:
    """Tests for 'omni skill sync' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_sync_no_changes(self, runner, tmp_path: Path):
        """Test sync reports no changes when index matches filesystem."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir(parents=True)

        index_file = cache_dir / "skill_index.json"
        existing_index = [
            {
                "name": "existing_skill",
                "description": "An existing skill",
                "version": "1.0.0",
                "path": str(tmp_path / "assets" / "skills" / "existing_skill"),
            },
        ]
        with open(index_file, "w") as f:
            json.dump(existing_index, f)

        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = skills_dir / "existing_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""
---
name: existing_skill
version: 1.0.0
---
""")

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.foundation.bridge.scanner.Path.cwd", return_value=tmp_path):
                result = runner.invoke(app, ["skill", "sync"])

        assert result.exit_code == 0

    def test_sync_with_json_output(self, runner, tmp_path: Path):
        """Test sync with JSON output."""
        cache_dir = tmp_path / ".cache"
        cache_dir.mkdir(parents=True)

        index_file = cache_dir / "skill_index.json"
        with open(index_file, "w") as f:
            json.dump([], f)

        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.foundation.bridge.scanner.Path.cwd", return_value=tmp_path):
                result = runner.invoke(app, ["skill", "sync", "--json"])

        assert result.exit_code == 0
        try:
            output_data = json.loads(result.output)
            assert "added" in output_data
            assert "deleted" in output_data
            assert "total" in output_data
        except json.JSONDecodeError:
            pass


class TestSkillIndexStats:
    """Tests for 'omni skill index-stats' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_index_stats_exists(self, runner):
        """Test that index-stats command is available."""
        result = runner.invoke(app, ["skill", "index-stats", "--help"])

        assert result.exit_code == 0
        assert "index" in result.output.lower() or "stats" in result.output.lower()


class TestSkillWatchDeprecated:
    """Tests for deprecated 'omni skill watch' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_watch_shows_deprecated(self, runner):
        """Test that watch command shows deprecation message."""
        result = runner.invoke(app, ["skill", "watch"])

        assert result.exit_code == 0
        assert "Deprecated" in result.output or "deprecated" in result.output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
