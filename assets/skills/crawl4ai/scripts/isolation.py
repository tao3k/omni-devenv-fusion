"""
isolation.py - Sidecar Execution Pattern for Heavy Skills

Executes heavy skill commands in isolated subprocess environments,
keeping the main agent process clean from heavy dependencies like Playwright.

This module is imported by __init__.py and delegates to subprocess execution.
"""

from typing import Any
import json
import subprocess
import sys
from pathlib import Path


async def _run_subprocess(command: str, **kwargs) -> dict[str, Any]:
    """
    Run a command in the skill's isolated uv environment.

    Args:
        command: The function name to call in engine.py
        **kwargs: Arguments to pass to the function

    Returns:
        dict with execution results
    """
    skill_dir = Path(__file__).parent.parent

    # Build JSON payload for stdin
    payload = json.dumps(kwargs, default=str)

    # Run in isolated environment
    result = subprocess.run(
        [
            sys.executable,
            str(skill_dir / "scripts" / "engine.py"),
            "--stdin",
        ],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(skill_dir),
    )

    if result.returncode != 0:
        return {
            "success": False,
            "error": f"Subprocess failed: {result.stderr}",
        }

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "success": False,
            "error": f"Invalid JSON output: {result.stdout}",
        }


async def execute_crawl(url: str, fit_markdown: bool = True) -> dict[str, Any]:
    """Execute crawl_url in isolated subprocess."""
    return await _run_subprocess("crawl_url", url=url, fit_markdown=fit_markdown)


async def execute_check_ready() -> dict[str, Any]:
    """Execute check_crawler_ready in isolated subprocess."""
    return await _run_subprocess("check_crawler_ready")
