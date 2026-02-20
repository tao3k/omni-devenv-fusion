"""sync.py - CLI for sync (thin layer).

Parse args and delegate to omni.agent.services.sync; no business logic here.
"""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.asyncio import run_async_blocking

from omni.agent.services.sync import (
    _resolve_references_config_path,
    sync_all,
    sync_knowledge,
    sync_memory,
    sync_router_init,
    sync_skills,
    sync_symbols,
)

sync_app = typer.Typer(
    name="sync",
    help="Synchronize system state and vector indexes (knowledge, skills, memory)",
    invoke_without_command=True,
)
console = Console()


def _print_sync_report(
    title: str, stats: dict[str, Any], json_output: bool = False, elapsed: float = 0.0
) -> None:
    """Print a standardized sync report."""
    if json_output:
        print(json.dumps(stats, indent=2))
        return
    success_count = sum(
        1 for v in stats.values() if isinstance(v, dict) and v.get("status") == "success"
    )
    error_count = sum(
        1 for v in stats.values() if isinstance(v, dict) and v.get("status") == "error"
    )
    total_count = len(stats)
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(f"[bold cyan]Sync Operation:[/bold cyan] {title}")
    grid.add_row(
        f"[dim]Completed in {elapsed:.2f}s | {success_count}/{total_count} successful[/dim]"
    )
    if error_count > 0:
        grid.add_row(f"[red]{error_count} errors encountered[/red]")
    grid.add_row("")
    metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
    metrics.add_column("Component")
    metrics.add_column("Status", style="yellow")
    metrics.add_column("Details", style="dim")
    for component, info in stats.items():
        if not isinstance(info, dict):
            continue
        status = info.get("status", "unknown")
        icon = (
            "[green]✓[/green]"
            if status == "success"
            else "[red]✗[/red]"
            if status == "error"
            else "[yellow]⊘[/yellow]"
        )
        details = info.get("details", "")
        comp_elapsed = info.get("elapsed", 0)
        if component == "symbols" and "external_deps" in info:
            ext = info["external_deps"]
            ext_status = ext.get("status", "")
            ext_details = ext.get("details", "")
            ext_icon = "[green]✓[/green]" if ext_status == "success" else "[yellow]⊘[/yellow]"
            elapsed_str = f" ({comp_elapsed:.2f}s)" if comp_elapsed > 0 else ""
            metrics.add_row(f"{component.title()}{elapsed_str} {icon}", status, details)
            metrics.add_row("  External Deps", ext_icon, ext_details)
        else:
            elapsed_str = f" ({comp_elapsed:.2f}s)" if comp_elapsed > 0 else ""
            metrics.add_row(f"{component.title()}{elapsed_str} {icon}", status, str(details))
    grid.add_row(metrics)
    border = "green" if error_count == 0 else "red" if error_count == total_count else "yellow"
    console.print(Panel(grid, title="✓ System Sync Complete", border_style=border))


@sync_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logs"),
):
    """Synchronize system state and vector indexes. If no subcommand, syncs everything."""
    if ctx.invoked_subcommand is not None:
        return
    stats, total_elapsed = run_async_blocking(sync_all(verbose=verbose))
    _print_sync_report("Full System Sync", stats, json_output, total_elapsed)


@sync_app.command("knowledge")
def sync_knowledge_cmd(
    ctx: typer.Context,
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show discovered files"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Sync documentation into the knowledge base."""
    # Use parent's verbose if -v was passed to `omni sync -v knowledge`
    parent_verbose = ctx.parent.params.get("verbose", False) if ctx.parent else False
    use_verbose = verbose or parent_verbose
    # Fallback: global -v is pre-parsed by entry_point; _verbose_flag is set in _bootstrap_configuration
    if not use_verbose:
        try:
            from omni.agent.cli.app import _is_verbose

            use_verbose = _is_verbose()
        except Exception:
            pass
    stats = {"knowledge": run_async_blocking(sync_knowledge(clear, use_verbose))}
    _print_sync_report("Knowledge Base", stats, json_output)


@sync_app.command("skills")
def sync_skills_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Sync skill registry (Cortex)."""
    stats = {"skills": run_async_blocking(sync_skills())}
    _print_sync_report("Skill Cortex", stats, json_output)


@sync_app.command("route")
def sync_route_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Initialize router DB (scores table). Required for omni route test."""
    stats = {"router": run_async_blocking(sync_router_init())}
    _print_sync_report("Router DB", stats, json_output)


@sync_app.command("memory")
def sync_memory_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Optimize and sync memory index."""
    stats = {"memory": run_async_blocking(sync_memory())}
    _print_sync_report("Memory Index", stats, json_output)


@sync_app.command("symbols")
def sync_symbols_cmd(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing symbol index first"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Sync code symbols using Zero-Token Indexing (omni-tags)."""
    stats = {"symbols": run_async_blocking(sync_symbols(clear, verbose))}
    _print_sync_report("Symbol Index (Zero-Token)", stats, json_output)


def register_sync_command(parent_app: typer.Typer) -> None:
    """Register the sync command with the parent app."""
    from omni.agent.cli.load_requirements import register_requirements

    register_requirements("sync", ollama=True, embedding_index=True)
    parent_app.add_typer(sync_app, name="sync")


__all__ = ["sync_app", "register_sync_command"]
