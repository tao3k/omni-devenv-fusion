"""
test_cli.py - CLI Module Tests

Phase 35.2: Modular CLI Testing

Tests for the atomic CLI module structure:
- agent/cli/__init__.py: Main exports (backward compatibility)
- agent/cli/app.py: Typer application and configuration
- agent/cli/console.py: Console and output formatting
- agent/cli/runner.py: Skill execution logic
- agent/cli/commands/__init__.py: Commands package
- agent/cli/commands/skill.py: Skill command group

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
import subprocess
import json
import io
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from typing import Any, Optional


# =============================================================================
# Test Result Classes
# =============================================================================


class TestResult:
    """Collect test results for summary."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def record(self, name: str, success: bool, error: Optional[str] = None):
        if success:
            self.passed += 1
            print(f"  ✓ {name}")
        else:
            self.failed += 1
            self.failures.append((name, error))
            print(f"  ✗ {name}: {error}")


# =============================================================================
# Module Import Tests
# =============================================================================


def test_module_imports():
    """Test that all CLI modules can be imported without errors."""
    print("\n[Module Imports]")

    # Test backward-compatible exports
    from agent.cli import app, main, err_console

    # Test individual module imports
    from agent.cli.app import app, main
    from agent.cli.console import (
        err_console,
        cli_log_handler,
        print_result,
        print_metadata_box,
    )
    from agent.cli.commands.skill import skill_app
    from agent.cli.runner import run_skills

    # Verify exports are not None
    assert app is not None, "app export is None"
    assert main is not None, "main export is None"
    assert err_console is not None, "err_console export is None"
    assert skill_app is not None, "skill_app is None"
    assert callable(run_skills), "run_skills is not callable"

    print("  ✓ All modules imported successfully")
    return True


def test_module_structure():
    """Verify the atomic module structure exists."""
    print("\n[Module Structure]")

    from pathlib import Path

    cli_dir = Path(__file__).parent.parent / "cli"
    assert cli_dir.exists(), f"cli directory not found: {cli_dir}"

    expected_files = [
        "__init__.py",
        "app.py",
        "console.py",
        "runner.py",
        "commands/__init__.py",
        "commands/skill.py",
        "commands/mcp.py",
    ]

    for file in expected_files:
        file_path = cli_dir / file
        assert file_path.exists(), f"Required file missing: {file_path}"

    print("  ✓ All atomic module files exist")
    return True


# =============================================================================
# Console Output Tests
# =============================================================================


def test_cli_log_handler():
    """Test cli_log_handler function."""
    print("\n[CLI Log Handler]")

    from agent.cli.console import cli_log_handler, err_console

    # Capture output
    captured = io.StringIO()
    with redirect_stderr(captured):
        cli_log_handler("[Test] Hello world")
        cli_log_handler("[Swarm] Test message")
        cli_log_handler("Error: Test error")

    output = captured.getvalue()
    assert "Hello world" in output, "Log message not found"
    assert "🚀" in output, "Swarm prefix not found"
    assert "❌" in output, "Error prefix not found"

    print("  ✓ CLI log handler works correctly")
    return True


def test_print_result_dict_format():
    """Test print_result with dict format (from isolation.py)."""
    print("\n[print_result - Dict Format]")

    from agent.cli.console import print_result

    # Test dict format: {'content': '...', 'metadata': {...}}
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

    print("  ✓ print_result handles dict format correctly")
    return True


def test_print_result_command_result():
    """Test print_result with CommandResult format (from @skill_command)."""
    print("\n[print_result - CommandResult Format]")

    from agent.cli.console import print_result

    # Mock CommandResult object (simulates @skill_command decorator output)
    class MockCommandResult:
        def __init__(self, data: Any, error: Optional[str] = None, metadata: Optional[dict] = None):
            self.data = data
            self.error = error
            self.metadata = metadata or {}

        def model_dump(self):
            return {"data": self.data, "error": self.error, "metadata": self.metadata}

        def model_dump_json(self, indent: int = 2):
            return json.dumps(self.model_dump(), indent=indent)

    # Test CommandResult with dict data
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

    print("  ✓ print_result handles CommandResult format correctly")
    return True


def test_print_result_json_mode():
    """Test print_result JSON mode output."""
    print("\n[print_result - JSON Mode]")

    from agent.cli.console import print_result

    # Mock CommandResult with model_dump method
    class MockCommandResult:
        def __init__(self, data: dict):
            self.data = data

        def model_dump(self):
            return {"data": self.data}

        def model_dump_json(self, indent: int = 2):
            return json.dumps(self.model_dump(), indent=indent)

    test_cases = [
        {
            "name": "Dict in JSON mode",
            "result": {"success": True, "data": {"content": "test"}},
            "expect_keys": ["success", "data"],
        },
        {
            "name": "CommandResult in JSON mode",
            "result": MockCommandResult({"content": "test"}),
            "expect_keys": ["data"],
        },
    ]

    for tc in test_cases:
        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            print_result(tc["result"], is_tty=False, json_output=True)

        output = stdout_capture.getvalue()
        parsed = json.loads(output)
        for key in tc["expect_keys"]:
            assert key in parsed, f"Key '{key}' not in JSON for {tc['name']}"

    print("  ✓ print_result JSON mode works correctly")
    return True


def test_print_metadata_box():
    """Test print_metadata_box function."""
    print("\n[print_metadata_box]")

    from agent.cli.console import print_metadata_box, err_console

    # Capture stderr output
    captured = io.StringIO()
    with redirect_stderr(captured):
        # Test with metadata dict
        print_metadata_box({"url": "https://example.com", "title": "Test"})
        # Test with empty dict (should not print)
        print_metadata_box({})

    output = captured.getvalue()
    assert len(output) > 0, "Metadata panel not printed"

    print("  ✓ print_metadata_box works correctly")
    return True


# =============================================================================
# Command Integration Tests
# =============================================================================


def test_skill_command_group():
    """Test skill command group is properly configured with all subcommands."""
    print("\n[Skill Command Group]")

    from agent.cli.commands.skill import skill_app
    from typer.testing import CliRunner

    runner = CliRunner()

    # Test skill run help
    result = runner.invoke(skill_app, ["--help"])
    assert result.exit_code == 0, f"Skill help failed: {result.output}"
    assert "run" in result.output, "Run command not in help"

    # Verify all subcommands are registered
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

    print("  ✓ Skill command group configured correctly with all commands")
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

    print("  ✓ All skill subcommands configured correctly")
    return True


def test_cli_help_commands():
    """Test CLI help commands via Typer test runner."""
    print("\n[CLI Help Commands]")

    from agent.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()

    # Test main help
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, f"Main help failed: {result.output}"
    assert "omni" in result.output.lower(), "omni not in help output"

    # Test skill help
    result = runner.invoke(app, ["skill", "--help"])
    assert result.exit_code == 0, f"Skill help failed: {result.output}"
    assert "run" in result.output, "run not in skill help"

    # Test mcp help with transport options
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0, f"MCP help failed: {result.output}"
    assert "--transport" in result.output or "-t" in result.output, "transport option not in help"
    assert "stdio" in result.output, "stdio option not in help"
    assert "sse" in result.output, "sse option not in help"
    assert "--port" in result.output or "-p" in result.output, "port option not in help"

    print("  ✓ All help commands work correctly")
    return True


def test_cli_entry_point():
    """Test CLI entry point via subprocess."""
    print("\n[CLI Entry Point]")

    # Test via uv run
    result = subprocess.run(
        ["uv", "run", "python", "-c", "from agent.cli import main; main()", "--help"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent.parent),
        timeout=30,
    )

    assert result.returncode == 0, f"CLI help failed: {result.stderr}"
    assert "omni" in result.stdout.lower() or "Omni" in result.stdout

    print("  ✓ CLI entry point works correctly")
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

    print("  ✓ run_skills function exists and is documented")
    return True


def test_runner_help_command():
    """Test run_skills with help command."""
    print("\n[Runner Help Command]")

    from agent.cli.runner import run_skills
    from agent.cli.console import cli_log_handler

    # Capture stderr for log output
    captured = io.StringIO()
    with redirect_stderr(captured):
        # Help command should list available skills
        run_skills(["help"], log_handler=cli_log_handler)

    output = captured.getvalue()
    assert "Available Skills" in output or "git" in output.lower()

    print("  ✓ run_skills help command works")
    return True


def test_runner_invalid_command():
    """Test run_skills with invalid command format."""
    print("\n[Runner Invalid Command]")

    from agent.cli.runner import run_skills
    from click.exceptions import Exit as ClickExit

    # Test without dot separator (should raise Click Exit)
    try:
        run_skills(["invalidcommand"])
        assert False, "Should have raised ClickExit"
    except ClickExit as e:
        # ClickExit has exit_code attribute
        assert e.exit_code == 1, f"Should exit with code 1, got {e.exit_code}"

    print("  ✓ run_skills rejects invalid command format")
    return True


# =============================================================================
# Edge Case Tests
# =============================================================================


def test_print_result_edge_cases():
    """Test print_result with edge cases."""
    print("\n[print_result Edge Cases]")

    from agent.cli.console import print_result

    edge_cases = [
        ("None result", None),
        ("Empty string", ""),
        ("Plain string", "Just a string"),
    ]

    for name, test_input in edge_cases:
        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            print_result(test_input, is_tty=False, json_output=False)

    print("  ✓ print_result handles edge cases correctly")
    return True


def test_console_stderr_configuration():
    """Test err_console is configured for stderr."""
    print("\n[Console Stderr Configuration]")

    from agent.cli.console import err_console

    # Verify err_console is configured for stderr
    assert err_console.file.isatty() or err_console.file == sys.stderr

    print("  ✓ err_console configured for stderr")
    return True


# =============================================================================
# Main Test Runner
# =============================================================================


def run_all_tests():
    """Run all CLI module tests."""
    print("=" * 60)
    print("CLI Module Tests")
    print("Phase 35.2: Modular CLI Architecture")
    print("=" * 60)
    print()

    tests = [
        # Module structure
        ("Module Imports", test_module_imports),
        ("Module Structure", test_module_structure),
        # Console output
        ("CLI Log Handler", test_cli_log_handler),
        ("print_result - Dict Format", test_print_result_dict_format),
        ("print_result - CommandResult", test_print_result_command_result),
        ("print_result - JSON Mode", test_print_result_json_mode),
        ("print_metadata_box", test_print_metadata_box),
        # Command integration
        ("Skill Command Group", test_skill_command_group),
        ("Skill Subcommands", test_skill_subcommands),
        ("CLI Help Commands", test_cli_help_commands),
        ("CLI Entry Point", test_cli_entry_point),
        # Runner
        ("Runner Function", test_runner_function_exists),
        ("Runner Help Command", test_runner_help_command),
        ("Runner Invalid Command", test_runner_invalid_command),
        # Edge cases
        ("print_result Edge Cases", test_print_result_edge_cases),
        ("Console Stderr Config", test_console_stderr_configuration),
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
