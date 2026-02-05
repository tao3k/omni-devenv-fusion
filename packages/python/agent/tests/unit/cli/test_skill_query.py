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

    def test_list_json_output(self, runner, tmp_path: Path):
        """Test list --json outputs skills from Rust DB as JSON with full metadata."""
        # Create mock skill index data (what get_skill_index returns)
        mock_skills = [
            {
                "name": "git",
                "path": "assets/skills/git",
                "description": "Git operations",
                "version": "1.0.0",
                "repository": "https://github.com/example/git-skill",
                "routing_keywords": ["git", "version control"],
                "intents": ["commit changes", "check status"],
                "authors": ["omni-dev-fusion"],
                "permissions": ["filesystem:*", "terminal:run_command"],
                "require_refs": [{"path": "docs/git-guide.md"}],
                "oss_compliant": ["apache-2.0"],
                "compliance_details": ["License verified"],
                "sniffing_rules": [{"type": "file_match", "pattern": "**/.git/**"}],
                "docs_available": {"skill_md": True, "readme": True, "tests": False},
                "tools": [
                    {
                        "name": "git.status",
                        "description": "Show working tree status",
                        "category": "query",
                        "input_schema": '{"type": "object", "properties": {}}',
                        "file_hash": "abc123",
                    },
                    {
                        "name": "git.commit",
                        "description": "Commit changes",
                        "category": "write",
                        "input_schema": '{"type": "object", "properties": {"message": {"type": "string"}},"required": ["message"]}',
                        "file_hash": "def456",
                    },
                ],
            },
            {
                "name": "filesystem",
                "path": "assets/skills/filesystem",
                "description": "File operations",
                "version": "1.0.0",
                "repository": "",
                "routing_keywords": ["file", "io"],
                "intents": ["read file", "write file"],
                "authors": ["omni-dev-fusion"],
                "permissions": ["filesystem:read"],
                "require_refs": [],
                "oss_compliant": [],
                "compliance_details": [],
                "sniffing_rules": [],
                "docs_available": {"skill_md": True, "readme": False, "tests": False},
                "tools": [
                    {
                        "name": "filesystem.read",
                        "description": "Read file",
                        "category": "read",
                        "input_schema": '{"type": "object", "properties": {"path": {"type": "string"}}}',
                        "file_hash": "ghi789",
                    },
                ],
            },
        ]

        with patch("asyncio.run", return_value=mock_skills):
            with patch(
                "omni.foundation.config.skills.SKILLS_DIR",
                return_value=tmp_path / "assets" / "skills",
            ):
                result = runner.invoke(app, ["skill", "list", "--json"])

        assert result.exit_code == 0
        # Parse JSON output
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 2

        # Verify skill 1 has full metadata
        assert output_data[0]["name"] == "git"
        assert output_data[0]["path"] == "assets/skills/git"
        assert output_data[0]["docs_path"] == "assets/skills/git/SKILL.md"
        assert output_data[0]["description"] == "Git operations"
        assert output_data[0]["version"] == "1.0.0"
        assert output_data[0]["repository"] == "https://github.com/example/git-skill"
        assert output_data[0]["routing_keywords"] == ["git", "version control"]
        assert output_data[0]["intents"] == ["commit changes", "check status"]
        assert output_data[0]["authors"] == ["omni-dev-fusion"]
        assert output_data[0]["permissions"] == ["filesystem:*", "terminal:run_command"]
        assert output_data[0]["require_refs"] == ["docs/git-guide.md"]
        assert output_data[0]["oss_compliant"] == ["apache-2.0"]
        assert output_data[0]["compliance_details"] == ["License verified"]
        assert output_data[0]["sniffing_rules"] == [{"type": "file_match", "pattern": "**/.git/**"}]
        assert output_data[0]["docs_available"]["skill_md"] is True
        assert output_data[0]["docs_available"]["readme"] is True
        assert output_data[0]["docs_available"]["tests"] is False
        assert output_data[0]["has_extensions"] is True
        assert len(output_data[0]["tools"]) == 2

        # Verify tool has all fields
        tool = output_data[0]["tools"][1]
        assert tool["name"] == "git.commit"
        assert tool["category"] == "write"
        assert "input_schema" in tool
        assert "message" in tool["input_schema"]
        assert tool["file_hash"] == "def456"

        # Verify skill 2
        assert output_data[1]["name"] == "filesystem"
        assert output_data[1]["permissions"] == ["filesystem:read"]
        assert output_data[1]["has_extensions"] is True

    def test_list_json_empty_skills(self, runner, tmp_path: Path):
        """Test list --json with no skills in Rust DB."""
        with patch("asyncio.run", return_value=[]):
            with patch(
                "omni.foundation.config.skills.SKILLS_DIR",
                return_value=tmp_path / "assets" / "skills",
            ):
                result = runner.invoke(app, ["skill", "list", "--json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 0

    def test_list_json_preserves_full_metadata(self, runner, tmp_path: Path):
        """Test that --json preserves all skill metadata from Rust scanner."""
        mock_skills = [
            {
                "name": "test_skill",
                "path": "assets/skills/test_skill",
                "description": "Test skill description",
                "version": "2.0.0",
                "routing_keywords": ["test", "example"],
                "intents": ["run tests", "verify code"],
                "authors": ["Test Author"],
                "permissions": ["network:http"],
                "tools": [
                    {"name": "test_skill.run", "description": "Run tests", "category": "test"},
                    {
                        "name": "test_skill.verify",
                        "description": "Verify code",
                        "category": "check",
                    },
                ],
            },
        ]

        with patch("asyncio.run", return_value=mock_skills):
            with patch(
                "omni.foundation.config.skills.SKILLS_DIR",
                return_value=tmp_path / "assets" / "skills",
            ):
                result = runner.invoke(app, ["skill", "list", "--json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        skill_data = output_data[0]

        assert skill_data["name"] == "test_skill"
        assert skill_data["path"] == "assets/skills/test_skill"
        assert skill_data["description"] == "Test skill description"
        assert skill_data["version"] == "2.0.0"
        assert skill_data["routing_keywords"] == ["test", "example"]
        assert skill_data["intents"] == ["run tests", "verify code"]
        assert skill_data["authors"] == ["Test Author"]
        assert skill_data["permissions"] == ["network:http"]
        assert skill_data["has_extensions"] is True
        assert len(skill_data["tools"]) == 2
        assert skill_data["tools"][0]["name"] == "test_skill.run"
        assert skill_data["tools"][0]["category"] == "test"


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
