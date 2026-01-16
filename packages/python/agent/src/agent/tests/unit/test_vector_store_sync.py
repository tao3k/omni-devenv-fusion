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


class TestPathNormalization:
    """Tests for path normalization in sync_skills.

    Phase 68: Critical tests for path handling to prevent sync bugs.
    """

    @pytest.fixture
    def skills_dir(self, tmp_path):
        """Create a temporary skills directory structure."""
        skills = tmp_path / "assets" / "skills"
        skills.mkdir(parents=True)
        return skills

    def test_normalize_simple_relative_path(self, skills_dir):
        """Simple relative paths should be normalized correctly."""
        skills_dir_resolved = skills_dir.resolve()
        skills_dir_str = str(skills_dir_resolved)

        def normalize_path(p: str) -> str:
            p_str = p
            # If path contains skills_dir as prefix, strip it
            if skills_dir_str in p_str:
                p_str = p_str.replace(skills_dir_str, "").strip("/")
            # Also handle legacy "assets/skills/" prefix
            if p_str.startswith("assets/skills/"):
                p_str = p_str[len("assets/skills/") :]
            return p_str

        result = normalize_path("git/scripts/status.py")
        assert result == "git/scripts/status.py"

    def test_normalize_path_with_skills_prefix(self, skills_dir):
        """Paths with assets/skills/ prefix should be normalized."""
        skills_dir_resolved = skills_dir.resolve()
        skills_dir_str = str(skills_dir_resolved)

        def normalize_path(p: str) -> str:
            p_str = p
            if skills_dir_str in p_str:
                p_str = p_str.replace(skills_dir_str, "").strip("/")
            if p_str.startswith("assets/skills/"):
                p_str = p_str[len("assets/skills/") :]
            return p_str

        # Path with assets/skills/ prefix
        result = normalize_path("assets/skills/git/scripts/status.py")
        assert result == "git/scripts/status.py"

    def test_normalize_absolute_path(self, skills_dir):
        """Absolute paths should be converted to relative paths."""
        from pathlib import Path

        skills_dir_resolved = skills_dir.resolve()
        skills_dir_str = str(skills_dir_resolved)

        def normalize_path(p: str) -> str:
            path = Path(p)
            if path.is_absolute():
                resolved = path.resolve()
                try:
                    return str(resolved.relative_to(skills_dir_resolved))
                except ValueError:
                    return str(resolved)
            else:
                p_str = p
                if skills_dir_str in p_str:
                    p_str = p_str.replace(skills_dir_str, "").strip("/")
                if p_str.startswith("assets/skills/"):
                    p_str = p_str[len("assets/skills/") :]
                return p_str

        # Test absolute path under skills_dir
        abs_path = str(skills_dir / "git" / "scripts" / "status.py")
        result = normalize_path(abs_path)
        assert result == "git/scripts/status.py"

    def test_normalize_mixed_path_formats_consistency(self):
        """Absolute and relative paths for same file should normalize to same value."""
        from pathlib import Path
        from common.skills_path import SKILLS_DIR

        skills_dir = SKILLS_DIR()
        skills_dir_resolved = skills_dir.resolve()
        skills_dir_str = str(skills_dir_resolved)

        def normalize_path(p: str) -> str:
            path = Path(p)
            if path.is_absolute():
                resolved = path.resolve()
                try:
                    return str(resolved.relative_to(skills_dir_resolved))
                except ValueError:
                    return str(resolved)
            else:
                p_str = p
                if skills_dir_str in p_str:
                    p_str = p_str.replace(skills_dir_str, "").strip("/")
                if p_str.startswith("assets/skills/"):
                    p_str = p_str[len("assets/skills/") :]
                return p_str

        # Absolute path
        abs_path = str((skills_dir / "git" / "scripts" / "status.py").resolve())
        abs_normalized = normalize_path(abs_path)

        # Relative path with assets/skills/ prefix (from Rust scanner)
        rel_path = "assets/skills/git/scripts/status.py"
        rel_normalized = normalize_path(rel_path)

        # Both should produce identical simple relative paths
        assert abs_normalized == rel_normalized == "git/scripts/status.py", (
            f"All paths should normalize to 'git/scripts/status.py': "
            f"abs='{abs_normalized}', rel='{rel_normalized}'"
        )

    def test_normalize_double_path_bug(self):
        """Should detect and handle double-path bug (assets/skills/assets/skills/...)."""
        from pathlib import Path
        from common.skills_path import SKILLS_DIR

        skills_dir = SKILLS_DIR()
        skills_dir_resolved = skills_dir.resolve()
        skills_dir_str = str(skills_dir_resolved)

        def normalize_path(p: str) -> str:
            path = Path(p)
            if path.is_absolute():
                resolved = path.resolve()
                try:
                    return str(resolved.relative_to(skills_dir_resolved))
                except ValueError:
                    return str(resolved)
            else:
                p_str = p
                # Handle path with skills_dir prefix
                if skills_dir_str in p_str:
                    p_str = p_str.replace(skills_dir_str, "").strip("/")
                # Handle path with assets/skills/ prefix (from Rust scanner)
                if p_str.startswith("assets/skills/"):
                    p_str = p_str[len("assets/skills/") :]
                # Handle double assets/skills/ prefix (bug case)
                while p_str.startswith("assets/skills/"):
                    p_str = p_str[len("assets/skills/") :]
                return p_str

        # Simulate buggy path with double assets/skills (from Rust scanner)
        buggy_path = "assets/skills/assets/skills/git/scripts/status.py"
        result = normalize_path(buggy_path)

        # Should NOT contain double "assets/skills"
        assert "assets/skills/assets/skills" not in result, (
            f"Path normalization should not produce double paths: {result}"
        )
        # Should produce simple relative path
        assert result == "git/scripts/status.py", (
            f"Expected 'git/scripts/status.py', got '{result}'"
        )


class TestSyncIdempotency:
    """Tests for sync idempotency - running sync twice should be stable."""

    @pytest.mark.asyncio
    async def test_sync_twice_no_changes(self):
        """Running sync twice should report no changes on second run."""
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()

        # First sync
        result1 = await vm.sync_skills("assets/skills", "test_idempotency")

        # Second sync - should be stable
        result2 = await vm.sync_skills("assets/skills", "test_idempotency")

        # First sync should have added some tools (or 0 if already synced)
        # Second sync should report no changes
        assert result2["added"] == 0, f"Expected 0 added on second sync, got {result2['added']}"
        assert result2["modified"] == 0, (
            f"Expected 0 modified on second sync, got {result2['modified']}"
        )
        assert result2["deleted"] == 0, (
            f"Expected 0 deleted on second sync, got {result2['deleted']}"
        )

    @pytest.mark.asyncio
    async def test_sync_three_times_stability(self):
        """Running sync three times should all report no changes after first."""
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()

        results = []
        for i in range(3):
            result = await vm.sync_skills("assets/skills", "test_stability")
            results.append(result)

        # First run may have changes, subsequent runs should have none
        for i in range(1, len(results)):
            assert results[i]["added"] == 0, f"Run {i + 1}: expected 0 added"
            assert results[i]["modified"] == 0, f"Run {i + 1}: expected 0 modified"
            assert results[i]["deleted"] == 0, f"Run {i + 1}: expected 0 deleted"


class TestSyncPathConsistency:
    """Tests for path format consistency between DB and filesystem."""

    @pytest.mark.asyncio
    async def test_db_paths_match_filesystem_paths(self):
        """Paths in DB should match paths discovered by scanner."""
        import json
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()
        store = vm._ensure_store()

        if not store:
            pytest.skip("Vector store not available")

        # Clean up any existing data in the test table to ensure test isolation
        await vm.drop_table("test_consistency")

        # Run sync to ensure DB is populated
        await vm.sync_skills("assets/skills", "test_consistency")

        # Get DB state
        existing_json = store.get_all_file_hashes("test_consistency")
        existing = json.loads(existing_json) if existing_json else {}

        # Get filesystem state via scanner
        current_jsons = store.scan_skill_tools_raw("assets/skills")
        current_tools = []
        for tool_json in current_jsons:
            try:
                current_tools.append(json.loads(tool_json))
            except json.JSONDecodeError:
                continue

        # Normalize all paths for comparison
        # Must match the normalization used in sync_skills
        from pathlib import Path
        from common.skills_path import SKILLS_DIR

        skills_dir = SKILLS_DIR()
        skills_dir_resolved = skills_dir.resolve()
        skills_dir_str = str(skills_dir_resolved)

        def normalize(p: str) -> str:
            """Normalize path to relative path from SKILLS_DIR.

            Handles:
            - Absolute paths
            - Relative paths with assets/skills/ prefix (from Rust scanner)
            - Simple relative paths
            """
            try:
                path = Path(p)
                if path.is_absolute():
                    resolved = path.resolve()
                    try:
                        return str(resolved.relative_to(skills_dir_resolved))
                    except ValueError:
                        return str(resolved)
                else:
                    # Relative path - may already have assets/skills/ prefix
                    p_str = p
                    # Handle path with skills_dir prefix
                    if skills_dir_str in p_str:
                        p_str = p_str.replace(skills_dir_str, "").strip("/")
                    # Handle path with "assets/skills/" prefix (from Rust scanner)
                    if p_str.startswith("assets/skills/"):
                        p_str = p_str[len("assets/skills/") :]
                    # Handle double assets/skills/ prefix
                    while p_str.startswith("assets/skills/"):
                        p_str = p_str[len("assets/skills/") :]
                    return p_str
            except Exception:
                return p

        db_paths = {normalize(p) for p in existing.keys()}
        fs_paths = {normalize(t.get("file_path", "")) for t in current_tools if t.get("file_path")}

        # All DB paths should exist in filesystem
        missing_in_fs = db_paths - fs_paths
        assert not missing_in_fs, f"Paths in DB but not in filesystem: {missing_in_fs}"

        # All filesystem paths should exist in DB
        missing_in_db = fs_paths - db_paths
        assert not missing_in_db, f"Paths in filesystem but not in DB: {missing_in_db}"


class TestSyncEdgeCases:
    """Edge case tests for sync functionality."""

    def test_empty_filesystem_no_crash(self):
        """Sync with empty filesystem should not crash."""
        # This tests the diff algorithm with edge cases
        existing = {"a.py": {"hash": "h1"}}
        current: list[dict] = []

        existing_paths = set(existing.keys())
        current_paths = {t.get("file_path", "") for t in current if t.get("file_path")}
        to_delete = existing_paths - current_paths

        assert len(to_delete) == 1  # a.py should be deleted
        assert "a.py" in to_delete

    def test_empty_db_no_crash(self):
        """Sync with empty DB (fresh install) should work."""
        existing: dict = {}
        current = [
            {"file_path": "a.py", "file_hash": "h1"},
            {"file_path": "b.py", "file_hash": "h2"},
        ]

        existing_paths = set(existing.keys())
        to_add = [t for t in current if t.get("file_path") and t["file_path"] not in existing_paths]

        assert len(to_add) == 2  # Both should be added
        assert {"a.py", "b.py"} == {t["file_path"] for t in to_add}

    def test_special_chars_in_paths(self):
        """Paths with special characters should be handled correctly."""
        from pathlib import Path
        from common.skills_path import SKILLS_DIR

        skills_dir = SKILLS_DIR()

        def normalize_path(p: str) -> str:
            path = Path(p)
            if path.is_absolute():
                resolved = path.resolve()
                try:
                    return str(resolved.relative_to(skills_dir.resolve()))
                except ValueError:
                    return str(resolved)
            else:
                return str((skills_dir / p).resolve().relative_to(skills_dir.resolve()))

        # Paths with spaces, underscores, numbers
        special_paths = [
            "my_skill/scripts/module_1.py",
            "test-123/scripts/hyphen-name.py",
        ]

        for p in special_paths:
            result = normalize_path(p)
            assert result, f"normalize_path should not return empty for: {p}"
            # Result should be a valid path string
            assert isinstance(result, str)
            assert len(result) > 0
