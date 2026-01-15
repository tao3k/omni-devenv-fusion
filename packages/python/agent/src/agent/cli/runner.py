"""
runner.py - Skill Execution Runner

Phase 35.2: Modular CLI Architecture
Phase 40: Automated Reinforcement Loop
Phase 62: JIT Skill Loader - Uses SkillManager for command execution

Provides skill execution logic with:
- Dynamic module loading via SkillManager
- Async/sync bridging
- Result formatting
- [Phase 40] Automatic feedback recording on success
- [Phase 62] Supports both tools.py and scripts/*.py patterns

UNIX Philosophy:
- Logs go to stderr (visible to user, ignored by pipes)
- Results go to stdout (pure data for pipes)
"""

from __future__ import annotations

import json
import sys
from typing import Callable, Optional

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
        skill_manager.load_all()  # Ensure all skills are loaded

        err_console.print()
        err_console.print(Panel("# 🛠️ Available Skills", style="bold blue"))
        err_console.print()

        for name, skill in sorted(skill_manager.skills.items()):
            err_console.print(f"## {name}")
            err_console.print(f"- **Commands**: {len(skill.commands)}")
            for cmd_name in list(skill.commands.keys())[:5]:
                err_console.print(f"  - `{cmd_name}`")
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
    cmd_args.pop("log_handler", None)

    # Use SkillManager for command execution (supports both tools.py and scripts/*.py)
    from agent.core.skill_manager import get_skill_manager
    from agent.core.skill_loader import get_skill_loader

    # Lazy mode: Don't auto-load all skills for faster CLI startup
    skill_manager = get_skill_manager(lazy=True)

    # Fast path: Try to get skill path from pre-indexed data (avoids directory scan)
    skill_path = None
    loader = get_skill_loader()
    if loader.is_indexed():
        # Skills already indexed, get path from index (fast!)
        skill_path = loader.get_skill_path(skill_name)

    if skill_path is None:
        # Fallback: Use directory lookup (handles unindexed or new skills)
        skill_path = SKILLS_DIR(skill=skill_name)
    if not skill_path.exists():
        err_console.print(Panel(f"Skill not found: {skill_name}", title="❌ Error", style="red"))
        raise typer.Exit(1)

    # Load only the requested skill
    skill_manager.load_skill(skill_path)

    # Check if command exists
    command = skill_manager.get_command(skill_name, cmd_name)
    if command is None:
        # Try alternate naming
        alt_name = f"{skill_name}_{cmd_name}"
        command = skill_manager.get_command(skill_name, alt_name)

    if command is None:
        # Get available commands for error message
        skill = skill_manager.skills.get(skill_name)
        available = list(skill.commands.keys()) if skill else []
        err_console.print(
            Panel(
                f"Command not found: {skill_name}.{cmd_name}. Available: {available}",
                title="❌ Error",
                style="red",
            )
        )
        raise typer.Exit(1)

    # Execute command via SkillManager (handles async/sync and script mode)
    import asyncio

    try:
        # Check if execute method returns a coroutine
        result = command.execute(cmd_args)
        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
    except Exception as e:
        err_console.print(Panel(f"Execution error: {e}", title="❌ Error", style="red"))
        raise typer.Exit(1)

    # [Phase 40] Record successful execution as positive feedback
    _record_cli_success(cmd, skill_name)

    # Print result with smart formatting
    is_tty = sys.stdout.isatty()
    print_result(result, is_tty, json_output)


def _record_cli_success(command: str, skill_name: str) -> None:
    """
    [Phase 40] Record CLI execution success as positive feedback.

    This is a lightweight signal - CLI success doesn't guarantee
    the routing was correct, but it's still useful data.

    Args:
        command: The full command that was executed (e.g., "git.status")
        skill_name: The skill that was used
    """
    try:
        from agent.capabilities.learning.harvester import record_routing_feedback

        # Use command as pseudo-query, record mild positive feedback
        record_routing_feedback(command, skill_name, success=True)
    except Exception:
        # Silently ignore if feedback system not available
        pass


__all__ = ["run_skills"]
