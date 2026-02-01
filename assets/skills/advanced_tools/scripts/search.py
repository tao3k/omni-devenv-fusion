"""
Advanced Search Tools (Modernized)

Wraps modern Rust-based CLI tools for high-performance retrieval.
Provides superior [FIND] and [SEARCH] capabilities for the Agentic OS.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths

logger = get_logger("skill.advanced_tools.search")


def _run_rg_with_retry(cmd: list[str], root: str, max_retries: int = 2) -> tuple[str, str, int]:
    """Run rg with stdin handling and retry logic for transient errors."""
    for attempt in range(max_retries + 1):
        try:
            process = subprocess.Popen(
                cmd,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                stdin=subprocess.DEVNULL,
            )
            stdout, stderr = process.communicate(timeout=30)
            return stdout, stderr, process.returncode
        except Exception:
            if attempt < max_retries:
                time.sleep(0.1 * (attempt + 1))
            continue
    return "", "", 1


# =============================================================================
# Ripgrep (rg) - High Performance Content Search
# =============================================================================


@skill_command(
    name="smart_search",
    description="""
    [SEARCH] High-performance code/text search using 'ripgrep' (rg).
    
    Use this tool to find TEXT CONTENT, string literals, TODOs, or regex patterns INSIDE files.
    
    Architecture: Parallelized File Scan -> Regex Match Engine -> Context Extraction -> JSON Stream Output
    
    Why this is the Gold Standard:
    1. Speed: Faster than grep, ack, or ag by orders of magnitude.
    2. Smart Filtering: Respects .gitignore, .ignore, and .rgignore automatically.
    3. Contextual Insight: Can provide lines around the match to understand usage.
    4. Multiline Support: Capable of searching across line boundaries if required. 
    
    Usage Guidelines:
    - Use when you need to know WHERE a variable, function, or string is defined or used.
    - Prefer specific file_globs (e.g., "*.py") to reduce noise in large projects.
    - Use context_lines to get a preview of the surrounding code for better analysis.

    Common Use Cases:
    - "Find all usages of class 'Kernel' in the project"
    - "Search for 'TODO' or 'FIXME' tags across all documentation"
    - "Locate error handling patterns in rust files": pattern='Err\\(.*?\\)', file_globs='*.rs'

    Args:
        - pattern: str - The regex or literal string to search for (required).
        - file_globs: str | None - Filter files using glob patterns (e.g. "*.py *.ts").
        - case_sensitive: bool = True - Whether to perform a case-sensitive search.
        - context_lines: int = 0 - Number of lines of context to show around each match.

    Returns:
        Structured JSON with:
        - success: bool
        - count: int (total matches found)
        - matches: List[dict] (file, line, content snippets)
    """,
    autowire=True,
)
def smart_search(
    pattern: str,
    file_globs: str | None = None,
    case_sensitive: bool = True,
    context_lines: int = 0,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """Search using `rg --json`."""
    if paths is None:
        paths = ConfigPaths()
    root = paths.project_root

    rg_exec = shutil.which("rg")
    if not rg_exec:
        return {"success": False, "error": "Tool 'rg' (ripgrep) not found in path."}

    # Build ripgrep command
    cmd = [rg_exec, "--json", pattern]
    if not case_sensitive:
        cmd.append("--ignore-case")
    else:
        cmd.append("--case-sensitive")

    if context_lines > 0:
        cmd.extend(["--context", str(context_lines)])

    if file_globs:
        for glob in file_globs.split():
            cmd.extend(["-g", glob])

    try:
        stdout, stderr, returncode = _run_rg_with_retry(cmd, root)

        if returncode > 1:
            return {"success": False, "error": f"ripgrep error: {stderr}"}

        matches = []
        file_matches = 0
        limit_reached = False

        for line in stdout.splitlines():
            try:
                data = json.loads(line)
                if data["type"] == "match":
                    file_matches += 1
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
# fd-find - Fast File Location and Discovery
# =============================================================================


@skill_command(
    name="smart_find",
    description="""
    [FIND] Ultra-fast file/directory discovery engine using 'fd'.
    
    Best for finding FILES and DIRECTORIES by name, extension, or path pattern.
    
    Architecture: Parallelized Rust Traversal -> Pattern Match -> .gitignore Filter -> Output
    
    Key Features:
    - High Performance: Written in Rust, outperforms standard 'find' by 10x+.
    - Developer Friendly: Automatically skips hidden folders (.git) and respects .gitignore.
    - Smart Case: Sensitive only when uppercase characters are provided in the pattern.
    - Combined Mode: Can find files by content when search_mode='content' (powered by rg).
    
    When to Use:
    - Use this whenever you need to locate a specific file but don't know its exact path.
    - Excellent for exploring project structure or verifying file existence.
    - Faster than 'list_directory' for recursive project-wide discovery.

    Common Use Cases:
    - "Find all python files (*.py) in the project" -> pattern='.', extension='py'
    - "Locate the 'settings.yaml' file" -> pattern='settings.yaml'
    - "Find all test files excluding node_modules" -> pattern='test', exclude='node_modules'
    - "Find all files containing 'TODO'" -> pattern='TODO', search_mode='content'

    Args:
        - pattern: str = "." - The search pattern (regex or glob). Default matches all files.
        - extension: str | None - Filter by file extension (e.g. 'py', 'rs').
        - exclude: str | None - Glob pattern to exclude (e.g. 'build/*', 'target/').
        - search_mode: str = "filename" - "filename" (uses fd) or "content" (uses rg).

    Returns:
        A dictionary containing:
        - success: bool
        - count: int (number of files matched)
        - files: List[str] (project-relative paths to matches, top 100)
    """,
    autowire=True,
)
def smart_find(
    pattern: str = ".",
    extension: str | None = None,
    exclude: str | None = None,
    paths: ConfigPaths | None = None,
    # Search mode: "filename" (default, uses fd) or "content" (uses rg)
    search_mode: str = "filename",
) -> dict[str, Any]:
    """Find files using 'fd' (by filename) or 'rg --files-with-matches' (by content)."""
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root

    # Mode 1: Content Search (Delegates to ripgrep)
    if search_mode == "content":
        rg_exec = shutil.which("rg")
        if not rg_exec:
            return {"success": False, "error": "Tool 'rg' (ripgrep) not found."}

        cmd = [rg_exec, "--files-with-matches", pattern]
        if extension:
            cmd.extend(["--type", extension.replace(".", "")])
        if exclude:
            for excl in exclude.split():
                cmd.extend(["-g", f"!{excl}"])

        try:
            result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=30)
            files = [line for line in result.stdout.splitlines() if line.strip()]
            return {
                "success": True,
                "tool": "ripgrep",
                "search_mode": "content",
                "count": len(files),
                "files": files[:100],
            }
        except Exception as e:
            return {"success": False, "error": f"Content search failed: {e}"}

    # Mode 2: Filename Search (Uses fd)
    fd_exec = shutil.which("fd") or shutil.which("fdfind")
    if not fd_exec:
        return {"success": False, "error": "Tool 'fd' not found in system path."}

    cmd = [fd_exec, "--type", "f"]  # Default to files
    if extension:
        cmd.extend(["--extension", extension])
    if exclude:
        cmd.extend(["--exclude", exclude])

    cmd.append(pattern)

    try:
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=30)
        files = [line for line in result.stdout.splitlines() if line.strip()]
        return {
            "success": True,
            "tool": "fd",
            "search_mode": "filename",
            "count": len(files),
            "files": files[:100],
        }
    except Exception as e:
        return {"success": False, "error": f"Filename search failed: {e}"}


__all__ = ["smart_find", "smart_search"]
