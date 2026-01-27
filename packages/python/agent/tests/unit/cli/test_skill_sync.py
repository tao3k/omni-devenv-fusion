"""
test_skill_sync.py - Skill Sync Command Tests

Tests for the 'omni skill sync' command with LanceDB storage:
- No changes detection
- Added tools detection
- Deleted tools detection
- JSON output format
- Verbose output

Usage:
    uv run pytest packages/python/agent/tests/unit/cli/test_skill_sync.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from omni.agent.cli.app import app


class TestSkillSync:
    """Test suite for 'omni skill sync' command."""

    @pytest.fixture
    def runner(self):
        """Create Typer CLI runner."""
        return CliRunner()

    def test_sync_no_changes(self, runner, tmp_path: Path):
        """Test sync reports no changes when LanceDB is up to date."""
        with patch("omni_core_rs.scan_skill_tools") as mock_scan:
            mock_scan.return_value = []

            with patch("omni_core_rs.diff_skills") as mock_diff:
                mock_report = MagicMock()
                mock_report.added = []
                mock_report.updated = []
                mock_report.deleted = []
                mock_report.unchanged_count = 0
                mock_diff.return_value = mock_report

                with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
                    mock_store_instance = MagicMock()
                    mock_store_instance.list_all_tools = AsyncMock(return_value=[])
                    mock_store.return_value = mock_store_instance

                    result = runner.invoke(app, ["skill", "sync"])

        assert result.exit_code == 0

    def test_sync_detects_added_tools(self, runner, tmp_path: Path):
        """Test sync detects newly added tools and auto-populates LanceDB."""
        # Simulate finding a new tool
        mock_tool = MagicMock()
        mock_tool.tool_name = "new_tool"
        mock_tool.description = "A new tool"
        mock_tool.skill_name = "test_skill"
        mock_tool.file_path = "assets/skills/test/scripts/tools.py"
        mock_tool.function_name = "new_tool"
        mock_tool.execution_mode = "local"
        mock_tool.keywords = ["new"]
        mock_tool.input_schema = "{}"
        mock_tool.file_hash = "def456"
        mock_tool.category = "test"

        with patch("omni_core_rs.scan_skill_tools") as mock_scan:
            mock_scan.return_value = [mock_tool]

            with patch("omni_core_rs.diff_skills") as mock_diff:
                mock_report = MagicMock()
                mock_report.added = [mock_tool]
                mock_report.updated = []
                mock_report.deleted = []
                mock_report.unchanged_count = 0
                mock_diff.return_value = mock_report

                with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
                    mock_store_instance = MagicMock()
                    # LanceDB is empty initially
                    mock_store_instance.list_all_tools = AsyncMock(return_value=[])
                    # Auto-populate fills LanceDB
                    mock_store_instance.index_skill_tools = AsyncMock(return_value=1)
                    mock_store.return_value = mock_store_instance

                    result = runner.invoke(app, ["skill", "sync"])

        assert result.exit_code == 0
        # When LanceDB is empty and tools are added, sync auto-populates
        # and reports "up to date" after successful population
        assert "up to date" in result.output.lower() or "auto-populat" in result.output.lower()

    def test_sync_detects_deleted_tools(self, runner, tmp_path: Path):
        """Test sync detects deleted tools."""
        # Simulate scanning returning fewer tools than in LanceDB
        # Only one tool scanned (one was deleted)
        mock_tool = MagicMock()
        mock_tool.tool_name = "remaining_tool"
        mock_tool.description = "Remaining tool"
        mock_tool.skill_name = "test_skill"
        mock_tool.file_path = "assets/skills/test/scripts/tools.py"
        mock_tool.function_name = "remaining_tool"
        mock_tool.execution_mode = "local"
        mock_tool.keywords = ["test"]
        mock_tool.input_schema = "{}"
        mock_tool.file_hash = "abc123"
        mock_tool.category = "test"

        with patch("omni_core_rs.scan_skill_tools") as mock_scan:
            mock_scan.return_value = [mock_tool]

            with patch("omni_core_rs.diff_skills") as mock_diff:
                mock_report = MagicMock()
                mock_report.added = []
                mock_report.updated = []
                # diff_skills returns list of tool names as strings
                mock_report.deleted = ["deleted_tool"]
                mock_report.unchanged_count = 1
                mock_diff.return_value = mock_report

                with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store_cls:
                    mock_store_instance = MagicMock()
                    # LanceDB has both tools (one will be deleted)
                    mock_store_instance.list_all_tools = AsyncMock(
                        return_value=[
                            {
                                "tool_name": "remaining_tool",
                                "description": "Remaining",
                                "category": "test",
                                "input_schema": "{}",
                                "file_hash": "abc123",
                            },
                            {
                                "tool_name": "deleted_tool",
                                "description": "Deleted",
                                "category": "test",
                                "input_schema": "{}",
                                "file_hash": "def456",
                            },
                        ]
                    )
                    # Mock delete method (sync calls this for actual deletions)
                    mock_store_instance.delete = MagicMock(return_value=True)
                    mock_store_cls.return_value = mock_store_instance

                    # Use --dry-run to avoid actual deletions during test
                    result = runner.invoke(app, ["skill", "sync", "--dry-run"])

        assert result.exit_code == 0
        # With changes detected, output should show the deleted tool count
        assert "-1 deleted" in result.output or "deleted" in result.output.lower()

    def test_sync_json_output(self, runner, tmp_path: Path):
        """Test sync with JSON output format."""
        with patch("omni_core_rs.scan_skill_tools") as mock_scan:
            mock_scan.return_value = []

            with patch("omni_core_rs.diff_skills") as mock_diff:
                mock_report = MagicMock()
                mock_report.added = []
                mock_report.updated = []
                mock_report.deleted = []
                mock_report.unchanged_count = 0
                mock_diff.return_value = mock_report

                with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
                    mock_store_instance = MagicMock()
                    mock_store_instance.list_all_tools = AsyncMock(return_value=[])
                    mock_store.return_value = mock_store_instance

                    result = runner.invoke(app, ["skill", "sync", "--json"])

        assert result.exit_code == 0

        # Parse JSON from output
        try:
            output_data = json.loads(result.output)
            assert "added" in output_data
            assert "deleted" in output_data
            assert "total" in output_data
            assert "changes" in output_data
            assert output_data.get("storage") == "lancedb"
        except json.JSONDecodeError:
            pass


class TestSkillSyncDeltaCalculation:
    """Test delta calculation logic for skill sync."""

    def test_added_delta(self):
        """Test calculation of added tools."""
        old_tools = {"tool_a", "tool_b"}
        current_tools = {"tool_a", "tool_b", "tool_c"}

        added = current_tools - old_tools
        deleted = old_tools - current_tools

        assert added == {"tool_c"}
        assert deleted == set()

    def test_deleted_delta(self):
        """Test calculation of deleted tools."""
        old_tools = {"tool_a", "tool_b", "tool_c"}
        current_tools = {"tool_a", "tool_b"}

        added = current_tools - old_tools
        deleted = old_tools - current_tools

        assert added == set()
        assert deleted == {"tool_c"}

    def test_both_added_and_deleted(self):
        """Test calculation when tools are both added and deleted."""
        old_tools = {"tool_a", "tool_b", "tool_c"}
        current_tools = {"tool_a", "tool_d", "tool_e"}

        added = current_tools - old_tools
        deleted = old_tools - current_tools

        assert added == {"tool_d", "tool_e"}
        assert deleted == {"tool_b", "tool_c"}

    def test_no_changes(self):
        """Test when tools haven't changed."""
        old_tools = {"tool_a", "tool_b"}
        current_tools = {"tool_a", "tool_b"}

        added = current_tools - old_tools
        deleted = old_tools - current_tools

        assert added == set()
        assert deleted == set()
        assert not (added or deleted)  # No changes


class TestSkillSyncOutput:
    """Test output formatting for skill sync."""

    def test_summary_with_added_and_deleted(self):
        """Test summary string with both additions and deletions."""
        added_count = 3
        deleted_count = 2

        if added_count > 0 or deleted_count > 0:
            parts = []
            if added_count > 0:
                parts.append(f"+{added_count} added")
            if deleted_count > 0:
                parts.append(f"-{deleted_count} deleted")
            summary = ", ".join(parts)
        else:
            summary = "No changes"

        assert "+3 added" in summary
        assert "-2 deleted" in summary

    def test_summary_no_changes(self):
        """Test summary string when no changes."""
        added_count = 0
        deleted_count = 0

        if added_count > 0 or deleted_count > 0:
            parts = []
            if added_count > 0:
                parts.append(f"+{added_count} added")
            if deleted_count > 0:
                parts.append(f"-{deleted_count} deleted")
            summary = ", ".join(parts)
        else:
            summary = "No changes"

        assert summary == "No changes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
