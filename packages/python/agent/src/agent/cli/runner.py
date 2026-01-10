"""
runner.py - Skill Execution Runner

Phase 35.2: Modular CLI Architecture

Provides skill execution logic with:
- Dynamic module loading
- Async/sync bridging
- Result formatting

UNIX Philosophy:
- Logs go to stderr (visible to user, ignored by pipes)
- Results go to stdout (pure data for pipes)
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Callable, Optional

from rich.panel import Panel

from common.skills_path import SKILLS_DIR

from .console import err_console, print_result

import typer


def run_skills(
    commands: list[str],
    json_output: bool = False,
    log_handler: Optional[Callable[[str], None]] = None,
) -> None:
    """Execute skill commands - lightweight, no MCP overhead.

    UNIX Philosophy:
    - Logs go to stderr (visible to user, ignored by pipes)
    - Results go to stdout (pure data for pipes)

    Args:
        commands: List of command arguments
        json_output: If True, force JSON output even in pipe mode
        log_handler: Optional callback for logging messages
    """
    # Log skill invocation
    if log_handler and commands and commands[0] not in ("help", "?"):
        log_handler(f"[CLI] Executing: {' '.join(commands[:2])}")

    if not commands or commands[0] in ("help", "?"):
        # Show available skills - lazy import to avoid pytest dependency
        from agent.core.skill_manager import get_skill_manager

        skill_manager = get_skill_manager()
        skills = skill_manager.skills

        err_console.print()
        err_console.print(Panel("# 🛠️ Available Skills", style="bold blue"))
        err_console.print()

        for name, skill in sorted(skills.items()):
            err_console.print(f"## {name}")
            err_console.print(f"- **Commands**: {len(skill.commands)}")
            for cmd_name in list(skill.commands.keys())[:5]:
                err_console.print(f"  - `{name}.{cmd_name}`")
            if len(skill.commands) > 5:
                err_console.print(f"  - ... and {len(skill.commands) - 5} more")
            err_console.print()
        err_console.print("---")
        err_console.print("**Usage**: `@omni('skill.command', args={})`")
        err_console.print("**Help**: `@omni('skill')` or `@omni('help')`")
        return

    # Execute skill command
    cmd = commands[0]
    if "." not in cmd:
        err_console.print(
            Panel(f"Invalid format: {cmd}. Use skill.command", title="❌ Error", style="red")
        )
        raise typer.Exit(1)

    parts = cmd.split(".")
    skill_name = parts[0]
    cmd_name = "_".join(parts[1:])

    skill_path = SKILLS_DIR(skill=skill_name, filename="tools.py")
    if not skill_path.exists():
        err_console.print(Panel(f"Skill not found: {skill_name}", title="❌ Error", style="red"))
        raise typer.Exit(1)

    # Parse args if provided
    cmd_args = {}
    if len(commands) > 1:
        json_arg = commands[1]
        if json_arg.startswith("{"):
            if len(commands) > 2:
                json_arg = " ".join(commands[1:])
            try:
                cmd_args = json.loads(json_arg)
            except json.JSONDecodeError as e:
                err_console.print(Panel(f"Invalid JSON args: {e}", title="❌ Error", style="red"))
                raise typer.Exit(1)

    # Extract log_handler from cmd_args if present
    extracted_log_handler = cmd_args.pop("log_handler", None)
    effective_log_handler = log_handler or extracted_log_handler

    # Dynamically import and call using ModuleLoader for proper package context
    from agent.core.module_loader import ModuleLoader

    loader = ModuleLoader(SKILLS_DIR())
    loader._ensure_parent_packages()
    loader._preload_decorators()

    module_name = f"agent.skills.{skill_name}.tools"
    module = loader.load_module(module_name, str(skill_path))

    func_name = f"{skill_name}_{cmd_name}" if cmd_name else cmd_name
    func = getattr(module, func_name, None)

    if func is None:
        func = getattr(module, cmd_name, None)

    if func is None:
        err_console.print(
            Panel(f"Command not found: {skill_name}.{cmd_name}", title="❌ Error", style="red")
        )
        raise typer.Exit(1)

    # Execute function (handle both sync and async)
    import inspect

    raw_result = func(**cmd_args) if cmd_args else func()

    # Handle async functions
    if inspect.iscoroutinefunction(func):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(raw_result)
        finally:
            loop.close()
    else:
        result = raw_result

    # Print result with smart formatting
    is_tty = sys.stdout.isatty()
    print_result(result, is_tty, json_output)


__all__ = ["run_skills"]
