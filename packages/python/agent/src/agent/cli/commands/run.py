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
    steps: int = typer.Option(20, "-s", "--steps", help="Maximum steps (default: 20)"),
):
    """Execute a single task through the CCA loop and exit."""
    from agent.core.omni_agent import OmniAgent
    from rich.console import Console
    from rich.panel import Panel
    import asyncio

    console = Console()

    async def _run():
        console.print(f"\n[bold]Starting Task:[/bold] {task}")
        console.print(f"[dim]Max steps: {steps}[/dim]\n")

        agent = OmniAgent()
        result = await agent.run(task, steps)

        console.print(Panel(result, title="Result", expand=False))

    asyncio.run(_run())


def register_run_command(parent_app: typer.Typer):
    """Register the run command with the parent app."""
    parent_app.add_typer(run_app, name="run")
