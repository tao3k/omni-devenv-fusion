#!/usr/bin/env python3
"""
agent/cli/omni_loop.py
[Omni-Dev 1.0] Enriched output with tool stats and token metrics.
Powered by ContextManager (The Token Diet)
"""

from __future__ import annotations

import argparse
import asyncio

from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from omni.foundation.utils.common import setup_import_paths

setup_import_paths()
console = Console()


def print_banner():
    """Print CCA runtime banner."""
    banner = Text()
    banner.append(" CCA Runtime ", style="bold green")
    banner.append("• ", style="dim")
    banner.append("Omni Loop (v1.0)", style="italic")
    console.print(Panel(banner, expand=False, border_style="green"))


def _print_enrich_result(task: str, result: str, agent):
    """Print enriched session report with stats from ContextManager."""
    # Get stats directly from ContextManager
    stats = agent.context.stats()

    step_count = agent.step_count if hasattr(agent, "step_count") else stats.get("turn_count", 0)
    est_tokens = stats.get("estimated_tokens", 0)
    system_messages = stats.get("system_messages", 0)
    total_messages = stats.get("total_messages", 0)

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
    metrics.add_row("Turns", str(step_count))
    metrics.add_row("System Msgs", str(system_messages))
    metrics.add_row("Total Msgs", str(total_messages))
    metrics.add_row("Est. Tokens", f"~{est_tokens}")
    grid.add_row(metrics)
    grid.add_row("")

    # Pruning config
    pruner_config = stats.get("pruner_config", {})
    config_info = Table(show_header=False, box=ROUNDED)
    config_info.add_column("Config")
    config_info.add_column("Value", style="dim")
    config_info.add_row("Max Tokens", str(pruner_config.get("max_tokens", "N/A")))
    config_info.add_row("Retained Turns", str(pruner_config.get("retained_turns", "N/A")))
    grid.add_row(config_info)
    grid.add_row("")

    # Reflection
    grid.add_row("[bold green]Reflection & Outcome:[/bold green]")
    grid.add_row(str(result))

    console.print(Panel(grid, title="✨ CCA Session Report ✨", border_style="green", expand=False))


async def run_task(task: str, max_steps: int | None):
    """Run a single task through the CCA loop.

    Args:
        task: The task to execute
        max_steps: None = auto-estimate, 1 = single step, N = max steps
    """
    # Import the NEW Core OmniLoop
    from omni.agent.core.omni import OmniLoop

    print_banner()
    console.print(f"\n[bold]🚀 Starting:[/bold] {task}")
    if max_steps is None:
        console.print("[dim]Max steps: Auto (AdaptivePlanner)[/dim]\n")
    else:
        console.print(f"[dim]Max steps: {max_steps}[/dim]\n")

    # Initialize the Smart Loop with ContextManager
    agent = OmniLoop()

    # Execute
    result = await agent.run(task, max_steps=max_steps)

    # Report
    _print_enrich_result(task, result, agent)
    return result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="omni", description="CCA Runtime - Omni Loop")
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument(
        "-s", "--steps", type=int, default=None, help="Max steps (default: auto-estimate)"
    )
    args, _ = parser.parse_known_args()

    if args.task:
        asyncio.run(run_task(args.task, args.steps))
    else:
        console.print("[yellow]Interactive mode: Use `omni` without arguments[/yellow]")
        console.print("[dim]For interactive mode: Run `omni` in a REPL setup[/dim]")


if __name__ == "__main__":
    main()
