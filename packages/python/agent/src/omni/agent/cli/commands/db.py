"""db.py - Database Query and Management Command

Query and manage Omni databases (knowledge, skills, router, memory).

Usage:
    omni db list                # List all databases
    omni db query "query"       # Query knowledge base
    omni db search "query"      # Search any database
    omni db stats               # Show database statistics
    omni db count <table>       # Count records in table

Databases:
    knowledge.lance  - Knowledge base (Librarian)
    skills.lance     - Skill registry (Cortex)
    router.lance     - Hybrid search index
    memory.lance     - Memory index
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.config.dirs import get_database_path, get_database_paths
from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

db_app = typer.Typer(
    name="db",
    help="Query and manage Omni databases (knowledge, skills, router, memory)",
    invoke_without_command=False,
)

_console = Console()


def _list_databases() -> list[dict[str, Any]]:
    """Get list of all databases with their paths and status."""
    databases = []
    db_paths = get_database_paths()

    for db_name, db_path in db_paths.items():
        path = Path(db_path)
        info = {
            "name": db_name,
            "path": str(path),
            "exists": path.exists(),
            "size_mb": 0.0,
        }
        if path.exists() and path.is_dir():
            try:
                total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                info["size_mb"] = round(total_size / (1024 * 1024), 2)
            except Exception:
                pass
        databases.append(info)

    return databases


def _get_table_count(db_path: str, table_name: str) -> int:
    """Get count of records in a table using Rust store."""
    try:
        from omni_core_rs import PyVectorStore

        store = PyVectorStore(db_path, 384, False)
        return store.count(table_name)
    except Exception:
        return -1


async def _query_knowledge(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Query the knowledge base using Librarian."""
    from omni.core.knowledge.librarian import Librarian

    librarian = Librarian()
    results = librarian.query(query, limit=limit)

    # Format results
    formatted = []
    for res in results:
        meta = res.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}

        formatted.append(
            {
                "score": res.get("score", 0.0),
                "path": meta.get("file_path", "unknown"),
                "lines": f"{meta.get('start_line', '?')}-{meta.get('end_line', '?')}",
                "text": res.get("text", "")[:200] + "..."
                if len(res.get("text", "")) > 200
                else res.get("text", ""),
            }
        )

    return formatted


def _run_async(coro):
    """Run async code, handling event loop properly."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Use nest_asyncio pattern for running in existing loop
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    # No event loop exists
    return asyncio.run(coro)


@db_app.command("list")
def db_list(json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")):
    """List all databases with their paths and sizes."""
    databases = _list_databases()

    if json_output:
        print(json.dumps(databases, indent=2))
        return

    if not databases:
        _console.print("[yellow]No databases found.[/yellow]")
        return

    # Create table
    table = Table(title="Omni Databases", box=ROUNDED)
    table.add_column("Database", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Size", style="magenta")
    table.add_column("Status", style="green")

    for db in databases:
        status = "[green]Exists[/green]" if db["exists"] else "[red]Missing[/red]"
        size = f"{db['size_mb']:.2f} MB" if db["exists"] else "-"
        table.add_row(db["name"], db["path"], size, status)

    _console.print(table)


@db_app.command("query")
def db_query(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Query the knowledge base."""
    results = _run_async(_query_knowledge(query, limit))

    if json_output:
        print(json.dumps(results, indent=2))
        return

    if not results:
        _console.print("[yellow]No results found.[/yellow]")
        return

    # Create table
    table = Table(title=f"Query Results: {query}", box=ROUNDED)
    table.add_column("Score", style="yellow", width=8)
    table.add_column("File", style="cyan")
    table.add_column("Lines", style="dim", width=8)
    table.add_column("Preview", style="white")

    for res in results:
        preview = res["text"].replace("\n", " ")[:100]
        table.add_row(f"{res['score']:.4f}", res["path"], res["lines"], preview)

    _console.print(table)


async def _search_db(
    query: str,
    db_name: str,
    table_name: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search any database using RustVectorStore."""
    from omni.foundation.bridge.rust_vector import RustVectorStore
    from omni.foundation.services.embedding import get_embedding_service

    db_path = get_database_path(db_name)
    # Create store with the correct database path
    store = RustVectorStore(db_path, 1024, True)

    # Get embedding for query
    embed_service = get_embedding_service()
    vectors = embed_service.embed(query)
    query_vector = vectors[0] if vectors else []

    # Search the database
    results = await store.search_tools(
        table_name=table_name,
        query_vector=query_vector,
        query_text=query,
        limit=limit,
        threshold=0.0,
    )

    return results


@db_app.command("search")
def db_search(
    query: str = typer.Argument(..., help="Search query"),
    database: str = typer.Argument(
        "skills", help="Database to search (knowledge, skills, router, memory)"
    ),
    limit: int = typer.Option(1, "--limit", "-n", help="Maximum results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Search any database (knowledge, skills, router, memory).

    Examples:
        omni db search "skill.discover" skills
        omni db search "python async" knowledge
        omni db search "git commit" router
    """
    # Map database name to table name
    db_to_table = {
        "knowledge": "knowledge_chunks",
        "skills": "skills",
        "router": "router",
        "memory": "memory_chunks",
    }

    table_name = db_to_table.get(database.lower())
    if not table_name:
        _console.print(f"[red]Unknown database: {database}[/red]")
        _console.print(f"Available databases: {', '.join(db_to_table.keys())}")
        return

    results = _run_async(_search_db(query, database, table_name, limit))

    if json_output:
        print(json.dumps(results, indent=2))
        return

    if not results:
        _console.print(f"[yellow]No results found in {database}.[/yellow]")
        return

    # For skills database, show tool-centric view
    if database == "skills":
        for i, res in enumerate(results):
            if i > 0:
                _console.print()

            # Header
            name = res.get("tool_name", res.get("name", "-"))
            skill = res.get("skill_name", "-")
            score = res.get("score", 0.0)
            _console.print(
                f"[bold cyan]{name}[/bold cyan] [magenta]({skill})[/magenta] [yellow]score={score:.4f}[/yellow]"
            )

            # All fields
            grid = Table.grid(expand=True)
            grid.add_column(style="dim", width=18)
            grid.add_column()

            for key, value in res.items():
                if key == "score":
                    continue
                # Format value
                if isinstance(value, list):
                    if len(value) > 5:
                        value_str = f"{value[:5]}... ({len(value)} items)"
                    else:
                        value_str = str(value)
                elif isinstance(value, str) and len(value) > 80:
                    value_str = value[:80] + "..."
                else:
                    value_str = str(value)
                grid.add_row(f"{key}:", value_str)

            _console.print(grid)
    else:
        # For other databases, show table view
        table = Table(title=f"Search: {query} [{database}]", box=ROUNDED)
        table.add_column("Score", style="yellow", width=8)
        table.add_column("Name", style="cyan")
        table.add_column("Skill", style="magenta")
        table.add_column("Preview", style="white")

        for res in results:
            name = res.get("tool_name", res.get("name", res.get("file_path", "unknown")))
            skill = res.get("skill_name", "-")
            preview = str(res)[:60]
            score = res.get("score", 0.0)
            table.add_row(f"{score:.4f}", name, skill, f"{preview}...")

        _console.print(table)


@db_app.command("stats")
def db_stats(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show database statistics."""
    databases = _list_databases()
    stats = {}

    for db in databases:
        if not db["exists"]:
            stats[db["name"]] = {"exists": False}
            continue

        db_path = db["path"]
        table_name = db["name"].replace(".lance", "")

        # Try to get table count
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

    # Create summary
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
            records_int = int(records)
            total_records += records_int
        except ValueError:
            pass

        try:
            total_size += info.get("size_mb", 0)
        except (ValueError, TypeError):
            pass

        metrics.add_row(name, records, size, status)

    # Add totals row
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
    # Determine database path based on table name
    table_to_db = {
        "knowledge_chunks": "knowledge",
        "knowledge": "knowledge",
        "skills": "skills",
        "skills_data": "skills",
        "router": "router",
        "memory": "memory",
    }

    db_name = table_to_db.get(table.lower(), table.lower())
    db_path = get_database_path(db_name)

    count = _get_table_count(db_path, table)

    if json_output:
        print(json.dumps({"table": table, "count": count}, indent=2))
        return

    if count >= 0:
        _console.print(f"[cyan]{table}[/cyan]: [bold]{count}[/bold] records")
    else:
        _console.print(f"[yellow]Table '{table}' not found or error reading database.[/yellow]")


def register_db_command(parent_app: typer.Typer) -> None:
    """Register the db command with the parent app."""
    parent_app.add_typer(db_app, name="db")


__all__ = ["db_app", "register_db_command"]
