"""run.py - Omni Loop Command (CCA Runtime)

Execute task via Omni Loop using the new Trinity Architecture.

Usage:
    omni run exec "task description"      # Execute single task
    omni run repl                          # Interactive REPL mode
"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

console = Console()

run_app = typer.Typer(
    name="run",
    help="Execute task via Omni Loop (CCA Runtime)",
    invoke_without_command=True,
)


def _print_banner():
    """Print CCA runtime banner."""
    from rich.text import Text

    banner = Text()
    banner.append(" CCA Runtime ", style="bold green")
    banner.append("• ", style="dim")
    banner.append("Omni Loop (v2.0)", style="italic")
    console.print(Panel(banner, expand=False, border_style="green"))


def _print_session_report(task: str, result: dict, step_count: int, tool_counts: dict, tokens: int):
    """Print enriched session report with stats."""
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(f"[bold cyan]Task:[/bold cyan] {task}")
    grid.add_row(f"[bold dim]Session ID:[/bold dim] {result.get('session_id', 'N/A')}")
    grid.add_row("")

    # Metrics table
    metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
    metrics.add_column("Metric")
    metrics.add_column("Value", style="yellow")
    metrics.add_row("Steps", str(step_count))
    metrics.add_row("Tools", str(sum(tool_counts.values())))
    metrics.add_row("Est. Tokens", f"~{tokens}")
    grid.add_row(metrics)
    grid.add_row("")

    # Tool breakdown
    if tool_counts:
        t_table = Table(title="Tool Usage", show_header=False, box=ROUNDED)
        t_table.add_column("Tool")
        t_table.add_column("Count", justify="right")
        for tool, count in tool_counts.items():
            t_table.add_row(tool, f"[bold green]{count}[/bold green]")
        grid.add_row(t_table)
        grid.add_row("")

    # Reflection
    grid.add_row("[bold green]Reflection & Outcome:[/bold green]")
    grid.add_row(result.get("output", "Task completed"))

    console.print(Panel(grid, title="✨ CCA Session Report ✨", border_style="green", expand=False))


async def _execute_task_via_kernel(task: str, max_steps: Optional[int]) -> dict:
    """Execute task using the new Kernel-based architecture."""
    from omni.core.kernel.engine import get_kernel
    from omni.core.skills.runtime import run_command

    kernel = get_kernel()
    await kernel.initialize()
    await kernel.start()

    try:
        # Use the router to find appropriate skill
        router = kernel.router

        # Route the task to find matching skill
        result = await router.route(task)

        output = ""
        commands_executed = 0

        # Check confidence (can be float or string like "medium"/"high")
        conf_value = result.score if hasattr(result, "score") else 0.5
        if result and conf_value > 0.5:
            skill_name = result.skill_name
            command_name = result.command_name

            # Handle skill-level match (no exact command found)
            if not command_name:
                # List available commands for this skill
                available_cmds = kernel.skill_context.list_commands()
                skill_commands = [
                    c.split(".", 1)[1] for c in available_cmds if c.startswith(f"{skill_name}.")
                ]
                if skill_commands:
                    output = f"Found [cyan]{skill_name}[/cyan] skill. Available commands:\n"
                    for cmd in skill_commands:
                        output += f"  • [yellow]{skill_name}.{cmd}[/yellow]\n"
                    output += f'\nTry: [bold]omni run exec "{skill_name} <command>"[/bold]'
                else:
                    output = f"Skill '{skill_name}' found but has no registered commands."
                commands_executed = 0
            else:
                full_command = f"{skill_name}.{command_name}"

                # Execute the command
                try:
                    cmd_result = await run_command(full_command)
                    output = cmd_result if cmd_result else f"Command {full_command} executed"
                    commands_executed = 1
                except Exception as e:
                    output = f"Command failed: {e}"
        else:
            # No explicit route found - just acknowledge the task
            output = f"Task received: '{task}'"

        # Get discovered skills count
        skills_count = len(kernel.discovered_skills)

        return {
            "session_id": "session_001",
            "output": output,
            "skills_count": skills_count,
            "commands_executed": commands_executed,
            "status": "completed",
        }
    finally:
        await kernel.shutdown()


@run_app.command("exec")
def exec_cmd(
    task: str = typer.Argument(..., help="Task description"),
    steps: int = typer.Option(None, "-s", "--steps", help="Max steps (default: auto)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Execute a single task through the Omni Loop.

    Examples:
        omni run exec "fix the bug in auth.py"
        omni run exec "write tests for user module" --steps 5
        omni run exec "refactor database code" --json
    """
    _print_banner()
    console.print(f"\n[bold]🚀 Starting:[/bold] {task}")
    if steps:
        console.print(f"[dim]Max steps: {steps}[/dim]\n")
    else:
        console.print("[dim]Max steps: Auto (Adaptive)[/dim]\n")

    # Execute task
    result = asyncio.run(_execute_task_via_kernel(task, steps))

    # Generate stats
    commands_executed = result.get("commands_executed", 0)
    tool_counts = {"skill_command": commands_executed} if commands_executed else {}
    tokens = 500  # Simplified estimate
    step_count = 1 if commands_executed else 3

    if json_output:
        import json

        output = {
            "task": task,
            "session_id": result.get("session_id"),
            "steps": step_count,
            "commands": commands_executed,
            "output": result.get("output"),
        }
        print(json.dumps(output, indent=2))
    else:
        _print_session_report(task, result, step_count, tool_counts, tokens)


@run_app.command("repl")
def repl_cmd():
    """Enter interactive REPL mode for continuous task execution.

    Examples:
        omni run repl
    """
    _print_banner()
    console.print("\n[bold]🔄 Interactive REPL Mode[/bold]")
    console.print("[dim]Enter tasks (Ctrl+C to exit):[/dim]\n")

    console.print("[yellow]⚠️  REPL mode requires full MCP integration.[/yellow]")
    console.print('[dim]For now, please use: omni run exec "task"[/dim]\n')

    # In full implementation:
    # - Read user input
    # - Route to appropriate skill
    # - Execute and show results
    # - Loop until Ctrl+C


def register_run_command(parent_app: typer.Typer):
    """Register the run command with the parent app."""
    parent_app.add_typer(run_app, name="run")


__all__ = ["run_app", "register_run_command"]
