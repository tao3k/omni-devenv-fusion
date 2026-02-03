import shutil

import pytest

from omni.test_kit.decorators import omni_skill

# Import constants for workflow states if needed, or define locally
WORKFLOW_TYPE = "smart_commit"


@pytest.mark.asyncio
@omni_skill(name="git")
class TestSmartCommitWorkflowModular:
    """Modular tests for smart commit workflow using Omni Test Kit."""

    async def test_workflow_start(self, skill_tester, temp_git_repo, monkeypatch):
        """Test starting the smart commit workflow."""
        monkeypatch.chdir(temp_git_repo)

        # Create a change to stage
        (temp_git_repo / "new_file.txt").write_text("content")

        # Run start command via skill_tester
        # Note: smart_commit is the main entry point, action='start'
        result = await skill_tester.run("git", "smart_commit", action="start")

        assert result.success
        output = result.output

        # Verify workflow started
        assert "Workflow preparation complete" in str(output) or "workflow_id" in str(output)
        # Note: result is a string rendered via Jinja template

    async def test_workflow_approve(self, skill_tester, temp_git_repo, monkeypatch):
        """Test approving the smart commit workflow."""
        monkeypatch.chdir(temp_git_repo)

        # 1. Start workflow
        (temp_git_repo / "file.txt").write_text("content")
        # Direct call to get result dict for easier ID extraction
        from git.scripts.smart_commit_workflow import _start_smart_commit_async

        start_result = await _start_smart_commit_async()
        workflow_id = start_result.get("workflow_id")
        assert workflow_id

        # 2. Approve workflow
        approve_result = await skill_tester.run(
            "git",
            "smart_commit",
            action="approve",
            workflow_id=workflow_id,
            message="feat: test commit",
        )

        assert approve_result.success
        assert "Commit Successful" in str(approve_result.output) or "COMMITTED" in str(
            approve_result.output
        )

    async def test_security_scan_detects_secrets(self, skill_tester, temp_git_repo, monkeypatch):
        """Test that security scan detects sensitive files."""
        monkeypatch.chdir(temp_git_repo)

        # Create a sensitive file
        (temp_git_repo / ".env").write_text("SECRET=123")

        result = await skill_tester.run("git", "smart_commit", action="start")

        assert result.success
        output = result.output

        # Verify security issue detected in rendered output
        assert "Security Issue Detected" in str(output)
        assert ".env" in str(output)

    def _create_failing_lefthook(self, repo_path):
        """Helper to create failing lefthook config."""
        fail_script = repo_path / "fail.sh"
        fail_script.write_text("#!/bin/bash\nexit 1")
        fail_script.chmod(0o755)

        (repo_path / "lefthook.yml").write_text("""
pre-commit:
  commands:
    fail:
      run: ./fail.sh
""")

    async def test_lefthook_failure(self, skill_tester, temp_git_repo, monkeypatch):
        """Test handling of lefthook failures."""
        if not shutil.which("lefthook"):
            pytest.skip("lefthook not installed")

        monkeypatch.chdir(temp_git_repo)
        self._create_failing_lefthook(temp_git_repo)

        (temp_git_repo / "test.txt").write_text("content")

        result = await skill_tester.run("git", "smart_commit", action="start")

        # Should report error
        assert result.success
        assert "Lefthook Pre-commit Failed" in str(result.output)

    async def test_visualize_workflow(self, skill_tester):
        """Test visualization command."""
        result = await skill_tester.run("git", "smart_commit", action="visualize")

        assert result.success
        assert "graph TD" in str(result.output)

    async def test_approve_includes_formatting_changes(
        self, skill_tester, temp_git_repo, monkeypatch
    ):
        """Test that approve includes files modified after start (e.g., cargo fmt).

        This tests the scenario where:
        1. User starts workflow with some staged files
        2. Formatting tool (cargo fmt, rustfmt) runs and modifies OTHER files
        3. User approves - ALL modified files should be included in commit
        """
        import subprocess
        from git.scripts.smart_commit_workflow import (
            _start_smart_commit_async,
            _approve_smart_commit_async,
        )

        monkeypatch.chdir(temp_git_repo)

        # 1. Create and stage a Python file
        python_file = temp_git_repo / "test_file.py"
        python_file.write_text("# Original content\nx = 1\n")

        subprocess.run(["git", "add", "test_file.py"], capture_output=True)

        # 2. Start workflow
        start_result = await _start_smart_commit_async()
        workflow_id = start_result.get("workflow_id")
        assert workflow_id is not None
        assert "test_file.py" in start_result.get("staged_files", [])

        # 3. Simulate cargo fmt/rustfmt modifying the file AFTER start
        # (This is what happens when you run cargo fmt between start and approve)
        python_file.write_text("# Formatted by cargo fmt\nx = 1\ny = 2\n")

        # 4. Also create a NEW file that should be included
        new_file = temp_git_repo / "new_file.py"
        new_file.write_text("# New file created after start\nz = 3\n")

        # 5. Approve the workflow
        approve_result = await _approve_smart_commit_async(
            message="feat(test): include formatting changes",
            workflow_id=workflow_id,
            project_root=str(temp_git_repo),
        )

        # 6. Verify commit was created
        assert approve_result.get("status") == "committed", (
            f"Expected committed, got: {approve_result}"
        )
        assert approve_result.get("commit_hash") is not None

        # 7. Verify both files are in the commit
        proc = subprocess.run(
            ["git", "show", "--name-only", "--format=", approve_result["commit_hash"]],
            capture_output=True,
            text=True,
            cwd=temp_git_repo,
        )
        committed_files = proc.stdout.strip().split("\n")

        assert "test_file.py" in committed_files, (
            f"Original file should be in commit: {committed_files}"
        )
        assert "new_file.py" in committed_files, f"New file should be in commit: {committed_files}"
