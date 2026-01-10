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
