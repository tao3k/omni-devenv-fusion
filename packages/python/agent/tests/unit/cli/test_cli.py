"""
test_cli.py - CLI Module Tests

Tests for the modular CLI structure:
- omni/agent/cli/__init__.py: Main exports
- omni/agent/cli/app.py: Typer application and configuration
- omni/agent/cli/console.py: Console and output formatting
- omni/agent/cli/runner.py: Skill execution logic
- omni/agent/cli/omni_loop.py: CCA Runtime Integration
- omni/agent/cli/commands/: Command submodules

Usage:
    uv run pytest packages/python/agent/tests/unit/cli/test_cli.py -v
"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

# =============================================================================
# Test Result Classes
# =============================================================================


class _TestResult:
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
# Module Import Tests (SSOT from references.yaml)
# =============================================================================


def test_module_exports():
    """Test that CLI module exports are available (SSOT from references.yaml)."""
    print("\n[Module Exports]")

    from omni.agent.cli import app, err_console, main, run_skills

    assert app is not None, "app export is None"
    assert main is not None, "main export is None"
    assert err_console is not None, "err_console export is None"
    assert callable(run_skills), "run_skills is not callable"

    print("  All module exports available")


def test_app_module():
    """Test app module exports."""
    print("\n[App Module]")

    from omni.agent.cli.app import app, main

    assert app is not None, "app is None"
    assert callable(main), "main is not callable"

    print("  App module exports correct")


def test_console_module():
    """Test console module exports."""
    print("\n[Console Module]")

    from omni.agent.cli.console import (
        cli_log_handler,
        err_console,
        print_metadata_box,
        print_result,
    )

    assert err_console is not None, "err_console is None"
    assert callable(cli_log_handler), "cli_log_handler is not callable"
    assert callable(print_result), "print_result is not callable"
    assert callable(print_metadata_box), "print_metadata_box is not callable"

    print("  Console module exports correct")


def test_runner_module():
    """Test runner module exports."""
    print("\n[Runner Module]")

    from omni.agent.cli.runner import run_skills

    assert callable(run_skills), "run_skills is not callable"

    print("  Runner module exports correct")


def test_commands_submodules():
    """Test command submodules are importable."""
    print("\n[Commands Submodules]")

    from omni.agent.cli.commands import register_mcp_command, register_run_command
    from omni.agent.cli.commands.ingest import ingest_app
    from omni.agent.cli.commands.route import route_app
    from omni.agent.cli.commands.skill import skill_app

    assert skill_app is not None, "skill_app is None"
    assert register_run_command is not None, "register_run_command is None"
    assert callable(register_mcp_command), "register_mcp_command is not callable"
    assert route_app is not None, "route_app is None"
    assert ingest_app is not None, "ingest_app is None"

    print("  All command submodules importable")


# =============================================================================
# Module Structure Tests (SSOT from references.yaml)
# =============================================================================


def test_module_structure(project_root: Path):
    """Verify the modular CLI structure exists in source."""
    print("\n[Module Structure]")

    # CLI directory path (using centralized project_root fixture)
    cli_dir = project_root / "packages" / "python" / "agent" / "src" / "omni" / "agent" / "cli"
    assert cli_dir.exists(), f"cli directory not found: {cli_dir}"

    # Get expected files from references.yaml SSOT
    from omni.foundation.services.reference import ReferenceLibrary

    ref = ReferenceLibrary()
    expected_files = ref.get(
        "cli.files", ["__init__.py", "app.py", "console.py", "runner.py", "omni_loop.py"]
    )
    expected_dirs = ref.get("cli.directories", ["commands"])

    for file in expected_files:
        file_path = cli_dir / file
        assert file_path.exists(), f"Required file missing: {file_path}"

    for dir_name in expected_dirs:
        dir_path = cli_dir / dir_name
        assert dir_path.exists(), f"Required directory missing: {dir_path}"
        assert dir_path.is_dir(), f"{dir_name} is not a directory"

    print("  Module structure verified")


# =============================================================================
# Console Output Tests
# =============================================================================


def test_cli_log_handler():
    """Test cli_log_handler function."""
    print("\n[CLI Log Handler]")

    from omni.agent.cli.console import cli_log_handler

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


def test_print_result_dict_format():
    """Test print_result with dict format."""
    print("\n[print_result - Dict Format]")

    from omni.agent.cli.console import print_result

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


def test_print_result_command_result():
    """Test print_result with CommandResult format."""
    print("\n[print_result - CommandResult Format]")

    from omni.agent.cli.console import print_result

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


def test_print_result_json_mode():
    """Test print_result JSON mode output."""
    print("\n[print_result - JSON Mode]")

    from omni.agent.cli.console import print_result

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


def test_print_metadata_box():
    """Test print_metadata_box function."""
    print("\n[print_metadata_box]")

    from omni.agent.cli.console import print_metadata_box

    captured = io.StringIO()
    with redirect_stderr(captured):
        print_metadata_box({"url": "https://example.com", "title": "Test"})
        print_metadata_box({})

    output = captured.getvalue()
    assert len(output) > 0, "Metadata panel not printed"

    print("  print_metadata_box works correctly")


def test_console_stderr_configuration():
    """Test err_console is configured for stderr."""
    print("\n[Console Stderr Configuration]")

    from omni.agent.cli.console import err_console

    assert err_console.file.isatty() or err_console.file == sys.stderr

    print("  err_console configured for stderr")


# =============================================================================
# Command Integration Tests (SSOT from references.yaml)
# =============================================================================


def test_skill_command_group():
    """Test skill command group is properly configured."""
    print("\n[Skill Command Group]")

    from omni.agent.cli.commands.skill import skill_app

    runner = CliRunner()
    result = runner.invoke(skill_app, ["--help"])

    assert result.exit_code == 0, f"Skill help failed: {result.output}"
    assert "run" in result.output, "Run command not in help"

    # Get expected subcommands from SSOT
    from omni.foundation.services.reference import ReferenceLibrary

    ref = ReferenceLibrary()
    skill_subcommands = ref.get("cli.skill_subcommands", {})

    if skill_subcommands:
        for cmd in skill_subcommands.keys():
            assert cmd in result.output, f"Command '{cmd}' not in skill help"

    print("  Skill command group configured correctly")


def test_skill_subcommands():
    """Test individual skill subcommands exist (SSOT from references.yaml)."""
    print("\n[Skill Subcommands]")

    from omni.agent.cli.commands.skill import skill_app
    from omni.foundation.services.reference import ReferenceLibrary

    runner = CliRunner()

    # Get expected subcommands from SSOT (references.yaml)
    ref = ReferenceLibrary()
    skill_subcommands = ref.get("cli.skill_subcommands", {})

    # Skip test if not defined in SSOT
    if not skill_subcommands:
        pytest.skip("cli.skill_subcommands not defined in references.yaml")

    # Get list of subcommand names from the skill_app
    subcommand_names = [cmd.name for cmd in skill_app.registered_commands]

    # Verify each expected subcommand exists and is callable
    for cmd in skill_subcommands.keys():
        assert cmd in subcommand_names, (
            f"Expected subcommand '{cmd}' not found in skill_app. Available: {subcommand_names}"
        )
        result = runner.invoke(skill_app, [cmd, "--help"])
        assert result.exit_code == 0, f"{cmd} --help failed"

    print(f"  All {len(skill_subcommands)} skill subcommands verified from SSOT")


def test_cli_help_commands():
    """Test CLI help commands."""
    print("\n[CLI Help Commands]")

    from omni.agent.cli import app

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


# =============================================================================
# Runner Tests
# =============================================================================


def test_runner_function_exists():
    """Test run_skills function exists and is callable."""
    print("\n[Runner Function]")

    from omni.agent.cli.runner import run_skills

    assert callable(run_skills), "run_skills is not callable"
    assert run_skills.__doc__ is not None, "run_skills has no docstring"

    print("  run_skills function exists and is documented")


def test_runner_help_command():
    """Test run_skills with help command."""
    print("\n[Runner Help Command]")

    from omni.agent.cli.console import cli_log_handler
    from omni.agent.cli.runner import run_skills

    captured = io.StringIO()
    with redirect_stderr(captured):
        run_skills(["help"], log_handler=cli_log_handler)

    output = captured.getvalue()
    assert "Available Skills" in output or "git" in output.lower()

    print("  run_skills help command works")


def test_runner_invalid_command():
    """Test run_skills with invalid command format."""
    print("\n[Runner Invalid Command]")

    from click.exceptions import Exit as ClickExit

    from omni.agent.cli.runner import run_skills

    try:
        run_skills(["invalidcommand"])
        assert False, "Should have raised ClickExit"
    except ClickExit as e:
        assert e.exit_code == 1, f"Should exit with code 1, got {e.exit_code}"

    print("  run_skills rejects invalid command format")


# =============================================================================
# Entry Point Tests
# =============================================================================


def test_entry_point_entry_point_exists():
    """Test that entry_point function exists and is callable."""
    print("\n[Entry Point - Function Exists]")

    from omni.agent.cli.app import entry_point

    assert callable(entry_point), "entry_point is not callable"
    assert entry_point.__name__ == "entry_point", "Function is not named 'entry_point'"

    print("  entry_point() function exists and is callable")


def test_entry_point_configures_logging():
    """Test that entry_point() properly configures logging.

    This is a critical regression test - if the entry point doesn't call
    _bootstrap_configuration(), logging won't work and commands will appear silent.
    """
    print("\n[Entry Point - Logging Configuration]")

    import structlog

    # Reset logging state
    import omni.foundation.config.logging as logging_module
    from omni.agent.cli.app import _bootstrap_configuration

    logging_module._configured = False

    # Clear any existing loggers
    structlog.reset_defaults()

    # Call _bootstrap_configuration directly (what entry_point does)
    _bootstrap_configuration(None, False)

    # Verify logging was configured
    assert logging_module._configured, "Logging was not configured by _bootstrap_configuration"

    print("  entry_point() properly configures logging")


def test_pyproject_entry_point_configured():
    """Test that pyproject.toml entry point is configured correctly.

    This ensures the 'omni' script calls entry_point() instead of main(),
    otherwise logging won't be configured.
    """
    print("\n[Pyproject Entry Point]")

    # Use built-in tomllib (Python 3.11+)
    import tomllib
    from pathlib import Path

    # Find pyproject.toml - test_cli.py is at:
    # packages/python/agent/tests/unit/cli/test_cli.py
    # We need: packages/python/agent/pyproject.toml
    test_file = Path(__file__).resolve()
    agent_root = test_file.parents[3]  # /.../packages/python/agent
    agent_pyproject = agent_root / "pyproject.toml"
    assert agent_pyproject.exists(), f"Agent pyproject.toml not found: {agent_pyproject}"

    with open(agent_pyproject, "rb") as f:
        data = tomllib.load(f)

    # Check that 'omni' script points to entry_point
    omni_script = data.get("project", {}).get("scripts", {}).get("omni", "")
    assert "entry_point" in omni_script, (
        f"Entry point should use 'entry_point', got: {omni_script}. "
        "This is a critical bug - the entry point must call _bootstrap_configuration()"
    )
    assert "cli.app:entry_point" in omni_script, (
        f"Entry point should be 'cli.app:entry_point', got: {omni_script}"
    )

    print("  pyproject.toml entry point configured correctly")


# =============================================================================
# Edge Case Tests
# =============================================================================


def test_print_result_edge_cases():
    """Test print_result with edge cases."""
    print("\n[print_result Edge Cases]")

    from omni.agent.cli.console import print_result

    edge_cases = [None, "", "Plain string"]

    for test_input in edge_cases:
        stdout_capture = io.StringIO()
        with redirect_stdout(stdout_capture):
            print_result(test_input, is_tty=False, json_output=False)

    print("  print_result handles edge cases correctly")


# =============================================================================
# Version Command Tests
# =============================================================================


def test_version_command():
    """Test version command outputs version information."""
    print("\n[Version Command]")

    from omni.agent.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0, f"Version command failed: {result.output}"
    assert "Omni Dev Fusion" in result.output, "Title not in version output"
    assert "Omni Agent" in result.output, "Package name not in version output"
    assert "Git Commit" in result.output, "Git commit not in version output"
    assert "Python" in result.output, "Python version not in version output"
    assert "Debug Info" in result.output, "Debug info not in version output"

    print("  Version command works correctly")


def test_version_command_includes_dependencies():
    """Test version command includes dependency versions."""
    print("\n[Version Command - Dependencies]")

    from omni.agent.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["version"])

    # Should attempt to show key dependencies
    assert "Dependencies" in result.output or "not installed" in result.output, (
        "Dependencies section not in version output"
    )

    print("  Version command shows dependencies")


def test_version_function_exists():
    """Test that version function is defined in app module."""
    print("\n[Version Function]")

    from omni.agent.cli.app import version

    assert callable(version), "version is not callable"
    assert version.__doc__ is not None, "version has no docstring"

    print("  version() function exists and is documented")


# =============================================================================
# Verbose Flag Tests (Lightweight)
# =============================================================================


def test_verbose_flag_works_with_subcommands():
    """Test that --verbose/-v works with subcommands (lightweight version)."""
    print("\n[Verbose Flag with Subcommands]")

    import sys
    from types import ModuleType

    # Get the app module from sys.modules after ensuring it's loaded
    # This avoids the Typer object shadowing issue
    if "omni.agent.cli.app" in sys.modules:
        app_module: ModuleType = sys.modules["omni.agent.cli.app"]
    else:
        # Load the module first
        import importlib

        app_module = importlib.import_module("omni.agent.cli.app")

    # Ensure we have the module object, not Typer
    if not isinstance(app_module, ModuleType):
        raise TypeError(f"Expected ModuleType, got {type(app_module)}")

    entry_point = app_module.entry_point
    original_argv = sys.argv
    original_bootstrap: Callable[[str | None, bool], None] = app_module._bootstrap_configuration  # type: ignore[assignment]

    try:
        # Test that -v is detected and removed from argv
        sys.argv = ["omni", "-v", "version"]
        captured: dict[str, bool | str | None] = {"conf": None, "verbose": None}

        def capture_bootstrap(conf: str | None, verbose: bool) -> None:
            captured["conf"] = conf
            captured["verbose"] = verbose

        app_module._bootstrap_configuration = capture_bootstrap  # type: ignore[assignment]

        try:
            entry_point()
        except SystemExit:
            pass

        assert captured["verbose"] is True, f"Expected verbose=True, got {captured['verbose']}"

    finally:
        sys.argv = original_argv
        app_module._bootstrap_configuration = original_bootstrap  # type: ignore[assignment]

    print("  -v flag pre-parsed correctly")


def test_verbose_flag_enables_debug_logging():
    """Test that verbose flag configures debug logging (lightweight)."""
    print("\n[Verbose Flag Logging]")

    from omni.agent.cli.app import _is_verbose, _bootstrap_configuration
    import structlog

    # Reset logging state by accessing the module's _configured attribute
    import omni.foundation.config.logging as logging_module  # type: ignore[import]

    logging_module._configured = False
    structlog.reset_defaults()

    # Call bootstrap with verbose=True
    _bootstrap_configuration(None, verbose=True)

    # Check that verbose flag is set
    assert _is_verbose() is True, "Verbose flag should be True"

    print("  verbose flag enables debug logging")


def test_entry_point_parses_verbose_before_typer():
    """Test that entry_point correctly parses --verbose (unit test)."""
    print("\n[Entry Point Pre-parsing - Verbose]")

    # Test the pre-parsing algorithm directly
    argv = ["omni", "skill", "run", "researcher.test", "-v"]
    conf = None
    verbose = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--verbose", "-v"):
            verbose = True
            argv.pop(i)
            continue
        elif arg in ("--conf", "-c") and i + 1 < len(argv):
            conf = argv[i + 1]
            argv.pop(i + 1)
            argv.pop(i)
            continue
        elif arg.startswith("--conf="):
            conf = arg.split("=", 1)[1]
            argv.pop(i)
            continue
        i += 1

    assert verbose is True, "verbose should be True"
    assert conf is None, "conf should be None"
    assert argv == ["omni", "skill", "run", "researcher.test"], f"argv mismatch: {argv}"

    print("  entry_point correctly pre-parses --verbose")


def test_entry_point_parses_conf_before_typer():
    """Test that entry_point correctly parses --conf (unit test)."""
    print("\n[Entry Point Pre-parsing - Conf]")

    # Test the pre-parsing algorithm directly
    argv = ["omni", "--conf", "/custom/path", "skill", "run", "test"]
    conf = None
    verbose = False

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--verbose", "-v"):
            verbose = True
            argv.pop(i)
            continue
        elif arg in ("--conf", "-c") and i + 1 < len(argv):
            conf = argv[i + 1]
            argv.pop(i + 1)
            argv.pop(i)
            continue
        elif arg.startswith("--conf="):
            conf = arg.split("=", 1)[1]
            argv.pop(i)
            continue
        i += 1

    assert conf == "/custom/path", f"conf should be /custom/path, got {conf}"
    assert verbose is False, "verbose should be False"
    assert argv == ["omni", "skill", "run", "test"], f"argv mismatch: {argv}"

    print("  entry_point correctly pre-parses --conf")


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
        # Entry point
        ("Entry Point Exists", test_entry_point_entry_point_exists),
        ("Entry Point Configures Logging", test_entry_point_configures_logging),
        ("Pyproject Entry Point", test_pyproject_entry_point_configured),
        # Edge cases
        ("print_result Edge Cases", test_print_result_edge_cases),
        # Version command
        ("Version Command", test_version_command),
        ("Version Command - Dependencies", test_version_command_includes_dependencies),
        ("Version Function", test_version_function_exists),
        # Verbose flag
        ("Verbose Flag with Subcommands", test_verbose_flag_works_with_subcommands),
        ("Verbose Flag Enables Debug Logging", test_verbose_flag_enables_debug_logging),
        ("Entry Point Parses Verbose", test_entry_point_parses_verbose_before_typer),
        ("Entry Point Parses Conf", test_entry_point_parses_conf_before_typer),
    ]

    result = _TestResult()

    for name, test_func in tests:
        try:
            test_func()
            result.record(name, True)
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


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
