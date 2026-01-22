"""
Advanced Search Tools (Modernized)

Wraps modern Rust-based CLI tools for high-performance retrieval.
Responsibilities:
- Fast Search: ripgrep (rg)
- Fast Location: fd-find (fd)
- Output: Structured JSON for LLM consumption
"""

import subprocess
import shutil
import json
import os
from typing import Any
from omni.foundation.api.decorators import skill_command
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.advanced_tools.search")


# =============================================================================
# Ripgrep (rg) - High Performance Search
# =============================================================================


@skill_command(
    name="smart_search",
    description="High-performance code search using 'ripgrep' (rg). Respects .gitignore.",
    autowire=True,
)
def smart_search(
    pattern: str,
    file_globs: str | None = None,  # e.g. "*.py *.ts"
    case_sensitive: bool = True,
    context_lines: int = 0,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Search using `rg --json`.
    Much faster than grep and provides structured output.
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root

    # 1. Environment Check (Environment Driven)
    rg_exec = shutil.which("rg")
    if not rg_exec:
        return {
            "success": False,
            "error": "Tool 'rg' (ripgrep) not found. Please install it in your environment.",
        }

    # 2. Build Command (JSON mode is safer for parsing)
    cmd = [rg_exec, "--json", pattern]

    if not case_sensitive:
        cmd.append("--ignore-case")
    else:
        cmd.append("--case-sensitive")

    if context_lines > 0:
        cmd.extend(["--context", str(context_lines)])

    if file_globs:
        # rg expects globs like -g '*.py'
        for glob in file_globs.split():
            cmd.extend(["-g", glob])

    try:
        # 3. Execute
        # cwd=root ensures we search in project context
        process = subprocess.Popen(
            cmd,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()

        if process.returncode > 1:  # 0=found, 1=not found, >1=error
            return {"success": False, "error": f"rg failed: {stderr}"}

        # 4. Parse JSON Stream
        matches = []
        file_matches = 0
        limit_reached = False

        for line in stdout.splitlines():
            try:
                data = json.loads(line)
                if data["type"] == "match":
                    file_matches += 1
                    # Hard limit to protect Context Window
                    if file_matches > 300:
                        limit_reached = True
                        continue

                    matches.append(
                        {
                            "file": data["data"]["path"]["text"],
                            "line": data["data"]["line_number"],
                            "content": data["data"]["lines"]["text"].strip(),
                        }
                    )
            except (json.JSONDecodeError, KeyError):
                continue

        return {
            "success": True,
            "tool": "ripgrep",
            "count": len(matches),
            "matches": matches,
            "truncated": limit_reached,
        }

    except Exception as e:
        logger.error(f"Smart search failed: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# fd-find - Fast File Location
# =============================================================================


@skill_command(
    name="smart_find",
    description="Fast file location using 'fd'. Respects .gitignore.",
    autowire=True,
)
def smart_find(
    pattern: str = ".",
    extension: str | None = None,
    exclude: str | None = None,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Find files using `fd`.
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root

    # 1. Env Check (Handle ubuntu/debian renaming 'fd' to 'fdfind')
    fd_exec = shutil.which("fd") or shutil.which("fdfind")
    if not fd_exec:
        return {"success": False, "error": "Tool 'fd' not found in PATH."}

    cmd = [fd_exec, "--type", "f"]  # Files only

    if extension:
        cmd.extend(["--extension", extension])

    if exclude:
        cmd.extend(["--exclude", exclude])

    cmd.append(pattern)

    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True,
        )

        files = [f for f in result.stdout.splitlines() if f.strip()]

        return {
            "success": True,
            "tool": "fd",
            "count": len(files),
            "files": files[:200],  # Limit
            "truncated": len(files) > 200,
        }
    except Exception as e:
        logger.error(f"Smart find failed: {e}")
        return {"success": False, "error": str(e)}


__all__ = ["smart_search", "smart_find"]
