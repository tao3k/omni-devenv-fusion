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
