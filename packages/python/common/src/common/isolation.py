"""
isolation.py - Sidecar Execution Pattern for Heavy Skill Dependencies

This module provides a standardized way to run skill scripts in isolated
environments using uv, avoiding dependency conflicts in the main agent runtime.

Philosophy:
- Main agent environment stays clean (no heavy dependencies like crawl4ai)
- Each skill manages its own dependencies via pyproject.toml
- Communication via JSON through stdout/stderr

Usage:
    from common.isolation import run_skill_script

    @skill_command
    def crawl_webpage(url: str):
        return run_skill_script(Path(__file__).parent, "engine.py", {"url": url})
"""

from __future__ import annotations

import subprocess
import os
from pathlib import Path
from typing import Any, Dict, Optional

# High-performance JSON parsing (orjson is ~3x faster than stdlib json)
try:
    import orjson

    _HAS_ORJSON = True
except ImportError:
    _HAS_ORJSON = False


def _json_loads(data: str | bytes) -> Any:
    """Fast JSON parsing using orjson if available."""
    if _HAS_ORJSON:
        return orjson.loads(data)
    import json

    return json.loads(data)


def run_skill_script(
    skill_dir: Path,
    script_name: str,
    args: Dict[str, Any],
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Run a skill script in an isolated uv environment.

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
        result = run_skill_script(
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

    # Build command: uv run --directory <skill_dir> python <script> --arg val
    cmd = [
        "uv",
        "run",
        "--quiet",  # Reduce noise in output
        "--directory",
        str(skill_dir),
        "python",
        str(script_path),
    ]

    # Convert args to CLI flags (e.g., {"url": "..."} -> "--url", "...")
    for key, value in args.items():
        cmd.append(f"--{key}")
        if isinstance(value, bool):
            cmd.append("true" if value else "false")
        else:
            cmd.append(str(value))

    # Execute in isolated environment
    env = os.environ.copy()
    # Optional: Add isolation-specific env vars
    env["UV_NO_SYNC"] = "1"  # Skip unnecessary sync for repeated calls

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
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
            "error": f"Failed to parse JSON output: {str(e)}",
            "stdout": stdout[:500] if stdout else None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }


def run_skill_script_async(
    skill_dir: Path,
    script_name: str,
    args: Dict[str, Any],
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Async wrapper for run_skill_script.

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
    return run_skill_script(skill_dir, script_name, args, timeout)


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON object from text.

    Looks for the first '{' and last '}' to extract the JSON object.
    This handles cases where scripts print logs before/after the JSON result.
    """
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or start > end:
        return None

    json_str = text[start : end + 1]
    try:
        return _json_loads(json_str)
    except (ValueError, TypeError):
        # Try to be more lenient - maybe there's nested JSON
        # Return None to trigger fallback handling
        return None


def check_skill_dependencies(skill_dir: Path) -> Dict[str, Any]:
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
    "run_skill_script",
    "run_skill_script_async",
    "check_skill_dependencies",
]
