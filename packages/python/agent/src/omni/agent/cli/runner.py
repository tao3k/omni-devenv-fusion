"""
runner.py - Skill Execution Runner (Kernel Native)

Lightweight CLI for executing skill commands using omni-core Kernel.
Supports skill.command format with JSON arguments.

UNIX Philosophy:
- Logs go to stderr (visible to user, ignored by pipes)
- Results go to stdout (pure data for pipes)
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable

import typer
from rich.panel import Panel

from .console import err_console, print_result


def run_skills(
    commands: list[str],
    json_output: bool = False,
    log_handler: Callable[[str], None] | None = None,
) -> None:
    """Execute skill commands using omni-core Kernel.

    Args:
        commands: List of command arguments
        json_output: If True, force JSON output even in pipe mode
        log_handler: Optional callback for logging messages
    """
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

    # Parse JSON args if provided
    cmd_args = {}
    if len(commands) > 1 and commands[1].startswith("{"):
        try:
            cmd_args = json.loads(commands[1])
        except json.JSONDecodeError as e:
            err_console.print(Panel(f"Invalid JSON args: {e}", title="❌ Error", style="red"))
            raise typer.Exit(1)

    # Use omni-core Kernel (from installed package)
    from omni.core import get_kernel

    kernel = get_kernel()

    # Ensure kernel is initialized
    if not kernel.is_ready:
        asyncio.run(kernel.initialize())

    ctx = kernel.skill_context

    # Get skill
    skill = ctx.get_skill(skill_name)
    if skill is None:
        available = ctx.list_skills()
        err_console.print(
            Panel(
                f"Skill not found: {skill_name}. Available: {available}",
                title="❌ Error",
                style="red",
            )
        )
        raise typer.Exit(1)

    # Check if command exists
    full_cmd = f"{skill_name}.{command_name}"
    if not ctx.get_command(full_cmd):
        # Try alternate naming
        alt_full_cmd = f"{skill_name}.{skill_name}_{command_name}"
        if ctx.get_command(alt_full_cmd):
            full_cmd = alt_full_cmd
        else:
            err_console.print(
                Panel(
                    f"Command not found: {skill_name}.{command_name}",
                    title="❌ Error",
                    style="red",
                )
            )
            raise typer.Exit(1)

    # Execute command
    try:
        result = asyncio.run(skill.execute(command_name, **cmd_args))
    except Exception as e:
        err_console.print(Panel(f"Execution error: {e}", title="❌ Error", style="red"))
        raise typer.Exit(1)

    # Print result
    is_tty = sys.stdout.isatty()
    print_result(result, is_tty, json_output)


def _show_help() -> None:
    """Show available skills and commands."""
    # Use omni-core Kernel (from installed package)
    from omni.core import get_kernel

    kernel = get_kernel()

    if not kernel.is_ready:
        asyncio.run(kernel.initialize())

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
