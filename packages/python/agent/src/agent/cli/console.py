"""
console.py - Console and Output Formatting

Phase 35.2: Modular CLI Architecture

Provides:
- err_console: stderr console for logs and UI
- Output formatting functions (metadata panels, results)

UNIX Philosophy:
- stderr: Logs, progress, UI elements (visible to user, invisible to pipes)
- stdout: Only skill results (pure data for pipes)
"""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel


# err_console: responsible for UI, panels, logs, spinners (user visible, pipe invisible)
err_console = Console(stderr=True)


def cli_log_handler(message: str) -> None:
    """Log callback - all logs go to stderr.

    Args:
        message: Log message to display
    """
    style = "dim"
    prefix = "  │"
    if "[Swarm]" in message:
        style = "cyan"
        prefix = "🚀"
    elif "Error" in message:
        style = "red"
        prefix = "❌"

    err_console.print(f"{prefix} {message}", style=style)


def print_metadata_box(result: Any) -> None:
    """Draw a beautiful metadata box on stderr.

    Args:
        result: The skill execution result
    """
    if isinstance(result, dict):
        # Extract metadata (exclude main content fields to keep box clean)
        metadata = {
            k: v
            for k, v in result.items()
            if k not in ["markdown", "content", "raw_output", "data"]
        }
        if metadata:
            err_console.print(
                Panel(
                    JSON.from_data(metadata),
                    title="[bold blue]Skill Metadata[/bold blue]",
                    border_style="blue",
                    expand=False,
                )
            )


def print_result(result: Any, is_tty: bool = False, json_output: bool = False) -> None:
    """Print skill result with dual-channel output.

    UNIX Philosophy:
    - stdout: Only skill results (pure data for pipes)
    - stderr: Logs, progress, metadata (visible to user, invisible to pipes)

    Args:
        result: The skill execution result (CommandResult or dict)
        is_tty: Whether stdout is a terminal
        json_output: If True, output raw JSON to stdout
    """
    import json

    if json_output:
        # JSON mode: Output full result as JSON to stdout
        if hasattr(result, "model_dump"):
            sys.stdout.write(result.model_dump_json(indent=2) + "\n")
        else:
            sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
        return

    # Extract content from result (handle CommandResult from @skill_command)
    content = ""
    metadata = {}

    if hasattr(result, "data") and result.data is not None:
        # CommandResult object from @skill_command decorator
        if isinstance(result.data, dict):
            content = result.data.get("content", result.data.get("markdown", ""))
            metadata = result.data.get("metadata", {})
        else:
            content = str(result.data)
    elif isinstance(result, dict):
        # Handle CommandResult format: data.content / data.metadata
        if "data" in result and isinstance(result["data"], dict):
            content = result["data"].get("content", result["data"].get("markdown", ""))
            metadata = result["data"].get("metadata", {})
        else:
            # Handle isolation.py direct format: content / metadata
            content = result.get("content", result.get("markdown", ""))
            metadata = result.get("metadata", {})
    elif isinstance(result, str):
        content = result

    # [TTY Mode]
    if is_tty:
        # Show metadata panel on stderr
        if metadata:
            err_console.print(
                Panel(
                    JSON.from_data(metadata),
                    title="[bold blue]Skill Metadata[/bold blue]",
                    border_style="blue",
                    expand=False,
                )
            )
        # Show content on stderr (user can see it)
        if content:
            err_console.print(Panel(content, title="Result", expand=False))
    else:
        # [Pipe Mode] - Content to stdout for pipes
        if content:
            sys.stdout.write(content)
            if not content.endswith("\n"):
                sys.stdout.write("\n")


__all__ = [
    "err_console",
    "cli_log_handler",
    "print_metadata_box",
    "print_result",
]
