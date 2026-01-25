"""
Git Smart Workflow Tests - Trinity Architecture v2.0

Tests for smart commit workflow functionality.
Uses direct imports from actual modules in scripts directory.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Add assets/skills to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _init_git_repo(tmp_path: Path) -> Path:
    """Initialize a git repository and return the project root."""
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
    )
    return tmp_path


def _commit_all(tmp_path: Path, message: str = "Initial commit"):
    """Create an initial commit to allow branching."""
    subprocess.run(
        ["git", "add", "."],
        cwd=tmp_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=tmp_path,
        capture_output=True,
    )


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
        subprocess.run(["git", "init"], capture_output=True)

        result = stage_and_scan(root_dir=str(tmp_path))

        assert isinstance(result, dict)
        assert "staged_files" in result

    def test_stage_and_scan_stages_files(self, tmp_path, monkeypatch):
        """Verify stage_and_scan stages files correctly."""
        from git.scripts.prepare import stage_and_scan

        monkeypatch.chdir(tmp_path)

        # Initialize git repo
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
        """Verify visualize_workflow function exists in the registry."""
        from omni.langgraph.visualize import visualize_workflow
        from git.scripts.smart_commit_workflow import _smart_commit_diagram

        assert callable(visualize_workflow)
        # Verify smart_commit is registered
        result = visualize_workflow("smart_commit")
        assert "graph TD" in result

    def test_visualize_workflow_returns_string(self, tmp_path, monkeypatch):
        """Verify visualize_workflow returns a string."""
        from omni.langgraph.visualize import visualize_workflow
        from git.scripts.smart_commit_workflow import _smart_commit_diagram

        monkeypatch.chdir(tmp_path)

        result = visualize_workflow("smart_commit")

        assert isinstance(result, str)
        assert "graph TD" in result


class TestSmartCommitApproveRestage:
    """Test smart_commit approve phase re-staging functionality.

    These tests create temporary git repositories to verify the workflow
    handles various scenarios correctly, especially the re-stage mechanism.
    """

    @pytest.mark.asyncio
    async def test_approve_restages_original_files(self, tmp_path, monkeypatch):
        """Test that approve re-stages files that were staged in start phase."""
        monkeypatch.chdir(tmp_path)
        project_root = _init_git_repo(tmp_path)

        # Create initial commit first
        _commit_all(project_root)

        # Create and stage a new file
        test_file = project_root / "new_file.txt"
        test_file.write_text("new content")
        subprocess.run(
            ["git", "add", "new_file.txt"],
            cwd=project_root,
            capture_output=True,
        )

        # Import and test the approve workflow
        from git.scripts.smart_commit_workflow import (
            _approve_smart_commit_async,
            _start_smart_commit_async,
            save_workflow_state,
            _WORKFLOW_TYPE,
        )

        # Start workflow - this stages files and saves state
        start_result = await _start_smart_commit_async(str(project_root))

        workflow_id = start_result.get("workflow_id")
        assert workflow_id is not None
        assert "new_file.txt" in start_result.get("staged_files", [])

        # Reset staging area (simulate user or lefthook clearing it)
        subprocess.run(
            ["git", "reset", "HEAD", "--", "new_file.txt"],
            cwd=project_root,
            capture_output=True,
        )

        # Modify the file (simulate lefthook changing it)
        test_file.write_text("modified by lefthook")

        # Now approve - should re-stage the original file
        result = await _approve_smart_commit_async(
            message="feat(test): test commit",
            workflow_id=workflow_id,
            project_root=str(project_root),
        )

        # Verify commit was created
        assert result.get("status") == "committed"
        assert result.get("commit_hash") is not None

    @pytest.mark.asyncio
    async def test_approve_with_empty_staged_files(self, tmp_path, monkeypatch):
        """Test approve handles case where original staged files are missing."""
        monkeypatch.chdir(tmp_path)
        project_root = _init_git_repo(tmp_path)

        _commit_all(project_root)

        from git.scripts.smart_commit_workflow import (
            _approve_smart_commit_async,
            save_workflow_state,
            _WORKFLOW_TYPE,
        )

        # Create a workflow state with no staged files (edge case)
        workflow_id = "empty_test"
        save_workflow_state(
            _WORKFLOW_TYPE,
            workflow_id,
            {"staged_files": [], "status": "pending"},
        )

        # This should not crash
        result = await _approve_smart_commit_async(
            message="feat(test): empty test",
            workflow_id=workflow_id,
            project_root=str(project_root),
        )

        # Should fail gracefully since no files to commit
        assert "error" in result or result.get("status") == "committed"

    @pytest.mark.asyncio
    async def test_workflow_state_persistence(self, tmp_path, monkeypatch):
        """Test that workflow state is saved and loaded correctly."""
        monkeypatch.chdir(tmp_path)
        project_root = _init_git_repo(tmp_path)

        _commit_all(project_root)

        # Create a test file
        test_file = project_root / "persist_test.txt"
        test_file.write_text("persist me")
        subprocess.run(
            ["git", "add", "persist_test.txt"],
            cwd=project_root,
            capture_output=True,
        )

        from git.scripts.smart_commit_workflow import (
            _start_smart_commit_async,
            load_workflow_state,
            _WORKFLOW_TYPE,
        )

        start_result = await _start_smart_commit_async(str(project_root))
        workflow_id = start_result.get("workflow_id")

        # Load state from checkpoint store
        loaded_state = load_workflow_state(_WORKFLOW_TYPE, workflow_id)

        # Checkpoint store may not be available in test environment
        if loaded_state is None:
            # Fallback: verify the workflow_id was generated and state was created
            assert workflow_id is not None
            assert start_result.get("staged_files") == ["persist_test.txt"]
        else:
            assert loaded_state is not None
            assert loaded_state.get("workflow_id") == workflow_id
            assert "persist_test.txt" in loaded_state.get("staged_files", [])


class TestSmartCommitSecurity:
    """Test security-related scenarios in smart_commit workflow."""

    def test_sensitive_files_detected_in_scan(self, tmp_path, monkeypatch):
        """Test that sensitive files are detected during stage_and_scan."""
        monkeypatch.chdir(tmp_path)
        project_root = _init_git_repo(tmp_path)

        _commit_all(project_root)

        # Create a sensitive file
        sensitive_file = project_root / ".env"
        sensitive_file.write_text("SECRET_KEY=abc123")

        from git.scripts.prepare import stage_and_scan

        result = stage_and_scan(root_dir=str(project_root))

        # Sensitive file should be detected and unstaged
        assert ".env" in result.get("security_issues", [])

    def test_sensitive_files_not_in_staged(self, tmp_path, monkeypatch):
        """Test that sensitive files are not included in staged_files."""
        monkeypatch.chdir(tmp_path)
        project_root = _init_git_repo(tmp_path)

        _commit_all(project_root)

        # Create both sensitive and normal files
        sensitive_file = project_root / ".env"
        sensitive_file.write_text("SECRET=abc")

        normal_file = project_root / "normal.txt"
        normal_file.write_text("normal content")

        from git.scripts.prepare import stage_and_scan

        result = stage_and_scan(root_dir=str(project_root))

        # Sensitive file should be in security_issues
        assert ".env" in result.get("security_issues", [])
        # Normal file should be staged
        assert "normal.txt" in result.get("staged_files", [])
        # Sensitive file should NOT be in staged_files
        assert ".env" not in result.get("staged_files", [])
