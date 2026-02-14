"""db stats / count subcommands."""

from __future__ import annotations

import json
from contextlib import suppress
from typing import Any

import typer
from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table

from omni.foundation.config import get_database_path

from ._resolver import (
    TABLE_TO_DB,
    _console,
    _get_table_count,
    _list_databases,
    db_app,
)


@db_app.command("stats")
def db_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show database statistics."""
    databases = _list_databases()
    stats: dict[str, Any] = {}

    for db in databases:
        if not db["exists"]:
            stats[db["name"]] = {"exists": False}
            continue

        db_path = db["path"]
        table_name = db["name"].replace(".lance", "")

        count = _get_table_count(db_path, table_name)
        if count >= 0:
            stats[db["name"]] = {
                "exists": True,
                "size_mb": db["size_mb"],
                "table": table_name,
                "record_count": count,
            }
        else:
            stats[db["name"]] = {
                "exists": True,
                "size_mb": db["size_mb"],
                "table": table_name,
                "record_count": "unknown",
            }

    if json_output:
        print(json.dumps(stats, indent=2))
        return

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row("[bold cyan]Database Statistics[/bold cyan]")
    grid.add_row("")

    metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
    metrics.add_column("Database")
    metrics.add_column("Records", style="yellow")
    metrics.add_column("Size", style="dim")
    metrics.add_column("Status", style="green")

    total_records = 0
    total_size = 0.0

    for name, info in stats.items():
        status = "[green]✓[/green]" if info.get("exists") else "[red]✗[/red]"
        records = str(info.get("record_count", "-"))
        size = f"{info.get('size_mb', 0):.2f} MB"

        try:
            total_records += int(records)
        except ValueError:
            pass

        with suppress(ValueError, TypeError):
            total_size += info.get("size_mb", 0)

        metrics.add_row(name, records, size, status)

    metrics.add_row(
        "[bold]Total[/bold]",
        f"[bold]{total_records}[/bold]",
        f"[bold]{total_size:.2f} MB[/bold]",
        "",
    )

    grid.add_row(metrics)
    _console.print(Panel(grid, title="Database Statistics", border_style="cyan"))


@db_app.command("count")
def db_count(
    table: str = typer.Argument(..., help="Table name (e.g., knowledge_chunks, skills)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Count records in a specific table."""
    db_name = TABLE_TO_DB.get(table.lower(), table.lower())
    db_path = get_database_path(db_name)

    count = _get_table_count(db_path, table)

    if json_output:
        print(json.dumps({"table": table, "count": count}, indent=2))
        return

    if count >= 0:
        _console.print(f"[cyan]{table}[/cyan]: [bold]{count}[/bold] records")
    else:
        _console.print(f"[yellow]Table '{table}' not found or error reading database.[/yellow]")
