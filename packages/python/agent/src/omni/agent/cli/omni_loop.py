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


def _format_result_for_display(result: str) -> str:
    """Format result for display, handling common tool output patterns."""
    if not result:
        return "(no output)"

    # Try to parse as JSON (common for tool outputs)
    import json

    try:
        if result.strip().startswith("{") and result.strip().endswith("}"):
            # First try standard JSON (double quotes)
            try:
                data = json.loads(result)
                return _format_json_result(data)
            except json.JSONDecodeError:
                # Try replacing single quotes with double quotes for Python dict strings
                # Handle single-quoted keys and values
                fixed = result.replace("'", '"')
                # Handle Python None, True, False
                fixed = (
                    fixed.replace("True", "true").replace("False", "false").replace("None", "null")
                )
                data = json.loads(fixed)
                return _format_json_result(data)
    except (json.JSONDecodeError, AttributeError, SyntaxError):
        pass

    return result


def _format_json_result(data: dict) -> str:
    """Format a JSON dict as a human-readable summary."""
    if not isinstance(data, dict):
        return str(data)

    # Handle researcher results
    if "success" in data and "harvest_dir" in data:
        return _format_research_result(data)

    # Handle other common patterns
    lines = []
    for key, value in data.items():
        if key in ("success", "error", "message"):
            continue  # Skip generic keys, handle separately
        if isinstance(value, str) and len(value) > 100:
            value = value[:100] + "..."
        lines.append(f"• {key}: {value}")

    # Add status line
    if data.get("success") is True:
        status = "[✓] Completed successfully"
    elif data.get("success") is False:
        status = f"[✗] Failed: {data.get('error', 'unknown error')}"
    else:
        status = ""

    if lines:
        return f"{status}\n" + "\n".join(lines)
    return status or str(data)[:200]


def _format_research_result(data: dict) -> str:
    """Format researcher tool result for display - directly output index.md content."""
    from pathlib import Path

    if not data.get("success"):
        return f"[✗] Research failed: {data.get('error', 'unknown error')}"

    harvest_dir = data.get("harvest_dir", "")
    if not harvest_dir:
        return "[✗] No harvest directory found"

    # Read and return index.md content directly
    index_path = Path(harvest_dir) / "index.md"
    if index_path.exists():
        return index_path.read_text()

    # Fallback to structured output if index.md not found
    lines = ["[✓] Research completed", f"📁 Results: {harvest_dir}"]

    if "shards_analyzed" in data:
        lines.append(f"📊 Shards analyzed: {data['shards_analyzed']}")

    return "\n".join(lines)


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

    # Reflection - use formatted result
    grid.add_row("[bold green]Reflection & Outcome:[/bold green]")
    formatted_result = _format_result_for_display(result)
    grid.add_row(formatted_result)

    console.print(Panel(grid, title="✨ CCA Session Report ✨", border_style="green", expand=False))


async def run_task(task: str, max_steps: int | None):
    """Run a single task through the CCA loop.

    Args:
        task: The task to execute
        max_steps: None = auto-estimate, 1 = single step, N = max steps
    """
    # Import the NEW Core OmniLoop
    from omni.agent.core.omni import OmniLoop
    from omni.core.kernel import get_kernel

    print_banner()
    console.print(f"\n[bold]🚀 Starting:[/bold] {task}")
    if max_steps is None:
        console.print("[dim]Max steps: Auto (AdaptivePlanner)[/dim]\n")
    else:
        console.print(f"[dim]Max steps: {max_steps}[/dim]\n")

    # Initialize kernel first (loads skills)
    kernel = get_kernel()
    console.print(
        f"[dim]Loaded {len(kernel.skill_context._skills)} skills, {len(kernel.skill_context.get_core_commands())} core commands[/dim]\n"
    )

    # Initialize the Smart Loop with ContextManager and kernel
    agent = OmniLoop(kernel=kernel)

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
