"""
testing/scripts/pytest.py - Testing Skill Commands

Phase 63: Migrated from tools.py to scripts pattern.
"""

import subprocess
from pathlib import Path

import structlog

from agent.skills.decorators import skill_script

logger = structlog.get_logger(__name__)


@skill_script(
    name="run_tests",
    category="read",
    description="""
    Runs tests using pytest with the project test runner.

    Constructs and executes pytest command with common helpful flags.
    Uses `uv run pytest` for isolated environment.

    Args:
        path: File or directory to test. Defaults to current directory (`.`).
        verbose: If `true`, shows detailed output (`-v`). Defaults to `false`.
        max_fail: Stop after N failures to save time. Defaults to `5`.
                 Use `0` to disable this limit.

    Returns:
        Test output with last 2000 chars on success, 4000 chars on failure.
        Returns error message if path not found or execution fails.

    Example:
        @omni("testing.run_tests", {"path": "tests/unit", "verbose": true})
        @omni("testing.run_tests", {"max_fail": 10})
    """,
    inject_root=True,
)
async def run_tests(path: str = ".", verbose: bool = False, max_fail: int = 5) -> str:
    target = Path(path)
    if not target.exists():
        return f"Path not found: {path}"

    cmd = ["uv", "run", "pytest", str(target)]
    if verbose:
        cmd.append("-v")
    if max_fail > 0:
        cmd.append(f"--maxfail={max_fail}")

    cmd.extend(["-ra", "--tb=short"])

    try:
        logger.info(f"Running tests: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        output = result.stdout + "\n" + result.stderr

        if result.returncode == 0:
            return f"Tests Passed:\n{output[-2000:]}"
        else:
            return f"Tests Failed:\n{output[-4000:]}"

    except subprocess.TimeoutExpired:
        return "Error: Test execution timed out (300s)."
    except Exception as e:
        return f"Execution Error: {str(e)}"


@skill_script(
    name="list_tests",
    category="read",
    description="""
    Discovers and lists available tests without running them.

    Uses `pytest --collect-only` to find test functions and classes.
    Useful to find the correct test ID for targeted debugging.

    Args:
        path: Directory or file to search for tests. Defaults to current directory (`.`).

    Returns:
        Formatted list of discovered tests with their IDs.

    Example:
        @omni("testing.list_tests", {"path": "tests/"})
    """,
    inject_root=True,
)
async def list_tests(path: str = ".") -> str:
    cmd = ["uv", "run", "pytest", path, "--collect-only", "-q"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return f"Discovered Tests:\n{result.stdout}"
    except Exception as e:
        return f"Error listing tests: {str(e)}"
