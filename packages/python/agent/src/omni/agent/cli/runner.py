"""
runner.py - CLI interface for skill run.

Thin layer: parse command (skill.command + JSON args) and delegate to
omni.core.skills.run_skill(). No run logic here; the skill runner
handles fast path and kernel fallback.
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import suppress
from typing import TYPE_CHECKING

import typer
from rich.panel import Panel

from omni.foundation.utils.asyncio import run_async_blocking

from .console import err_console, print_result

if TYPE_CHECKING:
    from collections.abc import Callable


def _setup_quiet_logging():
    """Suppress verbose logging for clean skill output."""
    logging.getLogger("omni").setLevel(logging.WARNING)
    logging.getLogger("omni.core").setLevel(logging.WARNING)
    logging.getLogger("omni.foundation").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)


def run_skills(
    commands: list[str],
    json_output: bool = False,
    quiet: bool = True,
    log_handler: Callable[[str], None] | None = None,
) -> None:
    """Execute skill commands using omni-core Kernel.

    Args:
        commands: List of command arguments
        json_output: If True, force JSON output even in pipe mode
        quiet: If True, suppress kernel logs for clean output
        log_handler: Optional callback for logging messages
    """
    # Suppress verbose logs unless -v/--verbose (so foundation/vector logs are visible when debugging)
    try:
        from omni.agent.cli.app import _is_verbose

        if quiet and not _is_verbose():
            _setup_quiet_logging()
    except Exception:
        if quiet:
            _setup_quiet_logging()

    # Log skill invocation
    if log_handler and commands and commands[0] not in ("help", "?"):
        log_handler(f"[CLI] Executing: {' '.join(commands[:2])}")

    if not commands or commands[0] in ("help", "?"):
        _show_help()
        return

    # Parse command: skill.command [json_args]
    cmd = commands[0]
    if "." not in cmd:
        err_console.print(
            Panel(f"Invalid format: {cmd}. Use skill.command", title="❌ Error", style="red")
        )
        raise typer.Exit(1)

    parts = cmd.split(".", 1)
    skill_name = parts[0]
    command_name = parts[1]

    # Parse JSON args if provided; otherwise treat single positional arg as file_path
    cmd_args: dict = {}
    if len(commands) > 1:
        rest = commands[1].strip()
        if rest.startswith("{"):
            try:
                cmd_args = json.loads(commands[1])
            except json.JSONDecodeError as e:
                err_console.print(Panel(f"Invalid JSON args: {e}", title="❌ Error", style="red"))
                raise typer.Exit(1) from e
        elif rest and not cmd_args:
            # Single non-JSON arg: pass as file_path (e.g. ingest_document "https://...")
            cmd_args = {"file_path": rest}

    # Delegate to skill runner. Use unified run_with_execution_timeout (same as MCP).
    monitor: object | None = None
    try:
        from omni.core.skills import run_skill_with_monitor
        from omni.foundation.api.tool_context import run_with_execution_timeout

        result, monitor = run_async_blocking(
            run_with_execution_timeout(
                run_skill_with_monitor(
                    skill_name,
                    command_name,
                    cmd_args,
                    output_json=json_output,
                    auto_report=False,
                )
            )
        )
    except TimeoutError as e:
        err_console.print(
            Panel(
                str(e) + "\n\nLong runs (e.g. researcher.git_repo_analyer) use heartbeat(); "
                "configure mcp.timeout and mcp.idle_timeout in settings.",
                title="⏱ Timeout",
                style="yellow",
            )
        )
        raise typer.Exit(124) from e
    except ValueError as e:
        err_console.print(Panel(str(e), title="❌ Error", style="red"))
        raise typer.Exit(1) from e
    except Exception as e:
        err_console.print(Panel(f"Execution error: {e}", title="❌ Error", style="red"))
        raise typer.Exit(1) from e

    is_tty = sys.stdout.isatty()
    try:
        print_result(result, is_tty, json_output)
        with suppress(Exception):
            sys.stdout.flush()
        if is_tty:
            err_console.print("[dim]Command completed.[/]")
    finally:
        # In verbose mode, defer dashboard until after result output to keep UX order:
        # command result first, diagnostics second.
        if monitor is not None:
            with suppress(Exception):
                monitor.report(output_json=json_output)

    # Close embedding client session to avoid "Unclosed client session" at exit
    with suppress(Exception):
        from omni.foundation.embedding_client import close_embedding_client

        run_async_blocking(close_embedding_client())


def _show_help() -> None:
    """Show available skills and commands."""
    # Use omni-core Kernel (from installed package)
    from omni.core import get_kernel

    kernel = get_kernel()

    if not kernel.is_ready:
        run_async_blocking(kernel.initialize())

    ctx = kernel.skill_context

    err_console.print()
    err_console.print(Panel("# 🛠️ Available Skills", style="bold blue"))
    err_console.print()

    for skill_name in sorted(ctx.list_skills()):
        skill = ctx.get_skill(skill_name)
        commands = skill.list_commands() if skill else []
        err_console.print(f"## {skill_name}")
        err_console.print(f"- **Commands**: {len(commands)}")
        for cmd in commands[:5]:
            err_console.print(f"  - `{cmd}`")
        if len(commands) > 5:
            err_console.print(f"  - ... and {len(commands) - 5} more")
        err_console.print()

    err_console.print("---")
    err_console.print("**Usage**: `@omni('skill.command', args={})`")
    err_console.print("**Help**: `@omni('skill')` or `@omni('help')`")


__all__ = ["run_skills"]
