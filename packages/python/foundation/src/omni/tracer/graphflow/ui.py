"""Graphflow rich-console UI helpers."""

from __future__ import annotations

from rich import box as rich_box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def ultra_header(trace_id: str, thread_id: str, scenario: str) -> Panel:
    """UltraRAG execution tracing header."""
    return Panel(
        Text.from_markup(
            f"[bold cyan]ULTRA-RAG EXECUTION TRACING[/bold cyan]\n\n"
            f"[white]Trace ID:[/white] [yellow]{trace_id}[/yellow]\n"
            f"[white]Thread:[/white]  [yellow]{thread_id}[/yellow]\n"
            f"[white]Scenario:[/white] [green]{scenario}[/green]",
            justify="left",
        ),
        title="[bold]UltraRAG[/bold]",
        border_style="cyan",
        box=rich_box.HEAVY,
    )


def ultra_memory_pool(variables: list[dict]) -> Panel:
    """UltraRAG memory pool display."""
    table = Table(box=rich_box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Variable", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Source Step", style="yellow")
    table.add_column("Status", style="green")

    for var in variables:
        table.add_row(var["name"], var["type"], var["source"], var["status"])

    return Panel(
        table,
        title="[bold cyan]🧠 Memory Pool[/bold cyan]",
        border_style="cyan",
    )


def ultra_step_enter(node: str, input_data: dict, step_id: str) -> Panel:
    """UltraRAG node enter display."""
    return Panel(
        Text.from_markup(
            f"[bold green]▶ ENTER[/bold green] [bold]{node}[/bold]\n\n"
            f"[cyan]Input:[/cyan]\n"
            + "\n".join(f"  • {k}: [yellow]{v}[/yellow]" for k, v in input_data.items())
            + f"\n\n[dim]type=NODE_START | id={step_id}[/dim]",
            justify="left",
        ),
        border_style="green",
        box=rich_box.ROUNDED,
    )


def ultra_step_exit(node: str, output: dict, reasoning: str | None = None) -> Panel:
    """UltraRAG node exit display."""
    content = Text.from_markup(
        f"[bold green]✓ EXIT[/bold green] [bold]{node}[/bold]\n\n"
        f"[cyan]Output:[/cyan]\n"
        + "\n".join(f"  • {k}: [yellow]{v}[/yellow]" for k, v in output.items()),
        justify="left",
    )
    if reasoning:
        content.append_text(Text.from_markup(f"\n\n[yellow]💭 {reasoning}[/yellow]"))
    return Panel(
        content,
        border_style="green",
        box=rich_box.ROUNDED,
    )


def ultra_summary(
    trace_id: str,
    thread_id: str,
    scenario: str,
    status: str,
    duration_ms: float,
    steps: int,
    memory: dict,
    tracer: "LangGraphTracer | None" = None,
) -> Columns:
    """UltraRAG execution summary with detailed memory pool."""
    summary_table = Table(box=rich_box.HEAVY, show_header=False)
    summary_table.add_column("Property", style="cyan")
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Trace ID", f"[yellow]{trace_id}[/yellow]")
    summary_table.add_row("Thread ID", f"[yellow]{thread_id}[/yellow]")
    summary_table.add_row("Scenario", f"[green]{scenario}[/green]")
    summary_table.add_row("Status", f"[bold green]{status}[/bold green]")
    summary_table.add_row("Duration", f"[white]{duration_ms:.2f}ms[/white]")
    summary_table.add_row("Steps", f"[white]{steps}[/white]")

    # Detailed memory pool from tracer
    if tracer and tracer.trace.memory_pool:
        mem_table = Table(box=rich_box.MINIMAL, show_header=True, header_style="bold cyan")
        mem_table.add_column("Variable", style="cyan")
        mem_table.add_column("Count", style="magenta")
        mem_table.add_column("Latest Value", style="white")

        for key, values in tracer.trace.memory_pool.items():
            if isinstance(values, list) and values:
                latest = values[-1] if values else ""
                latest_content = (
                    latest.get("content", "") if isinstance(latest, dict) else str(latest)
                )
                latest_display = (
                    latest_content[:80] + "..."
                    if len(str(latest_content)) > 80
                    else str(latest_content)
                )
                mem_table.add_row(
                    key, f"[magenta]{len(values)}[/magenta]", f"[white]{latest_display}[/white]"
                )
            else:
                mem_table.add_row(key, "1", str(values)[:80])

        for k, v in memory.items():
            if k not in tracer.trace.memory_pool:
                v_display = str(v)[:80] + "..." if len(str(v)) > 80 else str(v)
                mem_table.add_row(k, "1", f"[white]{v_display}[/white]")
    else:
        memory_table = Table(box=rich_box.MINIMAL, show_header=True, header_style="bold cyan")
        memory_table.add_column("Variable", style="cyan")
        memory_table.add_column("Value", style="white")
        for k, v in memory.items():
            if isinstance(v, list):
                memory_table.add_row(
                    k,
                    f"[yellow]{len(v)} items[/yellow]\n"
                    + "\n".join(f"  - {r[:50]}..." for r in v[:3]),
                )
            else:
                v_str = str(v)[:100] + "..." if len(str(v)) > 100 else str(v)
                memory_table.add_row(k, f"[yellow]{v_str}[/yellow]")
        mem_table = memory_table

    return Columns(
        [
            Panel(
                summary_table,
                title="[bold cyan]📊 Execution Summary[/bold cyan]",
                border_style="cyan",
            ),
            Panel(
                mem_table,
                title="[bold cyan]🧠 Memory Pool[/bold cyan]",
                border_style="cyan",
            ),
        ],
        equal=True,
    )


__all__ = [
    "console",
    "ultra_header",
    "ultra_memory_pool",
    "ultra_step_enter",
    "ultra_step_exit",
    "ultra_summary",
]
