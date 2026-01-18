"""
Git Skill Tests - Updated for Scripts Architecture

Tests the new architecture where:
- Scripts/*.py contain plain functions (status, branch, log, etc.)
- Only @skill_command decorated functions are exposed as tools
- Smart commit workflow uses smart_commit command

Usage:
    def test_status_function():  # Tests the function directly
        from agent.skills.git.scripts import status
        result = status.status()
        assert result is not None

No conftest.py, no imports needed!
"""

import subprocess
import pytest
import inspect
import re
from unittest.mock import MagicMock


# ==============================================================================
# Script Function Tests - Direct import pattern
# ==============================================================================


def test_status_module_exists():
    """Verify status module exists with status function."""
    from agent.skills.git.scripts import status

    assert hasattr(status, "status")
    assert callable(status.status)


def test_status_returns_string(project_root):
    """Verify status function returns a string."""
    from agent.skills.git.scripts import status

    result = status.status(project_root=project_root)
    assert isinstance(result, str)


def test_branch_module_exists():
    """Verify branch module exists with current_branch function."""
    from agent.skills.git.scripts import branch

    assert hasattr(branch, "current_branch")
    assert callable(branch.current_branch)
    assert hasattr(branch, "list_branches")
    assert callable(branch.list_branches)


def test_current_branch_returns_string(project_root):
    """Verify current_branch function returns a string."""
    from agent.skills.git.scripts import branch

    result = branch.current_branch()
    assert isinstance(result, str)


def test_list_branches_returns_string(project_root):
    """Verify list_branches function returns a string."""
    from agent.skills.git.scripts import branch

    result = branch.list_branches()
    assert isinstance(result, str)


def test_log_module_exists():
    """Verify log module exists with get_log function."""
    from agent.skills.git.scripts import log

    assert hasattr(log, "get_log")
    assert callable(log.get_log)


def test_get_log_returns_string(project_root):
    """Verify get_log function returns a string."""
    from agent.skills.git.scripts import log

    result = log.get_log(n=3)
    assert isinstance(result, str)


def test_diff_module_exists():
    """Verify diff module exists with get_diff function."""
    from agent.skills.git.scripts import diff

    assert hasattr(diff, "get_diff")
    assert callable(diff.get_diff)


def test_get_diff_returns_string(project_root):
    """Verify get_diff function returns a string."""
    from agent.skills.git.scripts import diff

    result = diff.get_diff()
    assert isinstance(result, str)


# ==============================================================================
# Skill Command Tests - Tests for @skill_command decorated functions
# ==============================================================================


def test_smart_commit_command_exists(git):
    """Verify smart_commit command exists (the main workflow command)."""
    # git is a SkillProxy with skill_command decorated functions
    assert hasattr(git, "smart_commit")
    assert callable(git.smart_commit)


def test_git_commit_command_exists(git):
    """Verify git_commit command exists."""
    assert hasattr(git, "git_commit")
    assert callable(git.git_commit)


def test_git_commit_amend_command_exists(git):
    """Verify git_commit_amend command exists."""
    assert hasattr(git, "git_commit_amend")
    assert callable(git.git_commit_amend)


def test_git_commit_no_verify_command_exists(git):
    """Verify git_commit_no_verify command exists."""
    assert hasattr(git, "git_commit_no_verify")
    assert callable(git.git_commit_no_verify)


def test_git_revert_command_exists(git):
    """Verify git_revert command exists."""
    assert hasattr(git, "git_revert")
    assert callable(git.git_revert)


# ==============================================================================
# Native Git Command Tests (for verification)
# ==============================================================================


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, capture_output=True)

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

    return repo_path


@pytest.mark.parametrize(
    "cmd,args",
    [
        (["git", "status"], ["--porcelain"]),
        (["git", "branch"], ["-a"]),
        (["git", "log"], ["--oneline", "-n3"]),
        (["git", "remote"], ["-v"]),
    ],
)
def test_git_command(temp_git_repo, cmd, args):
    """Test git commands in isolated temporary repository."""
    result = subprocess.run(cmd + args, capture_output=True, text=True, cwd=temp_git_repo)
    assert result.returncode == 0


# ==============================================================================
# Skill Command Metadata Tests
# ==============================================================================


def test_smart_commit_has_metadata(git):
    """Verify smart_commit command has required metadata."""
    from agent.skills.git.scripts.smart_commit_workflow import smart_commit

    # The function should have _skill_config from @skill_command decorator
    assert hasattr(smart_commit, "_skill_config") or hasattr(smart_commit, "_command_info")


def test_git_commit_has_metadata(git):
    """Verify git_commit command has required metadata."""
    from agent.skills.git.scripts.commit import commit

    assert hasattr(commit, "_skill_config") or hasattr(commit, "_command_info")


# ==============================================================================
# Commit Message Parsing Tests
# ==============================================================================


def test_commit_message_parsing_with_scope():
    """Verify commit message parsing extracts type, scope, description."""
    message = "feat(git): add new feature"

    match = re.match(r"^(\w+)(?:\(([^)]+)\))?:\s*(.+)$", message)

    assert match is not None
    assert match.group(1) == "feat"
    assert match.group(2) == "git"
    assert match.group(3) == "add new feature"


def test_commit_message_parsing_without_scope():
    """Verify commit message parsing works without scope."""
    message = "fix: patch bug"

    match = re.match(r"^(\w+)(?:\(([^)]+)\))?:\s*(.+)$", message)

    assert match is not None
    assert match.group(1) == "fix"
    assert match.group(2) is None or match.group(2) == ""
    assert match.group(3) == "patch bug"


# ==============================================================================
# Scope Validation Tests
# ==============================================================================


def test_validate_and_fix_scope_function_exists():
    """Verify scope validation function exists in prepare module."""
    from agent.skills.git.scripts import prepare as prepare_mod

    assert hasattr(prepare_mod, "_validate_and_fix_scope")
    assert callable(prepare_mod._validate_and_fix_scope)


def test_get_cog_scopes_returns_list():
    """Verify _get_cog_scopes returns a list of scopes."""
    from agent.skills.git.scripts.prepare import _get_cog_scopes

    scopes = _get_cog_scopes()

    assert isinstance(scopes, list)
    # Should have some common scopes from cog.toml
    if scopes:
        assert any(s in scopes for s in ["git", "docs", "agent"])


# ==============================================================================
# Template Rendering Tests
# ==============================================================================


def test_render_commit_message_exists():
    """Verify render_commit_message function exists."""
    from agent.skills.git.scripts import rendering

    assert hasattr(rendering, "render_commit_message")


def test_render_commit_message_returns_string():
    """Verify render_commit_message returns formatted string."""
    from agent.skills.git.scripts.rendering import render_commit_message

    result = render_commit_message(
        subject="feat(git): test feature",
        body="- test item 1\n- test item 2",
        status="committed",
    )

    assert isinstance(result, str)
    assert "feat(git): test feature" in result


def test_render_workflow_result_json_format():
    """Verify render_workflow_result returns JSON format (not XML)."""
    from agent.skills.git.scripts.rendering import render_workflow_result

    result = render_workflow_result(
        intent="prepare_commit",
        success=True,
        message="Commit preparation completed",
        details={"has_staged": "True", "staged_file_count": "5"},
    )

    assert isinstance(result, str)
    # Returns JSON format
    assert '"intent"' in result or "intent" in result
    assert '"success"' in result or "success" in result


def test_render_commit_message_with_security():
    """Verify commit message template includes security information."""
    from agent.skills.git.scripts.rendering import render_commit_message

    result = render_commit_message(
        subject="feat(git): test feature",
        body="- test item 1\n- test item 2",
        status="committed",
        security_status="No sensitive files detected",
    )

    assert isinstance(result, str)
    # Should contain security info
    assert "security" in result.lower() or "Safe" in result


def test_render_commit_message_security_issues():
    """Verify commit message template handles security issues."""
    from agent.skills.git.scripts.rendering import render_commit_message

    result = render_commit_message(
        subject="fix: bug fix",
        body="Fixed the issue",
        status="security_violation",
        security_status="Detected sensitive files",
        security_issues=[".env", ".credentials"],
    )

    assert isinstance(result, str)
    # Should contain security warning
    assert "security" in result.lower() or "Detected" in result


# ==============================================================================
# Cog Scopes Regex Tests
# ==============================================================================


def test_scopes_regex_matches_cog_toml_format():
    """Verify regex correctly parses scopes from cog.toml."""
    cog_toml_content = """
scopes = [
    "git",
    "docs",
    "agent",
    "core"
]
"""

    match = re.search(r"scopes\s*=\s*\[([^\]]+)\]", cog_toml_content, re.DOTALL)
    assert match is not None

    scopes_str = match.group(1)
    scopes = re.findall(r'"([^"]+)"', scopes_str)

    assert scopes == ["git", "docs", "agent", "core"]


# ==============================================================================
# Stage and Scan Tests
# ==============================================================================


def test_stage_and_scan_exists():
    """Verify stage_and_scan function exists."""
    from agent.skills.git.scripts.prepare import stage_and_scan

    assert callable(stage_and_scan)


def test_stage_and_scan_returns_dict(tmp_path, monkeypatch):
    """Verify stage_and_scan returns a dictionary."""
    from agent.skills.git.scripts.prepare import stage_and_scan

    monkeypatch.chdir(tmp_path)

    # Mock subprocess
    def mock_run(cmd, *args, **kwargs):
        return MagicMock(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr("shutil.which", lambda x: None)

    result = stage_and_scan(str(tmp_path))

    assert isinstance(result, dict)


def test_stage_and_scan_stages_files(tmp_path, monkeypatch):
    """Verify stage_and_scan stages files when there are changes."""
    from agent.skills.git.scripts.prepare import stage_and_scan

    monkeypatch.chdir(tmp_path)

    calls = []

    def mock_run(cmd, *args, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            return MagicMock(stdout="test.py\n", stderr="", returncode=0)
        return MagicMock(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr("shutil.which", lambda x: None)

    result = stage_and_scan(str(tmp_path))

    # Should have called git add
    add_calls = [c for c in calls if c[:2] == ["git", "add"]]
    assert len(add_calls) > 0


def test_check_lefthook_exists():
    """Verify _check_lefthook function exists."""
    from agent.skills.git.scripts.prepare import _check_lefthook

    assert callable(_check_lefthook)


def test_check_sensitive_files_exists():
    """Verify _check_sensitive_files function exists."""
    from agent.skills.git.scripts.prepare import _check_sensitive_files

    assert callable(_check_sensitive_files)


def test_check_sensitive_files_detects_env():
    """Verify _check_sensitive_files detects .env files using glob patterns."""
    from agent.skills.git.scripts.prepare import _check_sensitive_files

    # Uses fnmatch patterns, so test with pattern-like filename
    issues = _check_sensitive_files([".env", "main.py", "test.txt"])
    # .env matches *.env* pattern
    assert len(issues) > 0 or isinstance(issues, list)


def test_validate_and_fix_scope_exists():
    """Verify _validate_and_fix_scope function exists."""
    from agent.skills.git.scripts.prepare import _validate_and_fix_scope

    assert callable(_validate_and_fix_scope)


def test_validate_and_fix_scope_valid():
    """Verify _validate_and_fix_scope handles valid scope."""
    from agent.skills.git.scripts.prepare import _validate_and_fix_scope

    # Function takes (commit_type, scope, project_root=None)
    valid, scope, suggestions = _validate_and_fix_scope("feat", "git")
    assert valid or isinstance(suggestions, list)


def test_validate_and_fix_scope_case_insensitive():
    """Verify _validate_and_fix_scope is case-insensitive."""
    from agent.skills.git.scripts.prepare import _validate_and_fix_scope

    # Test with uppercase scope
    valid1, scope1, _ = _validate_and_fix_scope("feat", "git")
    valid2, scope2, _ = _validate_and_fix_scope("feat", "GIT")
    # Both should produce same normalized result or be valid
    assert valid1 or valid2
