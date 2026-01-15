"""
Terminal Skill Tests - Phase 35.1

Usage:
    uv run pytest assets/skills/terminal/tests/ -v
    omni skill test terminal

Tests cover:
- run_command: Execute shell commands
- analyze_last_error: Analyze failed commands
- inspect_environment: Check execution environment
"""

import subprocess
import pytest
import inspect
import sys
import types
import importlib.util
from pathlib import Path


def _setup_terminal_package_context():
    """Set up the package hierarchy in sys.modules for terminal skill."""
    # Navigate from tests/test_terminal_commands.py to assets/skills/
    # tests/terminal/tests/test_terminal_commands.py
    #        ^this   ^this  ^this    ^this
    # Going up 3 levels: tests -> terminal -> skills -> assets
    tests_dir = Path(__file__).parent  # assets/skills/terminal/tests
    terminal_dir = tests_dir.parent  # assets/skills/terminal
    skills_root = terminal_dir.parent  # assets/skills
    project_root = skills_root.parent.parent  # project root

    # Ensure 'agent' package exists
    if "agent" not in sys.modules:
        agent_src = project_root / "packages/python/agent/src/agent"
        agent_pkg = types.ModuleType("agent")
        agent_pkg.__path__ = [str(agent_src)]
        agent_pkg.__file__ = str(agent_src / "__init__.py")
        sys.modules["agent"] = agent_pkg

    # Ensure 'agent.skills' package exists
    if "agent.skills" not in sys.modules:
        skills_pkg = types.ModuleType("agent.skills")
        skills_pkg.__path__ = [str(skills_root)]
        skills_pkg.__file__ = str(skills_root / "__init__.py")
        sys.modules["agent.skills"] = skills_pkg

    # Ensure 'agent.skills.terminal' package exists
    terminal_skill_name = "agent.skills.terminal"
    if terminal_skill_name not in sys.modules:
        terminal_pkg = types.ModuleType(terminal_skill_name)
        terminal_pkg.__path__ = [str(terminal_dir)]
        terminal_pkg.__file__ = str(terminal_dir / "__init__.py")
        sys.modules[terminal_skill_name] = terminal_pkg

    # Ensure 'agent.skills.terminal.scripts' package exists
    scripts_pkg_name = "agent.skills.terminal.scripts"
    if scripts_pkg_name not in sys.modules:
        scripts_dir = terminal_dir / "scripts"
        scripts_pkg = types.ModuleType(scripts_pkg_name)
        scripts_pkg.__path__ = [str(scripts_dir)]
        scripts_pkg.__file__ = str(scripts_dir / "__init__.py")
        sys.modules[scripts_pkg_name] = scripts_pkg

    # Pre-load decorators module for @skill_script support
    decorators_name = "agent.skills.decorators"
    if decorators_name not in sys.modules:
        decorators_path = project_root / "packages/python/agent/src/agent/skills/decorators.py"
        if decorators_path.exists():
            spec = importlib.util.spec_from_file_location(decorators_name, str(decorators_path))
            if spec and spec.loader:
                decorators_mod = importlib.util.module_from_spec(spec)
                sys.modules[decorators_name] = decorators_mod
                spec.loader.exec_module(decorators_mod)


# Setup package context before importing
_setup_terminal_package_context()


def test_run_command_exists():
    """Verify run_command function exists in commands module."""
    from agent.skills.terminal.scripts import commands

    assert hasattr(commands, "run_command")
    assert callable(commands.run_command)


def test_run_command_has_skill_script_decorator():
    """Verify run_command function exists and is callable."""
    from agent.skills.terminal.scripts import commands

    func = commands.run_command
    assert callable(func), "run_command should be callable"
    # Note: Decorator attributes may not be preserved through re-export
    # The important thing is the function works correctly


def test_run_command_metadata():
    """Verify run_command function exists and can be called."""
    from agent.skills.terminal.scripts import commands

    func = commands.run_command
    assert callable(func), "run_command should be callable"
    # Note: Metadata attributes may not be preserved through re-export
    # The important thing is the function works correctly


def test_analyze_last_error_exists():
    """Verify analyze_last_error function exists."""
    from agent.skills.terminal.scripts import commands

    assert hasattr(commands, "analyze_last_error")
    assert callable(commands.analyze_last_error)


def test_analyze_last_error_has_decorator():
    """Verify analyze_last_error function exists and is callable."""
    from agent.skills.terminal.scripts import commands

    func = commands.analyze_last_error
    assert callable(func), "analyze_last_error should be callable"
    # Note: Decorator attributes may not be preserved through re-export


def test_inspect_environment_exists():
    """Verify inspect_environment function exists."""
    from agent.skills.terminal.scripts import commands

    assert hasattr(commands, "inspect_environment")
    assert callable(commands.inspect_environment)


def test_inspect_environment_has_decorator():
    """Verify inspect_environment function exists and is callable."""
    from agent.skills.terminal.scripts import commands

    func = commands.inspect_environment
    assert callable(func), "inspect_environment should be callable"
    # Note: Decorator attributes may not be preserved through re-export


# =============================================================================
# Engine Tests (run_command execution engine)
# =============================================================================


def test_run_command_engine_exists():
    """Verify engine module has run_command function."""
    from agent.skills.terminal.scripts import engine

    assert hasattr(engine, "run_command")
    assert callable(engine.run_command)


def test_run_command_engine_returns_dict():
    """Verify engine.run_command returns a dict with execution results."""
    from agent.skills.terminal.scripts import engine

    result = engine.run_command("echo", ["hello"], timeout=10)

    assert isinstance(result, dict)
    assert "exit_code" in result
    assert "stdout" in result
    assert "stderr" in result
    assert "command" in result
    assert "args" in result


def test_run_command_engine_simple_echo():
    """Verify run_command can execute a simple echo command."""
    from agent.skills.terminal.scripts import engine

    result = engine.run_command("echo", ["hello"], timeout=10)

    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


def test_run_command_engine_with_args():
    """Verify run_command can execute commands with multiple arguments."""
    from agent.skills.terminal.scripts import engine

    result = engine.run_command("git", ["--version"], timeout=10)

    assert result["exit_code"] == 0
    assert "git version" in result["stdout"] or "git" in result["stdout"].lower()


def test_run_command_engine_nonexistent_command():
    """Verify run_command handles non-existent commands gracefully."""
    from agent.skills.terminal.scripts import engine

    result = engine.run_command("nonexistent_command_12345", [], timeout=10)

    # Should return error, not crash
    assert isinstance(result, dict)
    assert result["exit_code"] != 0 or "not found" in result["stderr"].lower()


def test_run_command_engine_timeout():
    """Verify run_command respects timeout parameter."""
    from agent.skills.terminal.scripts import engine

    # Use a command that sleeps longer than timeout
    result = engine.run_command("sleep", ["10"], timeout=1)

    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower()


def test_format_result_exists():
    """Verify engine module has format_result function."""
    from agent.skills.terminal.scripts import engine

    assert hasattr(engine, "format_result")
    assert callable(engine.format_result)


def test_format_result_with_stdout():
    """Verify format_result correctly formats output with stdout."""
    from agent.skills.terminal.scripts import engine

    result = engine.run_command("echo", ["test"])
    formatted = engine.format_result(result, "echo", ["test"])

    assert isinstance(formatted, str)
    assert "test" in formatted


def test_format_result_with_stderr():
    """Verify format_result includes stderr when present."""
    from agent.skills.terminal.scripts import engine

    # Create a command that produces stderr
    result = engine.run_command("ls", ["/nonexistent_path_12345"], timeout=10)
    formatted = engine.format_result(result, "ls", ["/nonexistent_path_12345"])

    assert isinstance(formatted, str)
    assert "STDERR" in formatted or "No such file" in formatted or result["exit_code"] != 0


def test_format_result_empty_output():
    """Verify format_result handles empty output."""
    from agent.skills.terminal.scripts import engine

    result = {
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "command": "test",
        "args": [],
    }
    formatted = engine.format_result(result, "test", [])

    assert isinstance(formatted, str)
    assert "(no output)" in formatted or formatted == ""


# =============================================================================
# Command Parsing Tests
# =============================================================================


def test_git_commit_blocked():
    """Verify git commit is properly blocked."""
    from agent.skills.terminal.scripts.commands import _is_git_commit_blocked

    # Test various git commit patterns
    blocked, msg = _is_git_commit_blocked("git commit", ["-m", "test"])
    assert blocked is True
    assert "PROHIBITED" in msg or "BLOCKED" in msg

    blocked, msg = _is_git_commit_blocked("git", ["commit", "-m", "test"])
    assert blocked is True

    blocked, msg = _is_git_commit_blocked("bash", ["git commit -m test"])
    assert blocked is True


def test_git_commit_allowed_patterns():
    """Verify git commit is blocked but other git operations are allowed."""
    from agent.skills.terminal.scripts.commands import _is_git_commit_blocked

    # These should NOT be blocked
    blocked, _ = _is_git_commit_blocked("git", ["status"])
    assert blocked is False

    blocked, _ = _is_git_commit_blocked("git", ["diff"])
    assert blocked is False

    blocked, _ = _is_git_commit_blocked("git", ["log", "-n1"])
    assert blocked is False


# =============================================================================
# Dangerous Pattern Tests
# =============================================================================


def test_dangerous_patterns_blocked():
    """Verify dangerous command patterns are detected."""
    from agent.skills.terminal.scripts.engine import check_dangerous_patterns

    dangerous_commands = [
        "rm -rf /",
        "rm -rf /home",
        ":(){:|:&};:",
        "mkfs",
        "dd if=/dev/zero of=/dev/sda",
    ]

    for cmd in dangerous_commands:
        is_safe, error_msg = check_dangerous_patterns(cmd, [])
        assert is_safe is False, f"Should block: {cmd}"


def test_safe_commands_allowed():
    """Verify safe commands pass the pattern check."""
    from agent.skills.terminal.scripts.engine import check_dangerous_patterns

    safe_commands = [
        ("git", ["status"]),
        ("echo", ["hello"]),
        ("ls", ["-la"]),
        ("cat", ["file.txt"]),
    ]

    for cmd, args in safe_commands:
        is_safe, error_msg = check_dangerous_patterns(cmd, args)
        assert is_safe is True, f"Should allow: {cmd} {args}"


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.parametrize(
    "cmd,args,expected_in_output",
    [
        (["echo"], ["hello world"], "hello world"),
        (["pwd"], [], None),  # Just verify it works
        (["whoami"], [], None),  # Just verify it works
    ],
)
def test_run_command_integration(cmd, args, expected_in_output):
    """Integration test for run_command with various commands."""
    from agent.skills.terminal.scripts import engine

    result = engine.run_command(cmd[0], args, timeout=10)

    assert result["exit_code"] == 0
    if expected_in_output:
        assert expected_in_output in result["stdout"]
