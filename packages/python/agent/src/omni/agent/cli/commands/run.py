"""run.py - Omni Loop Command (CCA Runtime)

Execute task via Omni Loop using the new Trinity Architecture.

Usage:
    omni run "task description"           # Execute single task (ReAct Mode)
    omni run --repl                       # Interactive REPL mode

Examples:
    omni run "fix the bug in auth.py"
    omni run "write tests for user module" --steps 5
    omni run "refactor database code" --json
    omni run --repl                       # Interactive mode
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

console = Console()


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
    output = result.get("output", "Task completed")

    # Render output as markdown panel note
    if output:
        from rich.markdown import Markdown
        from rich.panel import Panel

        # Wrap output in a Panel for note-like appearance
        output_str = str(output) if not isinstance(output, str) else output
        if isinstance(output, dict):
            import json

            output_str = f"```json\n{json.dumps(output, indent=2)}\n```"

        note_panel = Panel(
            Markdown(output_str),
            border_style="dim",
            expand=True,
        )
        grid.add_row(note_panel)
    else:
        grid.add_row("Task completed")

    console.print(Panel(grid, title="✨ CCA Session Report ✨", border_style="green", expand=False))


async def _execute_task_via_kernel(
    task: str, max_steps: int | None, verbose: bool = False
) -> dict:
    """Execute task using the Omni Loop with Kernel context."""
    from omni.agent.core.omni import OmniLoop, OmniLoopConfig
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
        step_count = 0
        tool_calls_count = 0

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
                    output += f'\nTry: [bold]omni run "{skill_name} <command>"[/bold]'
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
                    step_count = 1
                    tool_calls_count = 1
                except Exception as e:
                    output = f"Command failed: {e}"
        else:
            # No explicit route found - use OmniLoop to process via LLM with ReAct
            try:
                # Create OmniLoop with kernel context for tool execution
                # quiet 模式隐藏工具调用日志，verbose 显示 DEBUG 日志
                show_logs = verbose is not False  # 默认和 verbose 都显示
                loop_config = OmniLoopConfig(
                    max_tokens=128000,
                    retained_turns=10,
                    verbose=show_logs,
                )
                loop = OmniLoop(config=loop_config, kernel=kernel)

                # Run the task through the ReAct Loop (LLM + tool calls)
                llm_response = await loop.run(task)

                output = llm_response
                tool_calls_count = loop.tool_calls_count
                step_count = loop.step_count
            except Exception as llm_error:
                # Fallback if LLM fails
                output = f"Task received: '{task}'\n\n[Note: LLM unavailable - {llm_error}]"
                commands_executed = 0

        # Get discovered skills count
        skills_count = len(kernel.discovered_skills)

        return {
            "session_id": "session_001",
            "output": output,
            "skills_count": skills_count,
            "commands_executed": commands_executed,
            "step_count": step_count,
            "tool_calls": tool_calls_count,
            "status": "completed",
        }
    finally:
        await kernel.shutdown()


def _run_repl():
    """Enter interactive REPL mode for continuous task execution."""
    _print_banner()
    console.print("\n[bold]🔄 Interactive REPL Mode[/bold]")
    console.print("[dim]Enter tasks (Ctrl+C to exit):[/dim]\n")

    console.print("[yellow]⚠️  REPL mode requires full MCP integration.[/yellow]")
    console.print('[dim]For now, please use: omni run "task"[/dim]\n')

    # In full implementation:
    # - Read user input
    # - Route to appropriate skill
    # - Execute and show results
    # - Loop until Ctrl+C


def register_run_command(parent_app: typer.Typer):
    """Register the run command with the parent app."""

    @parent_app.command()
    def run(
        task: Annotated[str | None, typer.Argument(help="Task description or query")] = None,
        steps: Annotated[
            int | None, typer.Option("-s", "--steps", help="Max steps (default: 10)")
        ] = None,
        json_output: Annotated[bool, typer.Option("--json", "-j", help="Output as JSON")] = False,
        repl: Annotated[bool, typer.Option("--repl", help="Enter interactive REPL mode")] = False,
        verbose: Annotated[
            bool,
            typer.Option("--verbose/--quiet", "-v/-q", help="Show/hide tool execution details"),
        ] = True,
    ):
        """Execute a task through the Omni Loop (ReAct Mode).

        Examples:
            omni run "fix the bug in auth.py"
            omni run "write tests for user module" --steps 5
            omni run "refactor database code" --json
            omni run --repl                       # Interactive mode
        """
        if repl:
            _run_repl()
            return

        if not task:
            console.print("[bold red]Error:[/bold red] Task description is required")
            raise typer.Exit(1)

        _print_banner()
        console.print(f"\n[bold]🚀 Starting:[/bold] {task}")
        if steps:
            console.print(f"[dim]Max steps: {steps}[/dim]\n")
        else:
            console.print("[dim]Max steps: 10 (ReAct Loop)[/dim]\n")

        # Execute task with ReAct loop
        result = asyncio.run(_execute_task_via_kernel(task, steps, verbose))

        # Generate stats from result
        commands_executed = result.get("commands_executed", 0)
        step_count = result.get("step_count", 1)
        tool_calls = result.get("tool_calls", 0)

        tool_counts = {"tool_calls": tool_calls} if tool_calls is not None else {}
        tokens = 500  # Simplified estimate

        if json_output:
            import json

            output = {
                "task": task,
                "session_id": result.get("session_id"),
                "steps": step_count,
                "tool_calls": tool_calls,
                "commands": commands_executed,
                "output": result.get("output"),
            }
            print(json.dumps(output, indent=2))
        else:
            _print_session_report(task, result, step_count, tool_counts, tokens)


__all__ = ["register_run_command"]
