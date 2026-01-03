"""
Pytest configuration and fixtures for stress tests.
"""
import sys
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from stress import (
    StressConfig, load_config, set_config,
)

# Create a shared console for test output
_test_console = Console(stderr=True, force_terminal=True)


# =============================================================================
# Rich Test Utilities - Shared across all test files
# =============================================================================

def section(title: str) -> None:
    """Print a section separator with title."""
    _test_console.rule(title)


def subsection(title: str) -> None:
    """Print a subsection separator."""
    _test_console.rule(f"[cyan]{title}[/]", style="cyan")


def pass_step(message: str) -> None:
    """Print a passing step."""
    _test_console.print(f"[green]✓[/] {message}")


def fail_step(message: str) -> None:
    """Print a failing step."""
    _test_console.print(f"[red]✗[/] {message}")


def info_step(message: str) -> None:
    """Print an info step."""
    _test_console.print(f"[blue]ℹ️[/] {message}")


def warn_step(message: str) -> None:
    """Print a warning step."""
    _test_console.print(f"[yellow]⚠️[/] {message}")


def step(num: int, message: str) -> None:
    """Print a numbered step."""
    _test_console.print(f"[bold cyan][Step {num}][/] {message}")


def result(status: str, message: str = "") -> None:
    """Print a test result with status."""
    if status.upper() in ("PASS", "OK", "SUCCESS"):
        _test_console.print(f"[green]✅ {status}[/] {message}")
    elif status.upper() in ("FAIL", "ERROR", "REJECTED"):
        _test_console.print(f"[red]❌ {status}[/] {message}")
    else:
        _test_console.print(f"[yellow]⚠️ {status}[/] {message}")


def response_info(response_len: int, extra: str = "") -> None:
    """Print response information."""
    _test_console.print(f"[green]Response: {response_len} chars[/]{extra}")


def tool_output(tool_name: str, success: bool, extra: str = "") -> None:
    """Print tool output result."""
    icon = "✓" if success else "✗"
    color = "green" if success else "red"
    _test_console.print(f"[{color}]{icon}[/] [bold]{tool_name}[/]{extra}")


def status_table(title: str, rows: list[dict[str, Any]]) -> Table:
    """Create and print a status table."""
    if not rows:
        return None

    table = Table(title=title, box="ROUNDED", style="cyan")
    for key in rows[0].keys():
        table.add_column(key.title(), style="bold cyan")

    for row in rows:
        values = [str(v) for v in row.values()]
        table.add_row(*values)

    _test_console.print(table)
    return table


def simple_table(title: str, *headers: str) -> Table:
    """Create a simple table with headers."""
    table = Table(title=title, box="ROUNDED", style="cyan")
    for header in headers:
        table.add_column(header, style="bold cyan")
    return table


def panel(content: str, title: str = None, style: str = "blue") -> Panel:
    """Create a styled panel."""
    return Panel(
        Text(content),
        title=title,
        border_style=style,
        box="ROUNDED",
        padding=(1, 2),
    )


def print_panel(content: str, title: str = None, style: str = "blue") -> None:
    """Print a styled panel."""
    _test_console.print(panel(content, title, style))


def summary(title: str, results: dict[str, bool]) -> None:
    """Print a test summary with pass/fail badges."""
    _test_console.rule(f"[bold]{title}[/]")
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        style = "green" if passed else "red"
        _test_console.print(f"   [{style}]{status}[/] {name}")


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def stress_dir(tmp_path: Path) -> Path:
    """Provide a temporary stress test directory."""
    stress_dir = tmp_path / "stress_data"
    stress_dir.mkdir(parents=True)
    yield stress_dir


@pytest.fixture
async def stress_env(stress_dir: Path, stress_config: StressConfig):
    """Provide a fully setup stress test environment with generated files."""
    import shutil

    # Apply config
    set_config(stress_config)

    # Generate noise files
    for i in range(stress_config.noise_files):
        (stress_dir / f"noise_{i}.py").write_text(f"""def func_{i}():
    x = {i}
    return x * 2
""")

    # Generate target files
    for i in range(900, 900 + stress_config.target_files):
        (stress_dir / f"target_{i}.py").write_text(f"""def risky_logic_{i}():
    try:
        process_data({i})
        return True
    except ValueError:
        pass  # Silent Killer

def another_func_{i}():
    try:
        api_call()
    except Exception:
        pass  # Silent Killer

def normal_func_{i}():
    try:
        do_work()
    except ValueError as e:
        raise
""")

    yield stress_dir, stress_config

    # Cleanup
    if stress_config.cleanup_after and stress_dir.exists():
        shutil.rmtree(stress_dir)


@pytest.fixture
def silent_killer_pattern() -> str:
    """Pattern for finding try-except-pass blocks."""
    return """try:
  $$BODY
except $ERR:
  pass"""


@pytest.fixture
def nested_pattern() -> str:
    """Pattern for deep recursion testing."""
    return "call($A, call($B, call($C, $D)))"


@pytest.fixture
def broken_python_file(stress_dir: Path) -> Path:
    """Create a malformed Python file for stability testing."""
    broken = stress_dir / "broken.py"
    broken.write_text("def broken_syntax(:\n    print 'oops\n    if True:")
    return broken


@pytest.fixture
def binary_file(stress_dir: Path) -> Path:
    """Create a binary file for stability testing."""
    binary = stress_dir / "data.bin"
    binary.write_bytes(b"\x00\x01\x02\x03\x04\x05")
    return binary
