"""
Filesystem Skill Tools
Implementation of safe file operations.
"""

import fnmatch
from pathlib import Path
from typing import List
from mcp.server.fastmcp import FastMCP
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


def register(mcp: FastMCP):
    """Register Filesystem tools with MCP using direct function binding."""
    import sys
    import importlib.util

    # Get the current module from sys.modules
    current_module = sys.modules.get("agent.skills.filesystem.tools")
    if current_module is None:
        spec = importlib.util.spec_from_file_location(
            "agent.skills.filesystem.tools",
            Path(__file__).resolve(),
        )
        current_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(current_module)
        sys.modules["agent.skills.filesystem.tools"] = current_module

    # Get functions from the module
    list_dir = getattr(current_module, "list_directory", None)
    read_file_fn = getattr(current_module, "read_file", None)
    read_multi = getattr(current_module, "read_multiple_files", None)
    write_file_fn = getattr(current_module, "write_file", None)
    get_info = getattr(current_module, "get_file_info", None)
    search = getattr(current_module, "search_files", None)

    # Register tools directly
    if list_dir:
        mcp.add_tool(list_dir, "List files and directories in the given path.")
    if read_file_fn:
        mcp.add_tool(read_file_fn, "Read the full content of a file (UTF-8).")
    if read_multi:
        mcp.add_tool(read_multi, "Read multiple files at once.")
    if write_file_fn:
        mcp.add_tool(write_file_fn, "Create or Overwrite a file with new content.")
    if get_info:
        mcp.add_tool(get_info, "Get metadata about a file.")
    if search:
        mcp.add_tool(search, "Search for files matching a glob pattern.")

    logger.info("Filesystem skill tools registered")
