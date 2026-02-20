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
        from git.scripts.smart_commit_graphflow.commands import _start_smart_commit_async

        start_result = await _start_smart_commit_async(project_root=str(temp_git_repo))
        workflow_id = start_result.get("workflow_id")
        assert workflow_id

        # 2. Approve workflow
        approve_result = await skill_tester.run(
            "git",
            "smart_commit",
            action="approve",
            workflow_id=workflow_id,
            message="feat(core): test commit",
        )

        assert approve_result.success
        assert "Commit Successful" in str(approve_result.output) or "COMMITTED" in str(
            approve_result.output
        )

    async def test_security_scan_detects_secrets(self, skill_tester, temp_git_repo, monkeypatch):
        """Test that security scan detects sensitive files."""
        from git.scripts.smart_commit_graphflow._enums import SmartCommitStatus
        from git.scripts.smart_commit_graphflow.commands import _start_smart_commit_async

        monkeypatch.chdir(temp_git_repo)

        # Create a sensitive file
        (temp_git_repo / ".env").write_text("SECRET=123")

        result = await _start_smart_commit_async(project_root=str(temp_git_repo))
        assert result.get("status") == SmartCommitStatus.SECURITY_VIOLATION
        assert ".env" in result.get("security_issues", [])

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
        from git.scripts.smart_commit_graphflow._enums import SmartCommitStatus
        from git.scripts.smart_commit_graphflow.commands import _start_smart_commit_async

        if not shutil.which("lefthook"):
            pytest.skip("lefthook not installed")

        monkeypatch.chdir(temp_git_repo)
        self._create_failing_lefthook(temp_git_repo)

        (temp_git_repo / "test.txt").write_text("content")

        result = await _start_smart_commit_async(project_root=str(temp_git_repo))
        assert result.get("status") == SmartCommitStatus.LEFTHOOK_FAILED
        assert result.get("error")

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
        from git.scripts.smart_commit_graphflow.commands import (
            _start_smart_commit_async,
            _approve_smart_commit_async,
        )

        monkeypatch.chdir(temp_git_repo)

        # 1. Create and stage a Python file
        python_file = temp_git_repo / "test_file.py"
        python_file.write_text("# Original content\nx = 1\n")

        subprocess.run(
            ["git", "add", "test_file.py"],
            capture_output=True,
            cwd=temp_git_repo,
        )

        # 2. Start workflow
        start_result = await _start_smart_commit_async(project_root=str(temp_git_repo))
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

    async def test_cargo_fmt_import_reorder_restage(self, skill_tester, temp_git_repo, monkeypatch):
        """Test that cargo fmt import reordering is re-staged.

        This simulates the exact scenario:
        - User stages a Rust file with: use serde_json::{json, Value};
        - cargo fmt runs and reformats to: use serde_json::{Value, json};
        - The workflow should detect this change and re-stage the file
        """
        import subprocess
        from git.scripts.prepare import stage_and_scan

        monkeypatch.chdir(temp_git_repo)

        # Initialize git config
        result = subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True,
            cwd=temp_git_repo,
        )
        result = subprocess.run(
            ["git", "config", "user.name", "Test"],
            capture_output=True,
            cwd=temp_git_repo,
        )

        # Create a Rust file with specific import order (unformatted)
        rust_file = temp_git_repo / "lib.rs"
        rust_file.write_text("use serde_json::{Value, json};\n\npub fn test() {}\n")

        # Stage the file
        subprocess.run(
            ["git", "add", "lib.rs"],
            capture_output=True,
            cwd=temp_git_repo,
        )

        # Get staged files before cargo fmt
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=temp_git_repo,
        )
        staged_before = result.stdout
        print(f"Staged before fmt: {staged_before.strip()}")
        assert "lib.rs" in staged_before

        # Simulate cargo fmt: reorder imports (alphabetical order)
        rust_file.write_text("use serde_json::{json, Value};\n\npub fn test() {}\n")

        # Now lib.rs shows as modified (diff between HEAD and working tree)
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=temp_git_repo,
        )
        modified = result.stdout
        print(f"Modified after fmt: {modified.strip()}")
        assert "lib.rs" in modified

        # Run stage_and_scan - this should detect the modification and re-stage
        scan_result = stage_and_scan(str(temp_git_repo))

        # Verify no errors
        assert scan_result.get("lefthook_error") == "", (
            f"Lefthook error: {scan_result.get('lefthook_error')}"
        )

        # Verify lib.rs is still in staged files
        staged_files = scan_result.get("staged_files", [])
        print(f"Staged after scan: {staged_files}")
        assert "lib.rs" in staged_files, f"lib.rs should be re-staged: {staged_files}"

        # Verify the staged content matches the formatted version
        proc = subprocess.run(
            ["git", "diff", "--cached", "lib.rs"],
            capture_output=True,
            text=True,
            cwd=temp_git_repo,
        )
        diff_cached = proc.stdout
        print(f"Staged diff:\n{diff_cached}")

        # The diff should show the import reorder is staged (alphabetical: json before Value)
        assert "json, Value" in diff_cached, (
            f"Import reorder should be in staged diff. Got: {diff_cached}"
        )

    async def test_approve_runs_lefthook_before_commit(
        self, skill_tester, temp_git_repo, monkeypatch
    ):
        """Test that approve runs lefthook pre-commit before actual commit.

        This ensures that any formatting changes from lefthook hooks are
        captured in the final commit, matching what git commit's hook would produce.
        """
        import subprocess
        import shutil
        from git.scripts.smart_commit_graphflow.commands import (
            _start_smart_commit_async,
            _approve_smart_commit_async,
        )

        if not shutil.which("lefthook"):
            pytest.skip("lefthook not installed")

        monkeypatch.chdir(temp_git_repo)

        # Setup git config
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            capture_output=True,
            cwd=temp_git_repo,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            capture_output=True,
            cwd=temp_git_repo,
        )

        # Create a lefthook that modifies files (like cargo fmt)
        lefthook_script = temp_git_repo / "lefthook_fmt.sh"
        lefthook_script.write_text("""#!/bin/bash
# Reorder imports alphabetically (json before Value)
perl -0777 -i -pe 's/Value, json/json, Value/g' lib.rs
exit 0
""")
        lefthook_script.chmod(0o755)

        (temp_git_repo / "lefthook.yml").write_text("""
pre-commit:
  commands:
    fmt:
      run: ./lefthook_fmt.sh
""")

        # Create original file with unformatted import order
        rust_file = temp_git_repo / "lib.rs"
        rust_file.write_text("use serde::{Value, json};\n\npub fn test() {}\n")

        subprocess.run(
            ["git", "add", "lib.rs"],
            capture_output=True,
            cwd=temp_git_repo,
        )
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            capture_output=True,
            cwd=temp_git_repo,
        )

        # Create a change
        rust_file.write_text(
            "use serde::{Value, json};\n\npub fn test() {}\n\npub fn another() {}\n"
        )
        subprocess.run(
            ["git", "add", "lib.rs"],
            capture_output=True,
            cwd=temp_git_repo,
        )

        # Start workflow
        start_result = await _start_smart_commit_async(project_root=str(temp_git_repo))
        workflow_id = start_result.get("workflow_id")

        # Approve - this should run lefthook before commit and re-stage
        approve_result = await _approve_smart_commit_async(
            message="feat(test): lefthook re-stage",
            workflow_id=workflow_id,
            project_root=str(temp_git_repo),
        )

        # Verify commit was created
        assert approve_result.get("status") == "committed", (
            f"Expected committed, got: {approve_result}"
        )
        commit_hash = approve_result.get("commit_hash")
        assert commit_hash

        # Verify the committed content has the formatted import order
        proc = subprocess.run(
            ["git", "show", commit_hash + ":lib.rs"],
            capture_output=True,
            text=True,
            cwd=temp_git_repo,
        )
        committed_content = proc.stdout
        assert "json, Value" in committed_content, (
            f"Formatted import should be in commit. Got: {committed_content}"
        )

    async def test_start_persists_state_via_common_workflow_store(self, temp_git_repo, monkeypatch):
        """Test start action persists workflow state through WorkflowStateStore."""
        from git.scripts.smart_commit_graphflow import commands

        monkeypatch.chdir(temp_git_repo)
        (temp_git_repo / "tracked.txt").write_text("content")

        captured: dict[str, object] = {}

        class _FakeStore:
            def save(self, workflow_id, state, *, metadata=None):
                captured["workflow_id"] = workflow_id
                captured["state"] = state

            def load(self, workflow_id):
                return None

        monkeypatch.setattr(commands, "_SMART_COMMIT_STORE", _FakeStore())

        result = await commands._start_smart_commit_async(project_root=str(temp_git_repo))

        assert captured["workflow_id"] == result.get("workflow_id")
        saved_state = captured.get("state")
        assert isinstance(saved_state, dict)
        assert saved_state.get("workflow_id") == result.get("workflow_id")
        assert isinstance(saved_state.get("staged_files"), list)

    async def test_status_uses_common_workflow_store(self, monkeypatch):
        """Test status retrieval is delegated to WorkflowStateStore."""
        from git.scripts.smart_commit_graphflow import commands

        class _FakeStore:
            def save(self, workflow_id, state, *, metadata=None):
                return None

            def load(self, workflow_id):
                return {"status": "prepared", "staged_files": ["a.py"]}

        monkeypatch.setattr(commands, "_SMART_COMMIT_STORE", _FakeStore())
        status = await commands._get_workflow_status_async("wf-status")
        assert status is not None
        assert status.get("status") == "prepared"

    async def test_start_allows_missing_pre_commit_hook(self, temp_git_repo, monkeypatch):
        """Missing pre-commit hook should not mark start as lefthook_failed."""
        from git.scripts.smart_commit_graphflow.commands import _start_smart_commit_async

        monkeypatch.chdir(temp_git_repo)
        (temp_git_repo / "missing-hook.txt").write_text("content\n")

        result = await _start_smart_commit_async(project_root=str(temp_git_repo))

        assert result.get("status") != "lefthook_failed"
        assert result.get("error", "") == ""

    async def test_start_default_root_uses_cwd_git_toplevel(self, temp_git_repo, monkeypatch):
        """Default start path should follow cwd git top-level, not PRJ_ROOT."""
        from git.scripts.smart_commit_graphflow.commands import _start_smart_commit_async

        monkeypatch.chdir(temp_git_repo)
        monkeypatch.setenv("PRJ_ROOT", str(temp_git_repo.parent))
        (temp_git_repo / "cwd-root.txt").write_text("content\n")

        result = await _start_smart_commit_async()

        assert "cwd-root.txt" in result.get("staged_files", [])

    async def test_action_validation_rejects_invalid_action(self):
        """Invalid action should return common validation error message."""
        from git.scripts.smart_commit_graphflow.commands import smart_commit
        from omni.foundation.api.mcp_schema import extract_text_content

        result = await smart_commit(action="invalid")
        text = extract_text_content(result) or ""

        assert "action must be one of:" in text

    async def test_action_validation_normalizes_case_and_whitespace(self):
        """Action normalization should accept mixed-case padded action strings."""
        from git.scripts.smart_commit_graphflow.commands import smart_commit
        from omni.foundation.api.mcp_schema import extract_text_content

        result = await smart_commit(action="  Visualize  ")
        text = extract_text_content(result) or ""

        assert "Smart Commit Workflow" in text
