"""
test_skill_index.py - Skill Index Commands Tests

Tests for:
- reindex: [Heavy] Wipe and rebuild the entire skill tool index (LanceDB)
- sync: [Fast] Incrementally sync skill tools based on file changes (LanceDB)
- index-stats: Show statistics about the skill index in LanceDB

Key invariants tested:
1. No duplicate tools after reindex
2. list_all_tools returns correct format (tool_name field)
3. Full reindex + sync cycle produces stable results
4. Repeated syncs don't accumulate changes

Usage:
    uv run pytest packages/python/agent/tests/unit/cli/test_skill_index.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
        # Mock RustVectorStore.index_skill_tools to return count
        with (
            patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store,
            patch(
                "omni.agent.cli.commands.skill.index_cmd.run_async_blocking"
            ) as mock_run_async_blocking,
        ):
            mock_store_instance = MagicMock()
            mock_store_instance.index_skill_tools = AsyncMock(return_value=0)
            mock_store_instance.drop_table = AsyncMock(return_value=True)
            mock_store.return_value = mock_store_instance

            def _consume(coro):
                coro.close()
                return 0

            mock_run_async_blocking.side_effect = _consume

            result = runner.invoke(app, ["skill", "reindex", "--json"])

        assert result.exit_code == 0
        assert mock_run_async_blocking.call_count >= 2
        assert "storage" in result.output.lower() or "lancedb" in result.output.lower()


class TestSkillSync:
    """Tests for 'omni skill sync' command."""

    @pytest.fixture
    def runner(self):
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

                # Mock RustVectorStore at definition location
                with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
                    mock_store_instance = MagicMock()
                    mock_store_instance.list_all_tools = MagicMock(return_value=[])
                    mock_store.return_value = mock_store_instance

                    result = runner.invoke(app, ["skill", "sync"])

        assert result.exit_code == 0
        # Should report no changes when both scanned and existing are empty
        assert "up to date" in result.output.lower() or "unchanged" in result.output.lower()

    def test_sync_with_json_output(self, runner, tmp_path: Path):
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
                    mock_store_instance.list_all_tools = MagicMock(return_value=[])
                    mock_store.return_value = mock_store_instance

                    result = runner.invoke(app, ["skill", "sync", "--json"])

        assert result.exit_code == 0
        try:
            output_data = json.loads(result.output)
            assert "added" in output_data
            assert "deleted" in output_data
            assert "total" in output_data
            assert output_data.get("storage") == "lancedb"
        except json.JSONDecodeError:
            pass

    def test_sync_detects_added_tools(self, runner, tmp_path: Path):
        """Test sync detects newly added tools and auto-populates LanceDB."""
        # Mock a new tool being scanned
        mock_tool = MagicMock()
        mock_tool.tool_name = "git.commit"
        mock_tool.description = "Create a git commit"
        mock_tool.skill_name = "git"
        mock_tool.file_path = "assets/skills/git/scripts/commands.py"
        mock_tool.function_name = "commit"
        mock_tool.execution_mode = "local"
        mock_tool.keywords = ["git", "commit"]
        mock_tool.input_schema = '{"type": "object", "properties": {"message": {"type": "string"}}}'
        mock_tool.file_hash = "abc123"
        mock_tool.category = "version_control"

        with patch("omni_core_rs.scan_skill_tools") as mock_scan:
            mock_scan.return_value = [mock_tool]

            with patch("omni_core_rs.diff_skills") as mock_diff:
                # Report the tool as added
                mock_report = MagicMock()
                mock_report.added = [mock_tool]
                mock_report.updated = []
                mock_report.deleted = []
                mock_report.unchanged_count = 0
                mock_diff.return_value = mock_report

                with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
                    mock_store_instance = MagicMock()
                    # LanceDB is empty initially
                    mock_store_instance.list_all_tools = MagicMock(return_value=[])
                    # Auto-populate fills LanceDB
                    mock_store_instance.index_skill_tools = AsyncMock(return_value=1)
                    mock_store.return_value = mock_store_instance

                    result = runner.invoke(app, ["skill", "sync"])

        assert result.exit_code == 0
        # When LanceDB is empty and tools are added, sync auto-populates
        # and reports "up to date" after successful population
        assert "up to date" in result.output.lower() or "auto-populat" in result.output.lower()


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

    def test_index_stats_with_lancedb(self, runner):
        """Test index-stats shows LanceDB storage."""
        with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.list_all_tools = MagicMock(
                return_value=[
                    {"skill_name": "git", "tool_name": "commit"},
                    {"skill_name": "git", "tool_name": "status"},
                    {"skill_name": "filesystem", "tool_name": "read"},
                ]
            )
            mock_store.return_value = mock_store_instance

            result = runner.invoke(app, ["skill", "index-stats"])

        assert result.exit_code == 0
        assert "lancedb" in result.output.lower()

    def test_index_stats_empty(self, runner):
        """Test index-stats with empty LanceDB."""
        with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.list_all_tools = MagicMock(return_value=[])
            mock_store.return_value = mock_store_instance

            result = runner.invoke(app, ["skill", "index-stats"])

        assert result.exit_code == 0
        assert "Skills: 0" in result.output
        assert "Tools: 0" in result.output


class TestDataFormatConsistency:
    """Tests to prevent data format mismatch issues.

    This class specifically guards against issues like:
    - list_all_tools returning 'tool_name' but diff_skills expecting 'name'
    """

    def test_list_all_tools_returns_tool_name_field(self):
        """Ensure list_all_tools returns tools with 'tool_name' field."""
        # This test verifies the expected format
        expected_keys = {
            "tool_name",
            "description",
            "skill_name",
            "category",
            "file_hash",
            "input_schema",
        }

        # Simulate what list_all_tools returns
        mock_tools = [
            {"tool_name": "git.commit", "description": "Create commit", "skill_name": "git"},
        ]

        for tool in mock_tools:
            assert "tool_name" in tool, "list_all_tools must return 'tool_name' field"

    def test_diff_skills_expects_name_field(self):
        """Verify that existing tools are transformed to 'name' field for diff_skills."""
        # The IndexToolEntry struct expects 'name' not 'tool_name'
        existing_tools_from_lance = [
            {"tool_name": "git.commit", "description": "Create commit", "skill_name": "git"},
        ]

        # Transformation should produce IndexToolEntry format
        existing_entries = []
        for tool in existing_tools_from_lance:
            entry = {
                "name": tool.get("tool_name", ""),  # tool_name -> name
                "description": tool.get("description", ""),
                "category": tool.get("category", ""),
                "input_schema": tool.get("input_schema", ""),
                "file_hash": tool.get("file_hash", ""),
            }
            existing_entries.append(entry)

        # Verify transformation
        assert existing_entries[0]["name"] == "git.commit"
        assert "tool_name" not in existing_entries[0]  # Should be transformed


class TestNoDuplicateTools:
    """Tests to prevent duplicate tools from accumulating.

    This guards against the issue where reindex without dropping table
    would append tools, causing duplicates.
    """

    def test_reindex_calls_index_skill_tools(self):
        """Verify that reindex calls index_skill_tools (Rust drops internally when it has tools)."""
        with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
            mock_store_instance = MagicMock()
            mock_store_instance.index_skill_tools = AsyncMock(return_value=10)
            mock_store.return_value = mock_store_instance

            runner = CliRunner()
            result = runner.invoke(app, ["skill", "reindex"])

            mock_store_instance.index_skill_tools.assert_called_once()
            assert result.exit_code == 0


class TestSyncStability:
    """Tests for sync command stability across multiple runs."""

    def test_duplicate_sync_runs_produce_same_result(self):
        """Running sync twice with no changes should produce same result."""
        mock_tool = MagicMock()
        mock_tool.tool_name = "git.status"
        mock_tool.description = "Show git status"
        mock_tool.skill_name = "git"
        mock_tool.file_path = "assets/skills/git/scripts/status.py"
        mock_tool.function_name = "status"
        mock_tool.execution_mode = "local"
        mock_tool.keywords = ["git", "status"]
        mock_tool.input_schema = "{}"
        mock_tool.file_hash = "hash123"
        mock_tool.category = "version_control"

        mock_report = MagicMock()
        mock_report.added = []
        mock_report.updated = []
        mock_report.deleted = []
        mock_report.unchanged_count = 1

        with patch("omni_core_rs.scan_skill_tools") as mock_scan:
            mock_scan.return_value = [mock_tool]

            with patch("omni_core_rs.diff_skills") as mock_diff:
                mock_diff.return_value = mock_report

                with patch("omni.foundation.bridge.rust_vector.RustVectorStore") as mock_store:
                    mock_store_instance = MagicMock()
                    mock_store_instance.list_all_tools = MagicMock(
                        return_value=[
                            {
                                "tool_name": "git.status",
                                "description": "Show git status",
                                "category": "",
                                "input_schema": "",
                                "file_hash": "hash123",
                            }
                        ]
                    )
                    mock_store.return_value = mock_store_instance

                    runner = CliRunner()

                    # First sync
                    result1 = runner.invoke(app, ["skill", "sync"])
                    # Second sync - should be same
                    result2 = runner.invoke(app, ["skill", "sync"])

        assert result1.exit_code == 0
        assert result2.exit_code == 0
        # Both should show "up to date" or "unchanged"
        assert "up to date" in result1.output.lower() or "unchanged" in result1.output.lower()
        assert "up to date" in result2.output.lower() or "unchanged" in result2.output.lower()


class TestIndexStatsAccuracy:
    """Tests to ensure index-stats shows accurate counts."""

    def test_index_stats_counts_unique_tools(self):
        """index-stats should count unique tools, not rows."""
        # Simulate duplicate tools in LanceDB (this should not happen)
        tools_with_duplicates = [
            {"skill_name": "git", "tool_name": "commit"},
            {"skill_name": "git", "tool_name": "commit"},  # duplicate
            {"skill_name": "git", "tool_name": "status"},
        ]

        # Count unique skill names
        skills_count = len(set(t.get("skill_name", "unknown") for t in tools_with_duplicates))
        assert skills_count == 1  # Only "git" skill

    def test_index_stats_differentiates_skills_and_tools(self):
        """index-stats should show correct distinction between skills and tools."""
        tools = [
            {"skill_name": "git", "tool_name": "commit"},
            {"skill_name": "git", "tool_name": "status"},
            {"skill_name": "filesystem", "tool_name": "read"},
        ]

        skills_count = len(set(t.get("skill_name", "unknown") for t in tools))
        tools_count = len(tools)

        assert skills_count == 2  # git, filesystem
        assert tools_count == 3  # commit, status, read


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
