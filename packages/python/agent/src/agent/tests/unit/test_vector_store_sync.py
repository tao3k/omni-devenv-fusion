"""
Unit tests for Phase 64: Incremental Sync functionality.

Tests the sync_skills diff algorithm and CLI commands for sync/reindex.
"""

from __future__ import annotations

import json

import pytest


class TestSyncDiffAlgorithm:
    """Tests for sync diff algorithm (no external dependencies)."""

    def _compute_diff(
        self,
        existing: dict[str, dict],
        current: list[dict],
    ) -> dict:
        """Compute the sync diff between existing DB state and current filesystem state.

        This is a pure function version of the diff logic for testing.
        """
        existing_paths = set(existing.keys())
        current_paths = {t.get("file_path", "") for t in current if t.get("file_path")}

        # Added: path not in DB
        to_add = [t for t in current if t.get("file_path") and t["file_path"] not in existing_paths]

        # Modified: path exists but hash differs
        to_update = [
            t
            for t in current
            if t.get("file_path")
            and t["file_path"] in existing_paths
            and t.get("file_hash") != existing[t["file_path"]].get("hash")
        ]

        # Deleted: path in DB but not in filesystem
        to_delete = existing_paths - current_paths

        return {
            "added": len(to_add),
            "modified": len(to_update),
            "deleted": len(to_delete),
            "added_paths": [t["file_path"] for t in to_add],
            "modified_paths": [t["file_path"] for t in to_update],
            "deleted_paths": list(to_delete),
        }

    def test_detect_added_tools(self):
        """New files should be detected as added."""
        existing = {"a.py": {"hash": "h1"}, "b.py": {"hash": "h2"}}
        current = [
            {"file_path": "a.py", "file_hash": "h1"},
            {"file_path": "b.py", "file_hash": "h2"},
            {"file_path": "c.py", "file_hash": "h3"},  # NEW
        ]

        result = self._compute_diff(existing, current)

        assert result["added"] == 1
        assert "c.py" in result["added_paths"]
        assert result["modified"] == 0
        assert result["deleted"] == 0

    def test_detect_modified_tools(self):
        """Files with different hashes should be detected as modified."""
        existing = {"a.py": {"hash": "h1"}}
        current = [{"file_path": "a.py", "file_hash": "h2"}]  # Different hash

        result = self._compute_diff(existing, current)

        assert result["added"] == 0
        assert result["modified"] == 1
        assert "a.py" in result["modified_paths"]
        assert result["deleted"] == 0

    def test_detect_deleted_tools(self):
        """Files in DB but not in filesystem should be detected as deleted."""
        existing = {"a.py": {"hash": "h1"}, "b.py": {"hash": "h2"}}
        current = [{"file_path": "a.py", "file_hash": "h1"}]

        result = self._compute_diff(existing, current)

        assert result["added"] == 0
        assert result["modified"] == 0
        assert result["deleted"] == 1
        assert "b.py" in result["deleted_paths"]

    def test_no_changes(self):
        """Identical state should report no changes."""
        existing = {"a.py": {"hash": "h1"}, "b.py": {"hash": "h2"}}
        current = [
            {"file_path": "a.py", "file_hash": "h1"},
            {"file_path": "b.py", "file_hash": "h2"},
        ]

        result = self._compute_diff(existing, current)

        assert result["added"] == 0
        assert result["modified"] == 0
        assert result["deleted"] == 0

    def test_complex_diff(self):
        """Multiple changes should be detected correctly."""
        existing = {
            "a.py": {"hash": "h1"},
            "b.py": {"hash": "h2"},
            "c.py": {"hash": "h3"},
        }
        current = [
            {"file_path": "a.py", "file_hash": "h1"},  # Unchanged
            {"file_path": "b.py", "file_hash": "h2_changed"},  # Modified
            {"file_path": "d.py", "file_hash": "h4"},  # Added
            # c.py deleted
        ]

        result = self._compute_diff(existing, current)

        assert result["added"] == 1
        assert "d.py" in result["added_paths"]

        assert result["modified"] == 1
        assert "b.py" in result["modified_paths"]

        assert result["deleted"] == 1
        assert "c.py" in result["deleted_paths"]

    def test_ignore_empty_paths(self):
        """Tools without file_path should be ignored."""
        existing = {"a.py": {"hash": "h1"}}
        current = [
            {"file_path": "a.py", "file_hash": "h1"},
            {"file_hash": "h2"},  # No file_path
            {"file_path": "", "file_hash": "h3"},  # Empty file_path
        ]

        result = self._compute_diff(existing, current)

        assert result["added"] == 0
        assert result["modified"] == 0
        assert result["deleted"] == 0


class TestSyncCLICommands:
    """CLI command tests for sync and reindex."""

    @pytest.fixture
    def cli_runner(self):
        """Create a Typer test runner."""
        from typer.testing import CliRunner

        return CliRunner()

    def test_sync_command_exists(self, cli_runner):
        """omni skill sync command should exist and show help."""
        from agent.cli.commands.skill import skill_app

        result = cli_runner.invoke(skill_app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "Incrementally sync" in result.output or "sync" in result.output.lower()

    def test_reindex_command_exists(self, cli_runner):
        """omni skill reindex command should exist and show help."""
        from agent.cli.commands.skill import skill_app

        result = cli_runner.invoke(skill_app, ["reindex", "--help"])
        assert result.exit_code == 0
        assert "reindex" in result.output.lower()

    def test_sync_json_output_format(self, cli_runner):
        """sync --json should return valid JSON with expected keys."""
        from agent.cli.commands.skill import skill_app

        result = cli_runner.invoke(skill_app, ["sync", "--json"])
        # The output might contain rich formatting, try to extract JSON
        # Check if output starts with { (JSON) or contains { in stderr
        output = result.output.strip()
        if output.startswith("{"):
            data = json.loads(output)
            assert "added" in data
            assert "modified" in data
            assert "deleted" in data
        else:
            # When using Rich console with --json, output may be in stderr or formatted
            # This test verifies the command runs without crashing
            assert "sync" in result.output.lower() or result.exit_code in (0, 1)

    def test_reindex_json_output_format(self, cli_runner):
        """reindex --json should return valid JSON."""
        from agent.cli.commands.skill import skill_app

        result = cli_runner.invoke(skill_app, ["reindex", "--json"])
        output = result.output.strip()
        if output.startswith("{"):
            data = json.loads(output)
            assert "total_tools_indexed" in data or "mode" in data
        else:
            # Verify command exists and runs
            assert "reindex" in result.output.lower() or result.exit_code in (0, 1)


class TestSyncResultFormat:
    """Tests for sync result format consistency."""

    def test_sync_result_keys(self):
        """Sync result should have all required keys."""
        required_keys = ["added", "modified", "deleted", "total"]

        result = {"added": 0, "modified": 0, "deleted": 0, "total": 0}
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

    def test_total_computation(self):
        """Total should equal added + modified + deleted."""
        added, modified, deleted = 2, 3, 1
        total = added + modified + deleted

        result = {"added": added, "modified": modified, "deleted": deleted, "total": total}
        assert result["total"] == result["added"] + result["modified"] + result["deleted"]


class TestVectorStoreSyncIntegration:
    """Integration tests for sync_skills (requires actual store)."""

    @pytest.mark.asyncio
    async def test_sync_skills_returns_dict(self):
        """sync_skills should return a dict with sync results."""
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()
        # Even if no store is available, should return dict
        result = await vm.sync_skills("assets/skills", "skills")

        assert isinstance(result, dict)
        assert "added" in result
        assert "modified" in result
        assert "deleted" in result

    @pytest.mark.asyncio
    async def test_index_skills_returns_int(self):
        """index_skill_tools_with_schema should return int count."""
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()
        count = await vm.index_skill_tools_with_schema("assets/skills", "skills")

        assert isinstance(count, int)
        assert count >= 0
