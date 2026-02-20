"""
test_skill_query.py - Skill Query Commands Tests

Tests for:
- list: List installed and loaded skills
- list --json: Output all skills info as JSON (from Rust DB)
- info: Show information about a skill
- discover: Discover skills from remote index [DEPRECATED]
- search: Search skills [DEPRECATED]

Usage:
    uv run pytest packages/python/agent/tests/unit/cli/test_skill_query.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from omni.agent.cli.app import app


class TestSkillList:
    """Tests for 'omni skill list' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_list_shows_skills(self, runner, tmp_path: Path):
        """Test that list command shows installed skills (light path: LanceDB list_all_tools)."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        mock_tools = [
            {"skill_name": "test_skill", "tool_name": "cmd1", "description": "Command 1"},
            {"skill_name": "test_skill", "tool_name": "cmd2", "description": "Command 2"},
        ]

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store_cls:
                mock_store = MagicMock()
                mock_store.list_all_tools.return_value = mock_tools
                mock_store_cls.return_value = mock_store
                result = runner.invoke(app, ["skill", "list"])

        assert result.exit_code == 0
        assert "test_skill" in result.output

    def test_list_handles_empty_skills_dir(self, runner, tmp_path: Path):
        """Test list with no skills installed (light path: LanceDB list_all_tools)."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store_cls:
                mock_store = MagicMock()
                mock_store.list_all_tools.return_value = []
                mock_store_cls.return_value = mock_store
                result = runner.invoke(app, ["skill", "list"])

        assert result.exit_code == 0

    def test_list_json_output(self, runner, tmp_path: Path):
        """Test list --json outputs skills from LanceDB as JSON (grouped by skill_name)."""
        mock_tools = [
            {
                "skill_name": "filesystem",
                "tool_name": "read",
                "description": "Read file",
                "category": "read",
            },
            {
                "skill_name": "git",
                "tool_name": "status",
                "description": "Show working tree status",
                "category": "query",
            },
            {
                "skill_name": "git",
                "tool_name": "commit",
                "description": "Commit changes",
                "category": "write",
            },
        ]

        with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.list_all_tools.return_value = mock_tools
            mock_store.return_value = mock_store_instance
            with patch(
                "omni.foundation.config.skills.SKILLS_DIR",
                return_value=tmp_path / "assets" / "skills",
            ):
                result = runner.invoke(app, ["skill", "list", "--json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 2  # filesystem, git

        # Verify skill order (sorted by name: filesystem, git)
        assert output_data[0]["name"] == "filesystem"
        assert output_data[1]["name"] == "git"
        assert len(output_data[0]["tools"]) == 1
        assert len(output_data[1]["tools"]) == 2
        assert output_data[1]["tools"][1]["name"] == "git.commit"
        assert output_data[1]["tools"][1]["category"] == "write"

    def test_list_json_empty_skills(self, runner, tmp_path: Path):
        """Test list --json with no skills in LanceDB."""
        with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.list_all_tools.return_value = []
            mock_store.return_value = mock_store_instance
            with patch(
                "omni.foundation.config.skills.SKILLS_DIR",
                return_value=tmp_path / "assets" / "skills",
            ):
                result = runner.invoke(app, ["skill", "list", "--json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 0

    def test_list_json_preserves_tool_metadata(self, runner, tmp_path: Path):
        """Test that --json preserves name, description, category from list_all_tools."""
        mock_tools = [
            {
                "skill_name": "test_skill",
                "tool_name": "run",
                "description": "Run tests",
                "category": "test",
            },
            {
                "skill_name": "test_skill",
                "tool_name": "verify",
                "description": "Verify code",
                "category": "check",
            },
        ]

        with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.list_all_tools.return_value = mock_tools
            mock_store.return_value = mock_store_instance
            with patch(
                "omni.foundation.config.skills.SKILLS_DIR",
                return_value=tmp_path / "assets" / "skills",
            ):
                result = runner.invoke(app, ["skill", "list", "--json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        skill_data = output_data[0]
        assert skill_data["name"] == "test_skill"
        assert len(skill_data["tools"]) == 2
        assert skill_data["tools"][0]["name"] == "test_skill.run"
        assert skill_data["tools"][0]["category"] == "test"
        assert skill_data["tools"][1]["name"] == "test_skill.verify"
        assert skill_data["tools"][1]["category"] == "check"

    def test_list_filters_invalid_and_private_records(self, runner, tmp_path: Path):
        """List should only show valid public commands from normalized command index rows."""
        mock_tools = [
            {
                "skill_name": "knowledge",
                "tool_name": "knowledge.recall",
                "description": "Recall docs",
                "category": "search",
            },
            {
                "skill_name": "_template",
                "tool_name": "_template.example",
                "description": "Template helper",
                "category": "internal",
            },
            {
                "skill_name": "/Users/guangtao/ghq/github",
                "tool_name": "/Users/guangtao/ghq/github.com/acme/skill.py:_helper",
                "description": "Invalid path-like entry",
                "category": "internal",
            },
            {
                "skill_name": "knowledge",
                "tool_name": "knowledge",
                "description": "Skill node (not a command)",
                "category": "internal",
            },
        ]

        with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.list_all_tools.return_value = mock_tools
            mock_store.return_value = mock_store_instance
            with patch(
                "omni.foundation.config.skills.SKILLS_DIR",
                return_value=tmp_path / "assets" / "skills",
            ):
                result = runner.invoke(app, ["skill", "list"])

        assert result.exit_code == 0
        assert "knowledge" in result.output
        assert "recall" in result.output
        assert "_template" not in result.output
        assert "/Users/guangtao" not in result.output


class TestSkillInfo:
    """Tests for 'omni skill info' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_info_shows_skill_details(self, runner, tmp_path: Path):
        """Test that info command shows skill details (commands from list_all_tools)."""
        skills_dir = tmp_path / "assets" / "skills"
        skills_dir.mkdir(parents=True)

        skill_dir = skills_dir / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test_skill
description: A test skill
metadata:
  version: "1.0.0"
  authors: ["Test Author"]
  routing_keywords:
    - "test"
    - "example"
---
This is a test skill.
""")

        mock_tools = [{"skill_name": "test_skill", "tool_name": "cmd1", "description": "Command 1"}]
        with patch("omni.foundation.config.skills.SKILLS_DIR", return_value=skills_dir):
            with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store_cls:
                mock_store = MagicMock()
                mock_store.list_all_tools.return_value = mock_tools
                mock_store_cls.return_value = mock_store
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


class TestSkillDiscoverUnavailable:
    """Tests for 'omni skill discover' availability messaging."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_discover_shows_unavailable(self, runner):
        """Test that discover command shows unavailable message."""
        result = runner.invoke(app, ["skill", "discover", "test"])

        assert result.exit_code == 0
        assert "Unavailable" in result.output or "not available" in result.output.lower()


class TestSkillSearchUnavailable:
    """Tests for 'omni skill search' availability messaging."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_search_shows_unavailable(self, runner):
        """Test that search command shows unavailable message."""
        result = runner.invoke(app, ["skill", "search", "test"])

        assert result.exit_code == 0
        assert "Unavailable" in result.output or "not available" in result.output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
