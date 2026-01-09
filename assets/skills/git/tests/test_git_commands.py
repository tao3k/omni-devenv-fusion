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
