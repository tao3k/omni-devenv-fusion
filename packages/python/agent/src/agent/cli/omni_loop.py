#!/usr/bin/env python3
"""
agent/cli/omni_loop.py
[Omni-Dev 1.0] Enriched output with tool stats and token metrics.
"""
from __future__ import annotations
import argparse
import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED
from common.lib import setup_import_paths

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
    """Print enriched session report with stats."""
    # 1. Stats
    tool_counts = {}
    tokens = 0
    for msg in agent.history:
        tokens += len(msg.get("content", "") or "") // 4
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                tool_counts[name] = tool_counts.get(name, 0) + 1

    # 2. Grid layout
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


async def run_task(task: str, max_steps: int):
    """Run a single task through the CCA loop."""
    from agent.core.omni_agent import OmniAgent

    print_banner()
    console.print(f"\n[bold]🚀 Starting:[/bold] {task}\n")

    agent = OmniAgent()
    result = await agent.run(task, max_steps)
    _print_enrich_result(task, result, agent)
    return result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="omni", description="CCA Runtime - Omni Loop")
    parser.add_argument("task", nargs="?", help="Task to execute")
    parser.add_argument("-s", "--steps", type=int, default=1, help="Max steps (default: 1)")
    args, _ = parser.parse_known_args()

    if args.task:
        asyncio.run(run_task(args.task, args.steps))
    else:
        from agent.core.omni_agent import interactive_mode
        print_banner()
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
