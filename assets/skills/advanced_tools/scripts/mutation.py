"""
Advanced Mutation Tools (Stream Editing)

Wraps sed for efficient text transformation.
Focus: Speed and standard regex compliance.
"""

import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.foundation.config.logging import get_logger
from omni.foundation.config.paths import ConfigPaths
from pydantic import BaseModel

logger = get_logger("skill.advanced_tools.mutation")


class FileChange(BaseModel):
    """Represents a single file change."""

    path: str
    search_for: str
    content: str
    diff: str = ""


@skill_command(
    name="batch_replace",
    description="Batch refactoring with dry-run safety. RECOMMENDED for refactoring.",
    autowire=True,
)
def batch_replace(
    pattern: str,
    replacement: str,
    file_glob: str = "**/*",
    dry_run: bool = True,
    max_files: int = 50,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Batch refactoring with dry-run safety.

    Args:
        pattern: Regex pattern to search for
        replacement: Replacement string (supports backreferences like \\1)
        file_glob: Glob pattern for files to search (e.g., "**/*.py")
        dry_run: If True, only preview changes (default: True for safety)
        max_files: Maximum number of files to process

    Returns:
        dict with success count, changes list, and diffs
    """
    if paths is None:
        paths = ConfigPaths()

    root = Path(paths.project_root)

    # Check for required tools
    rg_path = shutil.which("rg")
    if not rg_path:
        return {"success": False, "error": "'rg' (ripgrep) not found"}

    # Step 1: Discover files with matches
    try:
        result = subprocess.run(
            [rg_path, "--files-with-matches", "-l", pattern, "-g", file_glob],
            capture_output=True,
            text=True,
            cwd=root,
        )
        if result.returncode != 0 and "no matches" not in result.stderr.lower():
            return {"success": False, "error": f"ripgrep failed: {result.stderr}"}

        matching_files = [f for f in result.stdout.strip().split("\n") if f]
        if not matching_files:
            return {"success": True, "message": "No matches found", "changes": [], "count": 0}

        # Limit files
        matching_files = matching_files[:max_files]

    except Exception as e:
        return {"success": False, "error": f"Discovery failed: {e}"}

    # Step 2: Process each file
    changes: list[FileChange] = []
    try:
        for file_path in matching_files:
            full_path = root / file_path
            if not full_path.exists():
                continue

            content = full_path.read_text()
            search_for = pattern

            # Check if pattern matches
            if not re.search(pattern, content):
                continue

            if dry_run:
                # Generate diff for preview
                replacement_text = re.sub(pattern, replacement, content)
                diff_lines = []
                for i, (old_line, new_line) in enumerate(
                    zip(content.splitlines(), replacement_text.splitlines()), 1
                ):
                    if old_line != new_line:
                        diff_lines.append(f"{i}c{i}")
                        diff_lines.append(f"< {old_line}")
                        diff_lines.append(f"> {new_line}")
                diff_str = "\n".join(diff_lines)
            else:
                # Apply changes
                new_content = re.sub(pattern, replacement, content)
                full_path.write_text(new_content)
                replacement_text = new_content
                diff_str = f"Applied: {len([l for l in content.splitlines() if l != new_content.splitlines()])} lines changed"

            change = FileChange(
                path=file_path,
                search_for=search_for,
                content=replacement_text,
                diff=diff_str,
            )
            changes.append(change)

    except Exception as e:
        return {"success": False, "error": f"Processing failed: {e}"}

    return {
        "success": True,
        "mode": "Dry-Run" if dry_run else "Live",
        "count": len(changes),
        "changes": [
            {"path": c.path, "search_for": c.search_for, "content": c.content, "diff": c.diff}
            for c in changes
        ],
    }


@skill_command(
    name="regex_replace",
    description="Replace text in a file using sed regex. Efficient for large files.",
    autowire=True,
)
def regex_replace(
    file_path: str,
    pattern: str,
    replacement: str,
    paths: ConfigPaths | None = None,
) -> dict[str, Any]:
    """
    Execute: sed -i 's/pattern/replacement/g' file
    Uses | as delimiter to avoid escaping path slashes.
    """
    if paths is None:
        paths = ConfigPaths()

    root = paths.project_root
    target = (root / file_path).resolve()

    # 1. Security Check
    if not str(target).startswith(str(root)) or not target.exists():
        return {"success": False, "error": "Invalid file path."}

    # 2. Env Check
    sed_exec = shutil.which("sed")
    if not sed_exec:
        return {"success": False, "error": "'sed' not found."}

    # 3. Platform Handling (BSD/macOS vs GNU/Linux)
    is_macos = platform.system() == "Darwin"

    # Use extended regex (-r for GNU, -E for BSD) for better regex support
    ext_flag = "-E" if is_macos else "-r"

    # Construct sed expression with proper quoting
    # Use | as delimiter, assuming pattern/replacement don't contain it
    expr = f"s|{pattern}|{replacement}|g"

    # Build command: sed -i[ext] -e 'expr' file (BSD needs space after -i, GNU doesn't)
    cmd = [sed_exec, "-i" if not is_macos else "-i", ext_flag, expr, str(target)]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return {"success": False, "error": f"sed failed: {result.stderr}"}

        return {
            "success": True,
            "tool": "sed",
            "file": file_path,
            "command": " ".join(cmd),
        }
    except Exception as e:
        logger.error(f"Regex replace failed: {e}")
        return {"success": False, "error": str(e)}


__all__ = ["regex_replace", "batch_replace", "FileChange"]
