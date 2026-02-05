"""
isolation.py - Sidecar Execution Pattern for Heavy Skill Dependencies

This module provides a standardized way to run skill scripts in isolated
environments using uv, avoiding dependency conflicts in the main agent runtime.

Philosophy:
- Main agent environment stays clean (no heavy dependencies like crawl4ai)
- Each skill manages its own dependencies via pyproject.toml
- Communication via JSON through stdout/stderr

Usage:
    from omni.foundation.runtime.isolation import run_skill_command

    @skill_command
    def crawl_webpage(url: str):
        return run_skill_command(Path(__file__).parent, "engine.py", {"url": url})
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

# High-performance JSON parsing (orjson is ~3x faster than stdlib json)
try:
    import orjson

    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False


def _json_loads(data: str | bytes) -> Any:
    """Fast JSON parsing using orjson if available."""
    import json

    if _HAS_ORJSON:
        import orjson as _orjson

        return _orjson.loads(data)
    return json.loads(data)


def run_skill_command(
    skill_dir: Path,
    script_name: str,
    args: dict[str, Any],
    timeout: int = 60,
) -> dict[str, Any]:
    """Run a skill script in an isolated uv environment.

    This function:
    1. Uses the skill's local pyproject.toml for dependency resolution
    2. Executes the script in a subprocess with proper isolation
    3. Captures and parses JSON output from stdout

    Args:
        skill_dir: Path to the skill root directory (contains pyproject.toml)
        script_name: Name of the script to run (e.g., "engine.py")
        args: Dictionary of arguments to pass to the script
        timeout: Maximum execution time in seconds (default 60)

    Returns:
        Dictionary with 'success' key and either 'result' or 'error'

    Example:
        result = run_skill_command(
            Path(__file__).parent,
            "engine.py",
            {"url": "https://example.com", "fit_markdown": True}
        )
        if result["success"]:
            print(result["result"]["markdown"])
    """

    script_path = skill_dir / "scripts" / script_name

    if not script_path.exists():
        return {
            "success": False,
            "error": f"Script not found: {script_path}",
        }

    # Get project root using gitops (SSOT - Single Source of Truth)
    from omni.foundation.runtime.gitops import get_project_root

    project_root = get_project_root()

    # Ensure skill_dir is absolute for relative_to
    if not skill_dir.is_absolute():
        skill_dir = project_root / skill_dir

    # Check if skill_dir is under project_root
    try:
        skill_relative = skill_dir.relative_to(project_root)
        use_directory_flag = True
    except ValueError:
        # skill_dir is outside project root (e.g., temp directory)
        # Use absolute path directly without --directory flag
        skill_relative = skill_dir
        use_directory_flag = False

    # Build command: VIRTUAL_ENV=.venv UV_PROJECT_ENVIRONMENT=.venv uv run [--directory <path>] python scripts/<script> --arg val
    # Setting env vars before command ensures they override devenv's values
    cmd = [
        "VIRTUAL_ENV=.venv",
        "UV_PROJECT_ENVIRONMENT=.venv",
        "uv",
        "run",
        "--quiet",
    ]

    # Add --directory only if skill_dir is under project_root
    if use_directory_flag:
        cmd.extend(["--directory", str(skill_relative)])

    cmd.extend(["python", f"scripts/{script_name}"])

    # Convert args to CLI flags with proper type handling
    # - dict/list: JSON encode
    # - Booleans: "true"/"false"
    # - Other values: convert to string
    # - None/empty values: omit
    import json

    for key, value in args.items():
        # Skip None or empty values
        if value is None:
            continue
        if isinstance(value, str) and not value:
            continue
        if isinstance(value, (list, dict)) and len(value) == 0:
            continue

        cmd.append(f"--{key}")

        if isinstance(value, bool):
            # Booleans: always pass as "true"/"false" string
            cmd.append("true" if value else "false")
        elif isinstance(value, (list, dict)):
            # Complex types: JSON encode
            cmd.append(json.dumps(value))
        else:
            # Other values: convert to string
            cmd.append(str(value))

    # Join command into a shell string for proper env var expansion
    cmd_str = " ".join(cmd)

    stdout = ""  # Initialize for exception handlers

    try:
        result = subprocess.run(
            cmd_str,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True,
        )

        # Parse stdout - engine.py outputs clean JSON
        stdout = result.stdout.strip()

        if not stdout:
            return {"success": True, "content": "", "metadata": {}}

        try:
            result_data = _json_loads(stdout)
            # Engine outputs {"success": true, "content": "...", "metadata": {...}}
            return {
                "success": result_data.get("success", True),
                "content": result_data.get("content", ""),
                "metadata": result_data.get("metadata", {}),
            }
        except (ValueError, TypeError):
            # Fallback: treat entire stdout as content
            return {"success": True, "content": stdout, "metadata": {}}

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Script timed out after {timeout}s",
        }
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Script failed (exit code {e.returncode})",
            "stderr": e.stderr.strip() if e.stderr else None,
        }
    except (ValueError, TypeError) as e:
        return {
            "success": False,
            "error": f"Failed to parse JSON output: {e!s}",
            "stdout": stdout[:500] if stdout else None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {e!s}",
        }


def run_skill_command_async(
    skill_dir: Path,
    script_name: str,
    args: dict[str, Any],
    timeout: int = 60,
) -> dict[str, Any]:
    """
    Async wrapper for run_skill_command.

    Note: subprocess.run is synchronous by nature. This wrapper exists
    for API compatibility with async code patterns.

    Args:
        skill_dir: Path to the skill root directory
        script_name: Name of the script to run
        args: Arguments to pass to the script
        timeout: Maximum execution time in seconds

    Returns:
        Dictionary with 'success' key and either 'result' or 'error'
    """
    return run_skill_command(skill_dir, script_name, args, timeout)


def check_skill_dependencies(skill_dir: Path) -> dict[str, Any]:
    """
    Check if a skill's dependencies are installed.

    Runs 'uv sync --dry-run' to verify the environment without installing.

    Args:
        skill_dir: Path to the skill root directory

    Returns:
        Dictionary with 'ready' status and any messages
    """
    pyproject_path = skill_dir / "pyproject.toml"

    if not pyproject_path.exists():
        return {"ready": False, "error": "No pyproject.toml found"}

    try:
        result = subprocess.run(
            ["uv", "sync", "--dry-run", "--directory", str(skill_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {"ready": True, "message": "Dependencies satisfied"}
        else:
            return {
                "ready": False,
                "error": result.stderr.strip() or "Dependency resolution failed",
            }

    except subprocess.TimeoutExpired:
        return {"ready": False, "error": "Dependency check timed out"}
    except FileNotFoundError:
        return {"ready": False, "error": "uv not found in PATH"}


__all__ = [
    "check_skill_dependencies",
    "run_skill_command",
    "run_skill_command_async",
]
