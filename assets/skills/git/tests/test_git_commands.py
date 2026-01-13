"""
Git Skill Tests - Zero Configuration (Phase 35.1)

Usage:
    def test_git_status(git):  # 'git' fixture auto-injected
        assert git.status().success

No conftest.py, no imports needed!
"""

import subprocess
import pytest
import inspect
import re
from unittest.mock import MagicMock


def test_status_exists(git):
    assert hasattr(git, "status")
    assert callable(git.status)


def test_branch_exists(git):
    assert hasattr(git, "branch")
    assert callable(git.branch)


def test_log_exists(git):
    assert hasattr(git, "log")
    assert callable(git.log)


def test_diff_exists(git):
    assert hasattr(git, "diff")
    assert callable(git.diff)


def test_prepare_commit_exists(git):
    """Verify prepare_commit command exists."""
    assert hasattr(git, "prepare_commit")
    assert callable(git.prepare_commit)


def test_commit_exists(git):
    """Verify commit command exists."""
    assert hasattr(git, "commit")
    assert callable(git.commit)


@pytest.mark.parametrize(
    "cmd,args",
    [
        (["git", "status"], ["--porcelain"]),
        (["git", "branch"], ["-a"]),
        (["git", "log"], ["--oneline", "-n3"]),
        (["git", "remote"], ["-v"]),
    ],
)
def test_git_command(project_root, cmd, args):
    result = subprocess.run(cmd + args, capture_output=True, text=True, cwd=project_root)
    assert result.returncode == 0


def test_commands_have_metadata(git):
    for name, func in inspect.getmembers(git, inspect.isfunction):
        if hasattr(func, "_is_skill_command"):
            assert hasattr(func, "_skill_config")
            config = func._skill_config
            assert "name" in config
            assert "category" in config


def test_tools_py_has_commands(git):
    commands = [
        name
        for name, func in inspect.getmembers(git, inspect.isfunction)
        if hasattr(func, "_is_skill_command")
    ]
    assert len(commands) > 0


# ==============================================================================
# Commit Message Parsing Tests (Phase 35.3)
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
# Scope Validation Tests (Phase 35.3)
# ==============================================================================


def test_validate_and_fix_scope_function_exists(git):
    """Verify scope validation function exists in prepare module."""
    from agent.skills.git.scripts import prepare as prepare_mod

    assert hasattr(prepare_mod, "_validate_and_fix_scope")
    assert callable(prepare_mod._validate_and_fix_scope)


def test_get_cog_scopes_returns_list(git):
    """Verify _get_cog_scopes returns a list of scopes."""
    from agent.skills.git.scripts.prepare import _get_cog_scopes

    scopes = _get_cog_scopes()

    assert isinstance(scopes, list)
    # Should have some common scopes from cog.toml
    if scopes:
        assert any(s in scopes for s in ["git", "docs", "agent"])


# ==============================================================================
# Template Rendering Tests (Phase 35.3)
# ==============================================================================


def test_render_commit_message_exists(git):
    """Verify render_commit_message function exists."""
    from agent.skills.git.scripts import rendering

    assert hasattr(rendering, "render_commit_message")


def test_render_commit_message_returns_string(git):
    """Verify render_commit_message returns formatted string."""
    from agent.skills.git.scripts.rendering import render_commit_message

    result = render_commit_message(
        subject="feat(git): test feature",
        body="- test item 1\n- test item 2",
        verified=True,
        checks=["lefthook passed"],
        status="ready",
    )

    assert isinstance(result, str)
    assert "feat(git): test feature" in result


def test_render_workflow_result_xml_format(git):
    """Verify render_workflow_result returns XML-like format."""
    from agent.skills.git.scripts.rendering import render_workflow_result

    result = render_workflow_result(
        intent="prepare_commit",
        success=True,
        message="Commit preparation completed",
        details={"has_staged": "True", "staged_file_count": "5"},
    )

    assert isinstance(result, str)
    assert "<workflow_result>" in result
    assert "<intent>prepare_commit</intent>" in result
    assert "<success>true</success>" in result


def test_render_commit_message_with_security_guard(git):
    """Verify commit message template includes security guard information."""
    from agent.skills.git.scripts.rendering import render_commit_message

    result = render_commit_message(
        subject="feat(git): test feature",
        body="- test item 1\n- test item 2",
        verified=True,
        checks=["lefthook passed"],
        status="committed",
        security_passed=True,
        security_warning="🛡️ Security Guard Detection - No sensitive files detected. Safe to proceed.",
    )

    assert isinstance(result, str)
    # Should contain security guard info
    assert "security_guard" in result or "Security Guard" in result
    assert "true" in result.lower()  # security_passed = true
    assert "🛡️" in result or "Passed" in result


def test_render_commit_message_security_warning(git):
    """Verify commit message template handles security warning."""
    from agent.skills.git.scripts.rendering import render_commit_message

    result = render_commit_message(
        subject="fix: bug fix",
        body="Fixed the issue",
        verified=True,
        checks=["test passed"],
        status="committed",
        security_passed=False,
        security_warning="⚠️ Detected sensitive files: .env, .credentials",
    )

    assert isinstance(result, str)
    # Should contain security warning
    assert "security_guard" in result or "Detected" in result
    assert "false" in result.lower()  # security_passed = false


# ==============================================================================
# Cog Scopes Regex Tests (Phase 35.3)
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
# Conservative Staging Tests (Phase 36.8)
# ==============================================================================


def test_stage_and_scan_preserves_staged_files(git, tmp_path, monkeypatch):
    """Verify stage_and_scan preserves already staged files."""
    from agent.skills.git.scripts.prepare import stage_and_scan

    # Setup: Create a file and stage it
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")

    monkeypatch.chdir(tmp_path)

    # Mock subprocess to track calls
    calls = []
    original_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            # Return already staged file
            return MagicMock(stdout="test.txt\n", stderr="", returncode=0)
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)

    # Mock shutil.which to return None (no lefthook)
    monkeypatch.setattr("shutil.which", lambda x: None)

    result = stage_and_scan(str(tmp_path))

    # Verify git add was called with the staged file
    add_calls = [c for c in calls if c[:2] == ["git", "add"]]
    assert any("test.txt" in str(c) for c in add_calls)


def test_stage_and_scan_does_not_stage_untracked(git, tmp_path, monkeypatch):
    """Verify stage_and_scan does NOT stage untracked files."""
    from agent.skills.git.scripts.prepare import stage_and_scan

    # Setup: Create only untracked files (no existing staging)
    untracked_file = tmp_path / "untracked.txt"
    untracked_file.write_text("new file")

    monkeypatch.chdir(tmp_path)

    # Mock subprocess
    calls = []
    original_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            return MagicMock(stdout="", stderr="", returncode=0)
        if cmd[:2] == ["git", "diff"] and "--name-only" in cmd:
            # No modified tracked files
            return MagicMock(stdout="", stderr="", returncode=0)
        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr("shutil.which", lambda x: None)

    result = stage_and_scan(str(tmp_path))

    # Verify NO git add was called for untracked files
    add_calls = [c for c in calls if c[:2] == ["git", "add"]]
    assert len(add_calls) == 0, "Should not stage untracked files"


def test_stage_and_scan_restages_after_lefthook(git, tmp_path, monkeypatch):
    """Verify stage_and_scan re-stages files that lefthook unstaged."""
    from agent.skills.git.scripts.prepare import stage_and_scan

    # Setup: Create tracked file and stage it
    test_file = tmp_path / "tracked.py"
    test_file.write_text("print('hello')")

    monkeypatch.chdir(tmp_path)

    # Track the file first
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path)

    calls = []
    original_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        calls.append(cmd)

        # First call: initially staged
        if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            return MagicMock(stdout="tracked.py\n", stderr="", returncode=0)

        # Lefthook runs and reformats file (now it's unstaged)
        if cmd[0] == "lefthook":
            # Simulate lefthook reformatting file
            test_file.write_text("print('hello world')")
            return MagicMock(stdout="formatted tracked.py", stderr="", returncode=0)

        # After lefthook: file is modified but not staged
        if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            return MagicMock(stdout="", stderr="", returncode=0)

        # Get modified files
        if cmd[:2] == ["git", "diff"] and "--name-only" in cmd:
            return MagicMock(stdout="tracked.py\n", stderr="", returncode=0)

        return original_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr("shutil.which", lambda x: "lefthook")

    result = stage_and_scan(str(tmp_path))

    # Verify file was re-staged after lefthook
    add_calls = [c for c in calls if c[:2] == ["git", "add"]]
    # Should have at least one add call for the re-staged file
    assert len(add_calls) > 0


def test_stage_and_scan_uses_diff_filter_acm(git, tmp_path, monkeypatch):
    """Verify stage_and_scan uses --diff-filter=ACM for tracked files only."""
    from agent.skills.git.scripts.prepare import stage_and_scan

    monkeypatch.chdir(tmp_path)

    # Mock subprocess to check for --diff-filter flag
    calls = []

    def mock_run(cmd, *args, **kwargs):
        calls.append(cmd)

        if "--diff-filter" in " ".join(cmd):
            # Verify ACM flag is used (Added, Changed, Modified)
            assert "ACM" in cmd or "--diff-filter=ACM" in cmd

        if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            return MagicMock(stdout="", stderr="", returncode=0)
        if cmd[:2] == ["git", "diff"] and "--name-only" in cmd:
            return MagicMock(stdout="", stderr="", returncode=0)

        return MagicMock(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr("shutil.which", lambda x: None)

    stage_and_scan(str(tmp_path))

    # Verify --diff-filter=ACM was used
    diff_filter_calls = [c for c in calls if "--diff-filter" in " ".join(c)]
    assert len(diff_filter_calls) > 0, "Should use --diff-filter=ACM"


def test_prepare_commit_conservative_staging(git, tmp_path, monkeypatch):
    """Verify prepare_commit uses conservative staging (not git add .)."""
    from agent.skills.git.scripts.prepare import prepare_commit

    monkeypatch.chdir(tmp_path)

    # Create and track a file
    test_file = tmp_path / "test.py"
    test_file.write_text("x = 1")
    subprocess.run(["git", "add", "test.py"], cwd=tmp_path)

    # Create untracked file that should NOT be staged
    untracked = tmp_path / "new_untracked.txt"
    untracked.write_text("should not be staged")

    calls = []

    def mock_run(cmd, *args, **kwargs):
        calls.append(cmd)

        if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            return MagicMock(stdout="test.py\n", stderr="", returncode=0)

        if cmd[:2] == ["git", "diff"] and "--name-only" in cmd:
            return MagicMock(stdout="", stderr="", returncode=0)

        return MagicMock(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr("shutil.which", lambda x: None)

    result = prepare_commit(project_root=tmp_path)

    # Verify NO `git add .` was called
    add_dot_calls = [c for c in calls if c == ["git", "add", "."] or c == ["git", "add", "."]]
    assert len(add_dot_calls) == 0, "Should NOT use 'git add .'"

    # Verify specific files were added instead
    add_calls = [c for c in calls if c[:2] == ["git", "add"]]
    assert len(add_calls) > 0, "Should use 'git add <file>' for specific files"


def test_prepare_commit_handles_lefthook_reformat(git, tmp_path, monkeypatch):
    """Verify prepare_commit re-stages files after lefthook reformats them."""
    from agent.skills.git.scripts.prepare import prepare_commit

    monkeypatch.chdir(tmp_path)

    # Initialize git repo first
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    # Create and stage a file
    test_file = tmp_path / "format_me.py"
    test_file.write_text("x=1")
    subprocess.run(["git", "add", "format_me.py"], cwd=tmp_path)

    lefthook_ran = False
    call_count = 0
    calls = []

    def mock_run(cmd, *args, **kwargs):
        nonlocal lefthook_ran, call_count
        call_count += 1
        calls.append(cmd)

        # First git diff --cached: file is staged
        if call_count == 1 and cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            return MagicMock(stdout="format_me.py\n", stderr="", returncode=0)

        # Lefthook runs and reformats file
        if cmd[0] == "lefthook":
            lefthook_ran = True
            test_file.write_text("x = 1  # formatted")
            return MagicMock(stdout="Formatted 1 file", stderr="", returncode=0)

        # After lefthook: git diff --cached returns empty (file was unstaged by format)
        if cmd[:2] == ["git", "diff"] and "--cached" in cmd:
            return MagicMock(stdout="", stderr="", returncode=0)

        return MagicMock(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr("shutil.which", lambda x: "lefthook" if x == "lefthook" else None)

    result = prepare_commit(project_root=tmp_path)

    # Verify lefthook ran
    assert lefthook_ran, "Lefthook should have run"

    # Verify file was re-staged after lefthook
    # Should have: 1) initial staging, 2) re-staging after lefthook
    add_calls = [c for c in calls if c[:2] == ["git", "add"]]
    assert len(add_calls) >= 2, (
        f"File should be staged initially and re-staged after lefthook. Got: {add_calls}"
    )
