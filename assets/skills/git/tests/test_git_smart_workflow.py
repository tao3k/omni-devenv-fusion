"""
Git Smart Workflow Tests - Trinity Architecture v2.0

Tests for smart commit workflow functionality.
Uses direct imports from actual modules in scripts directory.
"""

import sys
from pathlib import Path

# Add assets/skills to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCommitState:
    """Test commit state schema and factory."""

    def test_create_initial_state(self):
        """Test creating initial commit state."""
        from git.scripts.commit_state import create_initial_state

        state = create_initial_state(project_root="/test", workflow_id="abc123")

        assert state["project_root"] == "/test"
        assert state["workflow_id"] == "abc123"
        assert state["status"] == "pending"
        assert state["staged_files"] == []
        assert state["diff_content"] == ""
        assert state["security_issues"] == []
        assert state["final_message"] == ""
        assert state["commit_hash"] is None
        assert state["error"] is None

    def test_create_initial_state_defaults(self):
        """Test default values for optional parameters."""
        from git.scripts.commit_state import create_initial_state

        state = create_initial_state()

        assert state["project_root"] == "."
        assert state["workflow_id"] == "default"


class TestStageAndScan:
    """Test stage_and_scan function."""

    def test_stage_and_scan_returns_dict(self, tmp_path, monkeypatch):
        """Verify stage_and_scan returns a dictionary."""
        from git.scripts.prepare import stage_and_scan

        monkeypatch.chdir(tmp_path)

        # Initialize git repo
        import subprocess

        subprocess.run(["git", "init"], capture_output=True)

        result = stage_and_scan(root_dir=str(tmp_path))

        assert isinstance(result, dict)
        assert "staged_files" in result

    def test_stage_and_scan_stages_files(self, tmp_path, monkeypatch):
        """Verify stage_and_scan stages files correctly."""
        from git.scripts.prepare import stage_and_scan

        monkeypatch.chdir(tmp_path)

        # Initialize git repo
        import subprocess

        subprocess.run(["git", "init"], capture_output=True)

        # Create a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        result = stage_and_scan(root_dir=str(tmp_path))

        assert "test.txt" in result.get("staged_files", [])


class TestSmartCommitWorkflow:
    """Test smart commit workflow functions."""

    def test_build_workflow_exists(self):
        """Verify _build_workflow function exists."""
        from git.scripts.smart_commit_workflow import _build_workflow

        assert callable(_build_workflow)

    def test_visualize_workflow_exists(self):
        """Verify visualize_workflow function exists."""
        from git.scripts.smart_commit_workflow import visualize_workflow

        assert callable(visualize_workflow)

    def test_visualize_workflow_returns_string(self, tmp_path, monkeypatch):
        """Verify visualize_workflow returns a string."""
        from git.scripts.smart_commit_workflow import visualize_workflow

        monkeypatch.chdir(tmp_path)

        result = visualize_workflow()

        assert isinstance(result, str)
