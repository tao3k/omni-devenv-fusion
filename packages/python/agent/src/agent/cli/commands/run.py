"""run.py - Phase 56: Omni Loop CCA Runtime Command"""

from __future__ import annotations

import typer
from typing import Optional

from common.lib import setup_import_paths

# Setup paths before importing omni_agent
setup_import_paths()

run_app = typer.Typer(
    name="run",
    help="Execute task via CCA Runtime (Omni Loop)",
    invoke_without_command=True,
)


def print_banner():
    """Print CCA runtime banner."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    banner = Text()
    banner.append(" CCA Runtime ", style="bold green")
    banner.append(" - Omni Loop (Phase 56)", style="italic")
    console.print(Panel(banner, expand=False))


@run_app.callback()
def run_callback(ctx: typer.Context):
    """Default: Enter interactive REPL mode when no command is specified."""
    # Only run REPL when no subcommand is provided
    if ctx.invoked_subcommand is None:
        print_banner()
        from agent.core.omni_agent import interactive_mode
        import asyncio

        asyncio.run(interactive_mode())


@run_app.command("repl", help="Enter interactive REPL mode")
def repl_cmd():
    """Enter interactive REPL mode."""
    from agent.core.omni_agent import interactive_mode
    import asyncio

    asyncio.run(interactive_mode())


@run_app.command("exec", help="Execute a single task and exit")
def exec_cmd(
    task: str = typer.Argument(..., help="Task description to execute"),
    steps: int = typer.Option(1, "-s", "--steps", help="Maximum steps (default: 1, max: 20)"),
):
    """Execute a single task through the CCA loop and exit."""
    from agent.core.omni_agent import OmniAgent
    from rich.console import Console
    from rich.table import Table
    from rich.box import ROUNDED
    from rich.panel import Panel
    import asyncio

    console = Console()

    def _print_enrich_result(task: str, result: str, agent):
        """Print enriched session report with stats."""
        # Stats
        tool_counts = {}
        tokens = 0
        for msg in agent.history:
            tokens += len(msg.get("content", "") or "") // 4
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    name = tc["function"]["name"]
                    tool_counts[name] = tool_counts.get(name, 0) + 1

        # Grid layout
        grid = Table.grid(expand=True)
        grid.add_column()
        grid.add_row(f"[bold cyan]Task:[/bold cyan] {task}")
        grid.add_row(f"[bold dim]Session ID:[/bold dim] {agent.session_id}")
        grid.add_row("")

        # Metrics table
        metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
        metrics.add_column("Metric")
        metrics.add_column("Value", style="yellow")
        metrics.add_row("Steps", str(agent.step_count))
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
        grid.add_row(result)

        console.print(Panel(grid, title="✨ CCA Session Report ✨", border_style="green", expand=False))

    async def _run():
        console.print(f"\n[bold]🚀 Starting:[/bold] {task}")
        console.print(f"[dim]Max steps: {steps}[/dim]\n")

        agent = OmniAgent()
        result = await agent.run(task, steps)
        _print_enrich_result(task, result, agent)

    asyncio.run(_run())


def register_run_command(parent_app: typer.Typer):
    """Register the run command with the parent app."""
    parent_app.add_typer(run_app, name="run")
