"""reindex.py - CLI for reindex (thin layer).

Parse args and delegate to omni.agent.services.reindex; no business logic here.
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.asyncio import run_async_blocking

from omni.agent.services.reindex import (
    ensure_embedding_index_compatibility,
    reindex_all,
    reindex_clear,
    reindex_knowledge,
    reindex_skills_only,
    reindex_status,
)

reindex_app = typer.Typer(
    name="reindex",
    help="Reindex vector databases (skills, knowledge, memory)",
    invoke_without_command=True,
)
_console = Console()


def _do_reindex_all(clear: bool, json_output: bool) -> None:
    """Call reindex service and print results."""
    from omni.agent.services.sync import sync_router_init, sync_symbols

    def sync_symbols_fn(c: bool):
        return run_async_blocking(sync_symbols(clear=c))

    def sync_router_init_fn():
        return run_async_blocking(sync_router_init())

    results = reindex_all(clear, sync_symbols=sync_symbols_fn, sync_router_init=sync_router_init_fn)
    if json_output:
        print(json.dumps(results, indent=2))
        return
    table = Table(title="Reindex All Results")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Details", style="dim")
    component_order = ("symbols", "skills", "router", "knowledge", "memory")
    for db in component_order:
        info = results.get(db, {})
        status = info.get("status", "unknown")
        if status == "success":
            if db == "skills":
                details = f"{info.get('tools_indexed', 0)} tools"
            elif db == "knowledge":
                details = f"{info.get('docs_indexed', 0)} docs"
            elif db == "symbols":
                details = info.get("details", "")
            elif db == "router":
                details = info.get("details", "Router DB (scores) initialized")
            else:
                details = info.get("details", "")
        elif status == "info":
            details = info.get("message", info.get("details", ""))
        else:
            details = info.get("error", info.get("details", "Unknown error"))
        table.add_row(db, status, details)
    _console.print(Panel(table, title="✅ Reindex Complete", style="green"))


@reindex_app.callback(invoke_without_command=True)
def reindex_main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear all databases first"),
):
    """Reindex all vector databases (skills, knowledge). Subcommands: skills, knowledge, status, clear."""
    if ctx.invoked_subcommand is not None:
        return
    _do_reindex_all(clear, json_output)


@reindex_app.command("skills")
def reindex_skills(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Reindex skill tools to skills.lance."""
    result = reindex_skills_only(clear)
    if json_output:
        print(json.dumps(result, indent=2))
    elif result["status"] == "success":
        _console.print(
            Panel(
                f"Indexed {result['tools_indexed']} tools to {result['database']}",
                title="✅ Success",
                style="green",
            )
        )
    else:
        _console.print(
            Panel(
                f"Failed: {result.get('error', 'Unknown error')}",
                title="❌ Error",
                style="red",
            )
        )


@reindex_app.command("knowledge")
def reindex_knowledge_cmd(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Reindex documentation to knowledge.lance."""
    result = reindex_knowledge(clear)
    if json_output:
        print(json.dumps(result, indent=2))
    elif result["status"] == "success":
        _console.print(
            Panel(
                f"Indexed {result['docs_indexed']} docs, {result.get('chunks_indexed', 0)} chunks",
                title="✅ Success",
                style="green",
            )
        )
    else:
        _console.print(
            Panel(
                f"Failed: {result.get('error', 'Unknown error')}",
                title="❌ Error",
                style="red",
            )
        )


@reindex_app.command("clear")
def reindex_clear_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Clear all vector databases."""
    result = reindex_clear()
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        _console.print(
            Panel(
                f"Cleared databases: {', '.join(result['cleared']) if result['cleared'] else 'none'}",
                title="🗑️ Cleared",
                style="yellow",
            )
        )


@reindex_app.command("status")
def reindex_status_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show status of all vector databases."""
    stats = reindex_status()
    if json_output:
        print(json.dumps(stats, indent=2))
    else:
        table = Table(title="Database Status")
        table.add_column("Database", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Details", style="dim")
        for db, info in stats.items():
            status = info.get("status", "unknown")
            if status == "ready":
                details = f"Tools: {info.get('tools', info.get('entries', 0))}"
            elif status == "not_ready":
                details = "Not initialized"
            else:
                details = info.get("error", "Unknown error")
            table.add_row(db, status, details)
        _console.print(table)


@reindex_app.command("all")
def reindex_all_cmd(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear all databases first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Reindex all vector databases."""
    _do_reindex_all(clear, json_output)


def register_reindex_command(parent_app: typer.Typer) -> None:
    """Register the reindex command with the parent app."""
    from omni.agent.cli.load_requirements import register_requirements

    register_requirements("reindex", ollama=False, embedding_index=False)
    parent_app.add_typer(reindex_app, name="reindex")


__all__ = [
    "reindex_app",
    "register_reindex_command",
]
