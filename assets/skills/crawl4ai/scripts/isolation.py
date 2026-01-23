"""
isolation.py - Sidecar Execution Pattern for Heavy Skills

Executes heavy skill commands in isolated subprocess environments,
keeping the main agent process clean from heavy dependencies like Playwright.

This module is imported by __init__.py and delegates to subprocess execution.
"""

from typing import Any
import json
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


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

    # Find uv executable
    uv_path = shutil.which("uv")
    if uv_path is None:
        return {
            "success": False,
            "error": "uv not found in PATH",
        }

    # Debug logging
    logger.debug(f"[crawl4ai] Command: {command}, kwargs: {kwargs}")
    logger.debug(f"[crawl4ai] Skill dir: {skill_dir}")
    logger.debug(f"[crawl4ai] pyproject.toml exists: {(skill_dir / 'pyproject.toml').exists()}")
    logger.debug(f"[crawl4ai] uv.lock exists: {(skill_dir / 'uv.lock').exists()}")

    # Run in isolated environment using uv run
    # Use --no-project to prevent using parent project (omni-dev-fusion)
    cmd = [
        uv_path,
        "run",
        "--no-project",  # Don't use parent project
        "--directory",
        str(skill_dir),
        "python",
        str(skill_dir / "scripts" / "engine.py"),
        "--stdin",
    ]

    logger.debug(f"[crawl4ai] Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
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
