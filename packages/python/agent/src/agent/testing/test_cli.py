"""
test_cli.py - CLI Module Tests

Tests for the modular CLI structure:
- agent/cli/__init__.py: Main exports
- agent/cli/app.py: Typer application and configuration
- agent/cli/console.py: Console and output formatting
- agent/cli/runner.py: Skill execution logic
- agent/cli/omni_loop.py: CCA Runtime Integration
- agent/cli/commands/: Command submodules

Usage:
    cd packages/python/agent/src/agent
    uv run python testing/test_cli.py

Debugging Tips:
    # Run with verbose output
    python -c "from testing.test_cli import *; test_console_output()"

    # Test specific format handling
    python -c "
    from agent.cli.console import print_result
    # Test CommandResult format (from @skill_command)
    class MockResult:
        data = {'content': 'test', 'metadata': {'url': 'example.com'}}
    print_result(MockResult(), is_tty=True)
    "
"""

from __future__ import annotations

import sys
import json
import io
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout
from typing import Any


# =============================================================================
# Test Result Classes
# =============================================================================


class TestResult:
    """Collect test results for summary."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def record(self, name: str, success: bool, error: str | None = None):
        if success:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            self.failures.append((name, error))
            print(f"  [FAIL] {name}: {error}")


# =============================================================================
# Module Import Tests
# =============================================================================


def test_module_exports():
    """Test that CLI module exports are available."""
    print("\n[Module Exports]")

    from agent.cli import app, main, err_console, run_skills

    assert app is not None, "app export is None"
    assert main is not None, "main export is None"
    assert err_console is not None, "err_console export is None"
    assert callable(run_skills), "run_skills is not callable"

    print("  All module exports available")
    return True


def test_app_module():
    """Test app module exports."""
    print("\n[App Module]")

    from agent.cli.app import app, main

    assert app is not None, "app is None"
    assert callable(main), "main is not callable"

    print("  App module exports correct")
    return True


def test_console_module():
    """Test console module exports."""
    print("\n[Console Module]")

    from agent.cli.console import (
        err_console,
        cli_log_handler,
        print_result,
        print_metadata_box,
    )

    assert err_console is not None, "err_console is None"
    assert callable(cli_log_handler), "cli_log_handler is not callable"
    assert callable(print_result), "print_result is not callable"
    assert callable(print_metadata_box), "print_metadata_box is not callable"

    print("  Console module exports correct")
    return True


def test_runner_module():
    """Test runner module exports."""
    print("\n[Runner Module]")

    from agent.cli.runner import run_skills

    assert callable(run_skills), "run_skills is not callable"

    print("  Runner module exports correct")
    return True


def test_commands_submodules():
    """Test command submodules are importable."""
    print("\n[Commands Submodules]")

    from agent.cli.commands.skill import skill_app
    from agent.cli.commands.run import run_app
    from agent.cli.commands.route import route_app
    from agent.cli.commands.ingest import ingest_app
    from agent.cli.commands import register_mcp_command

    assert skill_app is not None, "skill_app is None"
    assert callable(register_mcp_command), "register_mcp_command is not callable"
    assert run_app is not None, "run_app is None"
    assert route_app is not None, "route_app is None"
    assert ingest_app is not None, "ingest_app is None"

    print("  All command submodules importable")
    return True


# =============================================================================
# Module Structure Tests
# =============================================================================


def test_module_structure():
    """Verify the modular CLI structure exists."""
    print("\n[Module Structure]")

    cli_dir = Path(__file__).parent.parent / "cli"
    assert cli_dir.exists(), f"cli directory not found: {cli_dir}"

    expected_files = [
        "__init__.py",
        "app.py",
        "console.py",
        "runner.py",
        "omni_loop.py",
    ]

    expected_dirs = ["commands"]

    for file in expected_files:
        file_path = cli_dir / file
        assert file_path.exists(), f"Required file missing: {file_path}"

    for dir_name in expected_dirs:
        dir_path = cli_dir / dir_name
        assert dir_path.exists(), f"Required directory missing: {dir_path}"
        assert dir_path.is_dir(), f"{dir_name} is not a directory"

    print("  Module structure verified")
    return True


# =============================================================================
# Console Output Tests
# =============================================================================


def test_cli_log_handler():
    """Test cli_log_handler function."""
    print("\n[CLI Log Handler]")

    from agent.cli.console import cli_log_handler

    captured = io.StringIO()
    with redirect_stderr(captured):
        cli_log_handler("[Test] Hello world")
        cli_log_handler("[Swarm] Test message")
        cli_log_handler("Error: Test error")

    output = captured.getvalue()
    assert "Hello world" in output, "Log message not found"
    assert "🚀" in output, "Swarm prefix not found"
    assert "❌" in output, "Error prefix not found"

    print("  CLI log handler works correctly")
    return True


def test_print_result_dict_format():
    """Test print_result with dict format."""
    print("\n[print_result - Dict Format]")

    from agent.cli.console import print_result

    test_cases = [
        {
            "name": "Basic dict with content",
            "result": {
                "success": True,
                "content": "# Test Heading\nTest content",
                "metadata": {"url": "https://example.com"},
            },
            "expect_content": True,
        },
        {
            "name": "Dict with markdown key",
            "result": {"success": True, "markdown": "**bold** text"},
            "expect_content": True,
        },
        {
            "name": "Empty content",
            "result": {"success": True, "content": "", "metadata": {}},
            "expect_content": False,
        },
    ]

    for tc in test_cases:
        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            print_result(tc["result"], is_tty=False, json_output=False)

        output = stdout_capture.getvalue()
        if tc["expect_content"]:
            assert len(output) > 0, f"No output for {tc['name']}"

    print("  print_result handles dict format correctly")
    return True


def test_print_result_command_result():
    """Test print_result with CommandResult format."""
    print("\n[print_result - CommandResult Format]")

    from agent.cli.console import print_result

    class MockCommandResult:
        def __init__(self, data: Any, error: str | None = None, metadata: dict | None = None):
            self.data = data
            self.error = error
            self.metadata = metadata or {}
            # Compute output for ExecutionResult format
            if isinstance(data, dict):
                self.output = data.get("content", data.get("markdown", ""))
            else:
                self.output = str(data)
            # ExecutionResult attributes (needed because model_dump triggers ExecutionResult path)
            self.success = True
            self.duration_ms = 0.0

        def model_dump(self) -> dict:
            return {
                "output": self.output,
                "success": self.success,
                "duration_ms": self.duration_ms,
                "error": self.error,
            }

        def model_dump_json(self, indent: int = 2) -> str:
            return json.dumps(self.model_dump(), indent=indent)

    test_cases = [
        {
            "name": "CommandResult with content",
            "result": MockCommandResult(
                data={
                    "content": "# Crawled Content",
                    "metadata": {"url": "https://example.com", "title": "Example"},
                }
            ),
            "expect_content": True,
        },
        {
            "name": "CommandResult with string data",
            "result": MockCommandResult(data="Plain string result"),
            "expect_content": True,
        },
    ]

    for tc in test_cases:
        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            print_result(tc["result"], is_tty=False, json_output=False)

        output = stdout_capture.getvalue()
        if tc["expect_content"]:
            assert len(output) > 0, f"No output for {tc['name']}"

    print("  print_result handles CommandResult format correctly")
    return True


def test_print_result_json_mode():
    """Test print_result JSON mode output."""
    print("\n[print_result - JSON Mode]")

    from agent.cli.console import print_result

    class MockExecutionResult:
        def __init__(self, data: dict, success: bool = True, duration_ms: float = 0.0):
            self.data = data
            self.success = success
            self.duration_ms = duration_ms
            self.output = data.get("content", data.get("markdown", ""))
            self.error = None

        def model_dump(self) -> dict:
            return {
                "output": self.output,
                "success": self.success,
                "duration_ms": self.duration_ms,
                "error": self.error,
            }

        def model_dump_json(self, indent: int = 2) -> str:
            return json.dumps(self.model_dump(), indent=indent)

    test_cases = [
        {
            "name": "Dict in pipe mode",
            "result": {"success": True, "data": {"content": "test"}},
            "expect_content": "test",
        },
        {
            "name": "ExecutionResult in JSON mode",
            "result": MockExecutionResult({"content": "test"}),
            "expect_keys": ["output", "success", "duration_ms", "error"],
        },
    ]

    for tc in test_cases:
        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            print_result(tc["result"], is_tty=False, json_output=True)

        output = stdout_capture.getvalue()
        if "expect_content" in tc:
            assert tc["expect_content"] in output, (
                f"Expected content '{tc['expect_content']}' not in output for {tc['name']}"
            )
        if "expect_keys" in tc:
            parsed = json.loads(output)
            for key in tc["expect_keys"]:
                assert key in parsed, f"Key '{key}' not in JSON for {tc['name']}"

    print("  print_result JSON mode works correctly")
    return True


def test_print_metadata_box():
    """Test print_metadata_box function."""
    print("\n[print_metadata_box]")

    from agent.cli.console import print_metadata_box

    captured = io.StringIO()
    with redirect_stderr(captured):
        print_metadata_box({"url": "https://example.com", "title": "Test"})
        print_metadata_box({})

    output = captured.getvalue()
    assert len(output) > 0, "Metadata panel not printed"

    print("  print_metadata_box works correctly")
    return True


def test_console_stderr_configuration():
    """Test err_console is configured for stderr."""
    print("\n[Console Stderr Configuration]")

    from agent.cli.console import err_console

    assert err_console.file.isatty() or err_console.file == sys.stderr

    print("  err_console configured for stderr")
    return True


# =============================================================================
# Command Integration Tests
# =============================================================================


def test_skill_command_group():
    """Test skill command group is properly configured."""
    print("\n[Skill Command Group]")

    from agent.cli.commands.skill import skill_app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(skill_app, ["--help"])

    assert result.exit_code == 0, f"Skill help failed: {result.output}"
    assert "run" in result.output, "Run command not in help"

    expected_commands = [
        "run",
        "list",
        "discover",
        "info",
        "install",
        "update",
        "test",
        "check",
        "templates",
        "create",
    ]
    for cmd in expected_commands:
        assert cmd in result.output, f"Command '{cmd}' not in skill help"

    print("  Skill command group configured correctly")
    return True


def test_skill_subcommands():
    """Test individual skill subcommands exist."""
    print("\n[Skill Subcommands]")

    from agent.cli.commands.skill import skill_app
    from typer.testing import CliRunner

    runner = CliRunner()

    subcommands = [
        ("list", "List installed skills"),
        ("discover", "Discover skills"),
        ("info", "Show detailed information"),
        ("install", "Install a skill"),
        ("update", "Update an installed skill"),
        ("test", "Test skills"),
        ("check", "Validate skill structure"),
        ("templates", "Manage skill templates"),
        ("create", "Create a new skill"),
    ]

    for cmd, desc in subcommands:
        result = runner.invoke(skill_app, [cmd, "--help"])
        assert result.exit_code == 0, f"{cmd} help failed: {result.output}"
        assert desc.lower() in result.output.lower(), f"{cmd} help missing description"

    print("  All skill subcommands configured correctly")
    return True


def test_cli_help_commands():
    """Test CLI help commands."""
    print("\n[CLI Help Commands]")

    from agent.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()

    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, f"Main help failed: {result.output}"
    assert "omni" in result.output.lower(), "omni not in help output"

    result = runner.invoke(app, ["skill", "--help"])
    assert result.exit_code == 0, f"Skill help failed: {result.output}"
    assert "run" in result.output, "run not in skill help"

    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0, f"MCP help failed: {result.output}"
    assert "--transport" in result.output or "-t" in result.output
    assert "stdio" in result.output
    assert "sse" in result.output

    print("  All help commands work correctly")
    return True


# =============================================================================
# Runner Tests
# =============================================================================


def test_runner_function_exists():
    """Test run_skills function exists and is callable."""
    print("\n[Runner Function]")

    from agent.cli.runner import run_skills

    assert callable(run_skills), "run_skills is not callable"
    assert run_skills.__doc__ is not None, "run_skills has no docstring"

    print("  run_skills function exists and is documented")
    return True


def test_runner_help_command():
    """Test run_skills with help command."""
    print("\n[Runner Help Command]")

    from agent.cli.runner import run_skills
    from agent.cli.console import cli_log_handler

    captured = io.StringIO()
    with redirect_stderr(captured):
        run_skills(["help"], log_handler=cli_log_handler)

    output = captured.getvalue()
    assert "Available Skills" in output or "git" in output.lower()

    print("  run_skills help command works")
    return True


def test_runner_invalid_command():
    """Test run_skills with invalid command format."""
    print("\n[Runner Invalid Command]")

    from agent.cli.runner import run_skills
    from click.exceptions import Exit as ClickExit

    try:
        run_skills(["invalidcommand"])
        assert False, "Should have raised ClickExit"
    except ClickExit as e:
        assert e.exit_code == 1, f"Should exit with code 1, got {e.exit_code}"

    print("  run_skills rejects invalid command format")
    return True


# =============================================================================
# Edge Case Tests
# =============================================================================


def test_print_result_edge_cases():
    """Test print_result with edge cases."""
    print("\n[print_result Edge Cases]")

    from agent.cli.console import print_result

    edge_cases = [None, "", "Plain string"]

    for test_input in edge_cases:
        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            print_result(test_input, is_tty=False, json_output=False)

    print("  print_result handles edge cases correctly")
    return True


# =============================================================================
# Main Test Runner
# =============================================================================


def run_all_tests():
    """Run all CLI module tests."""
    print("=" * 60)
    print("CLI Module Tests")
    print("Modular CLI Architecture")
    print("=" * 60)

    tests = [
        # Module exports
        ("Module Exports", test_module_exports),
        ("App Module", test_app_module),
        ("Console Module", test_console_module),
        ("Runner Module", test_runner_module),
        ("Commands Submodules", test_commands_submodules),
        # Module structure
        ("Module Structure", test_module_structure),
        # Console output
        ("CLI Log Handler", test_cli_log_handler),
        ("print_result - Dict Format", test_print_result_dict_format),
        ("print_result - CommandResult", test_print_result_command_result),
        ("print_result - JSON Mode", test_print_result_json_mode),
        ("print_metadata_box", test_print_metadata_box),
        ("Console Stderr Config", test_console_stderr_configuration),
        # Command integration
        ("Skill Command Group", test_skill_command_group),
        ("Skill Subcommands", test_skill_subcommands),
        ("CLI Help Commands", test_cli_help_commands),
        # Runner
        ("Runner Function", test_runner_function_exists),
        ("Runner Help Command", test_runner_help_command),
        ("Runner Invalid Command", test_runner_invalid_command),
        # Edge cases
        ("print_result Edge Cases", test_print_result_edge_cases),
    ]

    result = TestResult()

    for name, test_func in tests:
        try:
            if test_func():
                result.record(name, True)
            else:
                result.record(name, False, "Test returned False")
        except Exception as e:
            result.record(name, False, str(e))

    print()
    print("=" * 60)
    print(f"Results: {result.passed} passed, {result.failed} failed")
    print("=" * 60)

    if result.failures:
        print("\nFailures:")
        for name, error in result.failures:
            print(f"  - {name}: {error}")

    return result.failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
