"""dashboard.py - Show last session metrics.

Usage:
    omni dashboard   # Show last run session metrics (task, steps, tools, tokens, etc.)
"""

from __future__ import annotations

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.table import Table

from omni.agent.cli.session_metrics import read_session_metrics

_console = Console()


def register_dashboard_command(parent_app: typer.Typer) -> None:
    """Register the dashboard command with the parent app."""

    @parent_app.command("dashboard")
    def dashboard() -> None:
        """Show last session metrics. Run `omni run <goal>` first to populate."""
        metrics = read_session_metrics()
        if not metrics:
            _console.print(
                "[dim]No session metrics yet. Run [bold]omni run <goal>[/bold] first.[/dim]"
            )
            raise typer.Exit(0)

        table = Table(
            title="Last Session Metrics",
            show_header=True,
            header_style="bold magenta",
            box=ROUNDED,
        )
        table.add_column("Metric")
        table.add_column("Value", style="cyan")

        task = metrics.get("task", "—")
        session_id = metrics.get("session_id", "—")
        table.add_row("Task", str(task))
        table.add_row("Session ID", str(session_id))
        table.add_row("Steps", str(metrics.get("step_count", "—")))
        table.add_row("Tool calls", str(metrics.get("tool_calls", "—")))
        table.add_row("Est. tokens", str(metrics.get("est_tokens", "—")))
        if metrics.get("system_messages") is not None:
            table.add_row("System messages", str(metrics["system_messages"]))
        if metrics.get("total_messages") is not None:
            table.add_row("Total messages", str(metrics["total_messages"]))
        table.add_row("Timestamp", str(metrics.get("timestamp", "—")))

        tool_counts = metrics.get("tool_counts")
        if tool_counts and isinstance(tool_counts, dict):
            table.add_row("", "")
            for tool, count in tool_counts.items():
                table.add_row(f"  {tool}", str(count))

        _console.print(table)


__all__ = ["register_dashboard_command"]
