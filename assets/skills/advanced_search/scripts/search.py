"""
advanced_search/scripts/search.py - Advanced Search Commands

Phase 63: Migrated from tools.py to scripts pattern.
"""

import asyncio
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, Any

import structlog

from agent.skills.decorators import skill_script

logger = structlog.get_logger(__name__)


class SearchResult(TypedDict):
    """Represents a single search match result."""

    file: str
    line_number: int
    line_content: str
    match: str


# =============================================================================
# Core Tools
# =============================================================================


def _build_ripgrep_command(
    pattern: str, path: str, file_type: str | None, include_hidden: bool, context_lines: int = 2
) -> list[str]:
    """Build ripgrep command with proper arguments."""
    cmd = ["rg", "--color=never", "--heading", "-n"]

    if not include_hidden:
        cmd.append("--hidden=false")

    if file_type:
        cmd.extend(["-t", file_type])

    cmd.extend(["-C", str(context_lines)])

    cmd.append(pattern)
    cmd.append(path)

    return cmd


async def _execute_search(cmd: list[str], cwd: str) -> tuple[str, str]:
    """Execute ripgrep command asynchronously."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
        )
        stdout, stderr = await process.communicate()
        return (stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"))
    except FileNotFoundError:
        raise RuntimeError("ripgrep (rg) is not installed. Please install ripgrep.")


def _parse_ripgrep_output(output: str, context_lines: int = 2) -> list[SearchResult]:
    """Parse ripgrep output into structured SearchResult objects."""
    results: list[SearchResult] = []

    if not output.strip():
        return results

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

                results.append(
                    SearchResult(
                        file=file_path,
                        line_number=line_number,
                        line_content=line_content,
                        match=line_content,
                    )
                )
            except ValueError:
                continue

    return results


@skill_script(
    name="search_project_code",
    category="read",
    description="Search for a regex pattern in code files using ripgrep.",
)
async def search_project_code(
    pattern: str,
    path: str = ".",
    file_type: str | None = None,
    include_hidden: bool = False,
    context_lines: int = 2,
) -> str:
    """Search for a regex pattern in code files using ripgrep.

    Uses ripgrep for high-performance parallel searching. Returns
    matches with line numbers and surrounding context.
    """
    start_time = time.perf_counter()

    # Validate pattern is not empty
    if not pattern or not pattern.strip():
        return "Error: Pattern cannot be empty"

    # Validate path exists
    search_path = Path(path)
    if not search_path.exists():
        return f"Error: Path does not exist: {path}"

    # Build ripgrep command
    cmd = _build_ripgrep_command(
        pattern=pattern,
        path=path,
        file_type=file_type,
        include_hidden=include_hidden,
        context_lines=context_lines,
    )

    try:
        stdout, stderr = await _execute_search(cmd, cwd=path)
    except RuntimeError as e:
        return f"Error: {e}"

    # Parse output into structured results
    results = _parse_ripgrep_output(stdout, context_lines=context_lines)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Calculate unique files searched (approximation)
    files_searched = len(set(r["file"] for r in results))

    # Format response
    lines = []
    lines.append(f"Found {len(results)} matches in {files_searched} files ({elapsed_ms:.2f}ms):\n")

    for result in results:
        lines.append(f"{result['file']}:{result['line_number']}: {result['line_content']}")

    return "\n".join(lines[:100])  # Limit to 100 results for display
