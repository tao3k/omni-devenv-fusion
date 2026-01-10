"""
agent/skills/filesystem/tools.py
Filesystem Skill - Safe File Operations.

Phase 25.1: Macro System with @skill_command decorators.
"""

import fnmatch
from pathlib import Path
from typing import List
import structlog

from agent.skills.decorators import skill_command

logger = structlog.get_logger(__name__)


def _get_safe_path(path: str) -> Path:
    """Resolve and verify path is within project root."""
    base = Path.cwd()
    target = (base / path).resolve()

    if not str(target).startswith(str(base)):
        logger.warning(f"Accessing path outside root: {target}")

    return target


@skill_command(
    name="list_directory",
    category="read",
    description="List files and directories in the given path.",
    inject_root=True,
)
async def list_directory(path: str = ".", project_root: Path = None) -> str:
    """List files and directories in the given path."""
    try:
        base = project_root or Path.cwd()
        target = (base / path).resolve()
        if not target.exists():
            return f"Path does not exist: {path}"
        if not target.is_dir():
            return f"Path is not a directory: {path}"

        items = []
        for item in target.iterdir():
            if item.name.startswith(".") and item.name != ".":
                continue
            kind = "DIR " if item.is_dir() else "FILE"
            size = "-" if item.is_dir() else f"{item.stat().st_size}b"
            items.append(f"{kind:<5} {size:<10} {item.name}")

        return f"Directory Listing for '{path}':\n" + "\n".join(sorted(items))
    except Exception as e:
        return f"Error listing directory: {e}"


@skill_command(
    name="read_file",
    category="read",
    description="Read the full content of a file (UTF-8).",
    inject_root=True,
)
async def read_file(path: str, project_root: Path = None) -> str:
    """Read the full content of a file (UTF-8)."""
    try:
        base = project_root or Path.cwd()
        target = (base / path).resolve()
        if not target.exists():
            return f"File not found: {path}"
        if not target.is_file():
            return f"Not a file: {path}"
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


@skill_command(
    name="read_multiple_files",
    category="read",
    description="Read multiple files at once.",
    inject_root=True,
)
async def read_multiple_files(paths: List[str], project_root: Path = None) -> str:
    """Read multiple files at once."""
    result = []
    for path in paths:
        result.append(f"--- FILE: {path} ---")
        result.append(await read_file(path, project_root))
        result.append(f"--- END FILE: {path} ---\n")
    return "\n".join(result)


@skill_command(
    name="write_file",
    category="write",
    description="Create or Overwrite a file with new content.",
    inject_root=True,
)
async def write_file(path: str, content: str, project_root: Path = None) -> str:
    """Create or Overwrite a file with new content."""
    try:
        base = project_root or Path.cwd()
        target = (base / path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@skill_command(
    name="get_file_info",
    category="read",
    description="Get metadata about a file.",
    inject_root=True,
)
async def get_file_info(path: str, project_root: Path = None) -> str:
    """Get metadata about a file."""
    try:
        base = project_root or Path.cwd()
        target = (base / path).resolve()
        if not target.exists():
            return "File not found."
        stat = target.stat()
        return (
            f"Path: {path}\n"
            f"Size: {stat.st_size} bytes\n"
            f"Type: {'Directory' if target.is_dir() else 'File'}\n"
            f"Absolute: {target}"
        )
    except Exception as e:
        return f"Error: {e}"


@skill_command(
    name="search_files",
    category="read",
    description="Search for files matching a glob pattern.",
    inject_root=True,
)
async def search_files(pattern: str, path: str = ".", project_root: Path = None) -> str:
    """Search for files matching a glob pattern."""
    try:
        base = project_root or Path.cwd()
        target = (base / path).resolve()
        results = list(target.rglob(pattern))
        max_results = 50
        shown = [str(p.relative_to(base)) for p in results[:max_results]]
        output = f"Found {len(results)} matches for '{pattern}':\n" + "\n".join(shown)
        if len(results) > max_results:
            output += f"\n... and {len(results) - max_results} more."
        return output
    except Exception as e:
        return f"Error searching files: {e}"
