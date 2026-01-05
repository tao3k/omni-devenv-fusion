"""
agent/skills/filesystem/tools.py
Filesystem Skill - Safe File Operations.

Phase 25: Omni CLI Architecture
Passive Skill Implementation - Exposes EXPOSED_COMMANDS dictionary.
"""

import fnmatch
from pathlib import Path
from typing import List
import structlog

logger = structlog.get_logger(__name__)


def _get_safe_path(path: str) -> Path:
    """Resolve and verify path is within project root."""
    base = Path.cwd()
    target = (base / path).resolve()

    if not str(target).startswith(str(base)):
        logger.warning(f"Accessing path outside root: {target}")

    return target


async def list_directory(path: str = ".") -> str:
    """List files and directories in the given path."""
    try:
        target = _get_safe_path(path)
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


async def read_file(path: str) -> str:
    """Read the full content of a file (UTF-8)."""
    try:
        target = _get_safe_path(path)
        if not target.exists():
            return f"File not found: {path}"
        if not target.is_file():
            return f"Not a file: {path}"
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


async def read_multiple_files(paths: List[str]) -> str:
    """Read multiple files at once."""
    result = []
    for path in paths:
        result.append(f"--- FILE: {path} ---")
        result.append(await read_file(path))
        result.append(f"--- END FILE: {path} ---\n")
    return "\n".join(result)


async def write_file(path: str, content: str) -> str:
    """Create or Overwrite a file with new content."""
    try:
        target = _get_safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


async def get_file_info(path: str) -> str:
    """Get metadata about a file."""
    try:
        target = _get_safe_path(path)
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


async def search_files(pattern: str, path: str = ".") -> str:
    """Search for files matching a glob pattern."""
    try:
        target = _get_safe_path(path)
        results = list(target.rglob(pattern))
        max_results = 50
        shown = [str(p.relative_to(Path.cwd())) for p in results[:max_results]]
        output = f"Found {len(results)} matches for '{pattern}':\n" + "\n".join(shown)
        if len(results) > max_results:
            output += f"\n... and {len(results) - max_results} more."
        return output
    except Exception as e:
        return f"Error searching files: {e}"


# =============================================================================
# EXPOSED_COMMANDS - Omni CLI Entry Point
# =============================================================================

EXPOSED_COMMANDS = {
    "list_directory": {
        "func": list_directory,
        "description": "List files and directories in the given path.",
        "category": "read",
    },
    "read_file": {
        "func": read_file,
        "description": "Read the full content of a file (UTF-8).",
        "category": "read",
    },
    "read_multiple_files": {
        "func": read_multiple_files,
        "description": "Read multiple files at once.",
        "category": "read",
    },
    "write_file": {
        "func": write_file,
        "description": "Create or Overwrite a file with new content.",
        "category": "write",
    },
    "get_file_info": {
        "func": get_file_info,
        "description": "Get metadata about a file.",
        "category": "read",
    },
    "search_files": {
        "func": search_files,
        "description": "Search for files matching a glob pattern.",
        "category": "read",
    },
}


# =============================================================================
# Legacy Export for Compatibility
# =============================================================================

__all__ = [
    "list_directory",
    "read_file",
    "read_multiple_files",
    "write_file",
    "get_file_info",
    "search_files",
    "EXPOSED_COMMANDS",
]
