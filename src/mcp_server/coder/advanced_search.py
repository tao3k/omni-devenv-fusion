"""
Advanced Search Tool - High-performance code search using ripgrep.

This module provides the `search_project_code` tool for fast, parallel
code searching across the project codebase.
"""
import asyncio
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, Any


class SearchResult(TypedDict):
    """Represents a single search match result."""
    file: str          # Path to the file containing the match
    line_number: int   # 1-indexed line number of the match
    line_content: str  # The actual line content
    match: str         # The matching portion of the line


class SearchStats(TypedDict):
    """Statistics about the search operation."""
    files_searched: int
    total_matches: int
    elapsed_ms: float


class SearchResponse(TypedDict):
    """Complete response from the search tool."""
    results: list[SearchResult]
    stats: SearchStats
    error: str | None  # None if successful, error message if failed


def _build_ripgrep_command(
    pattern: str,
    path: str,
    file_type: str | None,
    include_hidden: bool,
    context_lines: int = 2
) -> list[str]:
    """Build ripgrep command with proper arguments.

    Args:
        pattern: Regex pattern to search for.
        path: Search directory.
        file_type: Optional file extension filter.
        include_hidden: Whether to include hidden files.
        context_lines: Lines of context around matches.

    Returns:
        List of command arguments for ripgrep.
    """
    cmd = ["rg", "--color=never", "--heading", "-n"]

    if not include_hidden:
        cmd.append("--hidden=false")

    if file_type:
        cmd.extend(["-t", file_type])

    cmd.extend(["-C", str(context_lines)])

    cmd.append(pattern)
    cmd.append(path)

    return cmd


async def _execute_search(
    cmd: list[str],
    cwd: str
) -> tuple[str, str]:
    """Execute ripgrep command asynchronously.

    Args:
        cmd: Command arguments list.
        cwd: Working directory for the search.

    Returns:
        Tuple of (stdout, stderr) from the process.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd
        )
        stdout, stderr = await process.communicate()
        return (stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"))
    except FileNotFoundError:
        raise RuntimeError("ripgrep (rg) is not installed. Please install ripgrep.")


def _parse_ripgrep_output(
    output: str,
    context_lines: int = 2
) -> list[SearchResult]:
    """Parse ripgrep output into structured SearchResult objects.

    Args:
        output: Raw output from ripgrep command.
        context_lines: Number of context lines expected (for parsing).

    Returns:
        List of SearchResult objects.
    """
    results: list[SearchResult] = []

    if not output.strip():
        return results

    # ripgrep with --heading outputs: "path/to/file\n<matches>"
    lines = output.split("\n")

    current_file = ""
    for line in lines:
        if not line:
            continue

        # Check if this is a file header (no colon, doesn't look like match)
        if ":" not in line:
            current_file = line.strip()
            continue

        # Parse match line: "filepath:line_number:content"
        parts = line.split(":", 2)
        if len(parts) >= 3:
            file_path = parts[0].strip()
            try:
                line_number = int(parts[1].strip())
                line_content = parts[2].strip()

                # Extract the matching portion
                # Find the pattern match within the line
                match = line_content  # Default to full line

                results.append(SearchResult(
                    file=file_path,
                    line_number=line_number,
                    line_content=line_content,
                    match=match
                ))
            except ValueError:
                continue

    return results


async def search_project_code(
    pattern: str,
    path: str = ".",
    file_type: str | None = None,
    include_hidden: bool = False,
    context_lines: int = 2
) -> SearchResponse:
    """Search for a regex pattern in files using ripgrep.

    Args:
        pattern: Required regex pattern to search for.
        path: Search directory (defaults to current directory).
        file_type: Optional file extension filter (e.g., "py" for Python files).
        include_hidden: Whether to search in hidden files/directories.
        context_lines: Number of context lines around matches.

    Returns:
        SearchResponse containing results list, stats, and any error message.
    """
    start_time = time.perf_counter()

    # Validate pattern is not empty
    if not pattern or not pattern.strip():
        return SearchResponse(
            results=[],
            stats=SearchStats(files_searched=0, total_matches=0, elapsed_ms=0.0),
            error="Pattern cannot be empty"
        )

    # Validate path exists
    search_path = Path(path)
    if not search_path.exists():
        return SearchResponse(
            results=[],
            stats=SearchStats(files_searched=0, total_matches=0, elapsed_ms=0.0),
            error=f"Path does not exist: {path}"
        )

    # Build ripgrep command
    cmd = _build_ripgrep_command(
        pattern=pattern,
        path=path,
        file_type=file_type,
        include_hidden=include_hidden,
        context_lines=context_lines
    )

    try:
        stdout, stderr = _execute_search(cmd, cwd=path)
    except RuntimeError as e:
        return SearchResponse(
            results=[],
            stats=SearchStats(files_searched=0, total_matches=0, elapsed_ms=0.0),
            error=str(e)
        )

    # Parse output into structured results
    results = _parse_ripgrep_output(stdout, context_lines=context_lines)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Calculate unique files searched (approximation)
    files_searched = len(set(r["file"] for r in results))

    return SearchResponse(
        results=results,
        stats=SearchStats(
            files_searched=files_searched,
            total_matches=len(results),
            elapsed_ms=elapsed_ms
        ),
        error=None
    )


def _format_response(response: SearchResponse) -> str:
    """Format SearchResponse as a readable string."""
    if response["error"]:
        return f"Error: {response['error']}"

    lines = []
    lines.append(f"Found {response['stats']['total_matches']} matches in "
                  f"{response['stats']['files_searched']} files "
                  f"({response['stats']['elapsed_ms']:.2f}ms):\n")

    for result in response["results"]:
        lines.append(f"{result['file']}:{result['line_number']}: {result['line_content']}")

    return "\n".join(lines[:100])  # Limit to 100 results for display


def register_advanced_search_tools(mcp: Any) -> None:
    """Register advanced search tools with the MCP server.

    Args:
        mcp: FastMCP server instance.
    """

    @mcp.tool()
    async def search_project_code(
        pattern: str,
        path: str = ".",
        file_type: str | None = None,
        include_hidden: bool = False,
        context_lines: int = 2
    ) -> str:
        """Search for a regex pattern in code files using ripgrep.

        Uses ripgrep for high-performance parallel searching. Returns
        matches with line numbers and surrounding context.

        Args:
            pattern: The regex pattern to search for (required).
            path: Directory to search in (default: current directory).
            file_type: Filter by file extension, e.g., "py" or "nix".
            include_hidden: Include hidden files and directories.
            context_lines: Lines of context around matches (default: 2).

        Returns:
            Formatted string with search results and statistics.
        """
        response = await search_project_code(
            pattern=pattern,
            path=path,
            file_type=file_type,
            include_hidden=include_hidden,
            context_lines=context_lines
        )
        return _format_response(response)
