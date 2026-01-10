"""
agent/skills/testing/tools.py
Testing Skill - Pytest integration.

Phase 25: Omni CLI Architecture
Skill implementation with @skill_command decorators.
"""

import subprocess
from pathlib import Path
import structlog

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)


@skill_command(
    name="run_tests",
    category="read",
    description="Run tests using pytest.",
)
async def run_tests(path: str = ".", verbose: bool = False, max_fail: int = 5) -> str:
    """
    Run tests using pytest.

    Args:
        path: File or directory to test (default: current directory).
        verbose: If True, show detailed output (-v).
        max_fail: Stop after N failures (default: 5) to save time.
    """
    # Validate path
    target = Path(path)
    if not target.exists():
        return f"Path not found: {path}"

    # Construct command
    cmd = ["uv", "run", "pytest", str(target)]
    if verbose:
        cmd.append("-v")
    if max_fail > 0:
        cmd.append(f"--maxfail={max_fail}")

    # Add common helpful flags
    cmd.extend(["-ra", "--tb=short"])  # Show summary, short traceback

    try:
        logger.info(f"Running tests: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min timeout
        )

        output = result.stdout + "\n" + result.stderr

        if result.returncode == 0:
            return f"Tests Passed:\n{output[-2000:]}"  # Return last 2000 chars
        else:
            return f"Tests Failed:\n{output[-4000:]}"  # Return more context on failure

    except subprocess.TimeoutExpired:
        return "Error: Test execution timed out (300s)."
    except Exception as e:
        return f"Execution Error: {str(e)}"


@skill_command(
    name="list_tests",
    category="read",
    description="Discover and list available tests without running them.",
)
async def list_tests(path: str = ".") -> str:
    """
    Discover and list available tests without running them.
    Useful to find the correct test ID for targeted debugging.
    """
    cmd = ["uv", "run", "pytest", path, "--collect-only", "-q"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return f"Discovered Tests:\n{result.stdout}"
    except Exception as e:
        return f"Error listing tests: {str(e)}"
