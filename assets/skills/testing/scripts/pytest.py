"""
Testing Skill (Modernized)

Responsibilities:
- Execute Pytest suites safely within Project Root.
- Parse output for LLM consumption (Pass/Fail/Traceback).
- Structured failure data for auto-fixing workflows.
- Auto-wired dependencies.
"""

import re
import shutil
import subprocess
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths

logger = get_logger("skill.testing.pytest")


def _parse_failures(stdout: str, stderr: str) -> list[dict[str, Any]]:
    """
    Parse pytest output to extract structured failure info.

    Returns list of failures with file, line, error, and test name.
    """
    failures: list[dict[str, Any]] = []
    lines = stdout.splitlines()

    # Track current state for multi-line failure parsing
    current_failure: dict[str, Any] | None = None
    traceback_lines: list[str] = []
    in_traceback = False

    for line in lines:
        stripped = line.strip()

        # Detect FAILED header line
        # Format: "FAILED tests/unit/test_x.py::test_name - ErrorType: message"
        if stripped.startswith("FAILED "):
            # Save previous failure if exists
            if current_failure:
                current_failure["traceback"] = "\n".join(traceback_lines[-20:])
                failures.append(current_failure)

            # Parse new failure
            parts = stripped[7:].split(" - ", 1)  # Remove "FAILED "
            location = parts[0]
            error_msg = parts[1] if len(parts) > 1 else "Unknown Error"

            # Parse file:line from traceback format or location
            file_path = ""
            line_num = 0
            test_name = ""

            if "::" in location:
                file_part, test_part = location.split("::", 1)
                file_path = file_part
                test_name = test_part
            else:
                file_path = location

            # Try to extract line number from traceback pattern
            # Format: "File "...", line 42, in test_function"
            tb_line_match = None
            for tb_line in lines:
                if file_path in tb_line and "line " in tb_line:
                    match = re.search(r"line (\d+)", tb_line)
                    if match:
                        line_num = int(match.group(1))
                        tb_line_match = tb_line
                        break

            current_failure = {
                "file": file_path,
                "line": line_num,
                "test": test_name,
                "error": error_msg,
                "traceback": "",
            }
            traceback_lines = []
            in_traceback = True
            continue

        # Collect traceback context
        if in_traceback:
            if stripped.startswith("=" * 20) or stripped.startswith("---"):
                # End of this failure's traceback
                in_traceback = False
            elif (
                stripped
                and not stripped.startswith("ceres_prompt>")
                and not stripped.startswith("-")
            ):
                traceback_lines.append(line)

    # Don't forget the last failure
    if current_failure:
        current_failure["traceback"] = "\n".join(traceback_lines[-20:])
        failures.append(current_failure)

    # Also parse short test summary for quick overview
    short_summary = []
    in_summary = False
    for line in lines:
        if "=== short test summary info ===" in line:
            in_summary = True
            continue
        if in_summary and line.startswith("FAILED "):
            short_summary.append(line)
        elif in_summary and line.startswith("==="):
            in_summary = False

    return failures


@skill_command(
    name="run_pytest",
    category="workflow",
    description="""
    Run pytest and return STRUCTURED failure data for auto-fixing.

    Args:
        - target: str = "." - File or directory to test
        - verbose: bool = false - Show detailed output (-vv)
        - max_fail: int = 5 - Stop after N failures (0 to disable)
        - include_traceback: bool = true - Include traceback snippets in failures
        - paths: Optional[ConfigPaths] - Injected ConfigPaths instance

    Returns:
        Structured dict with success status, failure list, and output summary.
    """,
    autowire=True,
)
def run_pytest(
    target: str = ".",
    verbose: bool = False,
    max_fail: int = 5,
    include_traceback: bool = True,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Execute pytest safely within project root.

    Returns structured failure data with file:line:error for auto-fixing.

    Args:
        target: File or directory to test. Defaults to ".".
        verbose: If True, shows detailed output (-vv). Defaults to False.
        max_fail: Stop after N failures. Defaults to 5. Use 0 to disable.
        include_traceback: Include traceback snippets in failures. Defaults to True.
        paths: ConfigPaths instance (auto-wired).

    Returns:
        Structured dict with success status, failure list, and output summary.
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    target_path = (root / target).resolve()

    # Security Sandbox
    if not str(target_path).startswith(str(root)):
        return {
            "success": False,
            "error": "Access denied: Cannot run tests outside project root.",
        }

    # Env Check
    pytest_exec = shutil.which("pytest")
    if not pytest_exec:
        return {
            "success": False,
            "error": "pytest not found. Please ensure it is installed in your environment.",
        }

    # Build Command
    cmd = [pytest_exec]
    if verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")
    if max_fail > 0:
        cmd.extend(["--maxfail", str(max_fail)])
    cmd.extend(["-p", "no:cacheprovider", "--tb=short"])
    cmd.append(str(target_path))

    try:
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=300)

        is_success = result.returncode == 0
        has_failures = result.returncode == 1
        output_summary = _summarize_output(result.stdout, result.stderr)
        failures = _parse_failures(result.stdout, result.stderr)

        # Limit failures to prevent token explosion
        max_failures = 10
        if len(failures) > max_failures:
            failures = failures[:max_failures]

        response: dict[str, Any] = {
            "success": is_success,
            "failed": has_failures,
            "exit_code": result.returncode,
            "target": str(target_path.relative_to(root))
            if str(target_path).startswith(str(root))
            else str(target_path),
            "summary": output_summary,
            "failure_count": len(failures),
            "failures": failures,
        }

        if not is_success:
            # Include last part of raw output for context
            response["raw_output"] = result.stdout[-3000:]

        return response

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Test execution timed out (300s)."}
    except Exception as e:
        logger.error(f"Pytest execution failed: {e}")
        return {"success": False, "error": str(e)}


@skill_command(
    name="list_tests",
    category="read",
    description="""
    Discover and list available tests without running them.

    Args:
        - target: str = "." - File or directory to search for tests
        - paths: Optional[ConfigPaths] - Injected ConfigPaths instance

    Returns:
        Dictionary with success status, target path, test count, and list of tests.
    """,
    autowire=True,
)
def list_tests(
    target: str = ".",
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Discover tests using pytest --collect-only."""
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    target_path = (root / target).resolve()

    if not str(target_path).startswith(str(root)):
        return {"success": False, "error": "Access denied: Cannot search outside project root."}

    pytest_exec = shutil.which("pytest")
    if not pytest_exec:
        return {"success": False, "error": "pytest not found."}

    cmd = [pytest_exec, str(target_path), "--collect-only", "-q"]

    try:
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=60)
        lines = result.stdout.splitlines()
        tests = [line for line in lines if line.strip() and not line.startswith("<")]

        return {
            "success": result.returncode == 0 or "collected" in result.stdout,
            "target": str(target_path.relative_to(root))
            if str(target_path).startswith(str(root))
            else str(target_path),
            "count": len(tests),
            "tests": tests[:50],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _summarize_output(stdout: str, stderr: str) -> str:
    """Extract the essence of pytest output for LLM consumption."""
    lines = stdout.splitlines()
    summary = []
    capture = False

    for line in lines:
        if "=== FAILURES ===" in line or "=== short test summary info ===" in line:
            capture = True
        if capture or "FAILED" in line or "ERROR" in line:
            summary.append(line)

    if lines:
        summary.append(lines[-1])

    return "\n".join(summary[-50:])


__all__ = ["list_tests", "run_pytest"]
