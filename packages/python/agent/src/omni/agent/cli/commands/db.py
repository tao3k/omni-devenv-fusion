"""db.py - Database Query and Management Command

Query and manage Omni databases (knowledge, skills, router, memory).

Usage:
    omni db list                # List all databases
    omni db query "query"       # Query knowledge base
    omni db search "query"      # Search any database
    omni db stats               # Show database statistics
    omni db count <table>       # Count records in table
    omni db validate-schema     # Audit: no legacy 'keywords' in skills/router metadata

Databases:
    knowledge.lance  - Knowledge base (Librarian)
    skills.lance     - Skill registry (Cortex)
    router.lance     - Hybrid search index
    memory.lance     - Memory index
"""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.config import get_database_path, get_database_paths
from omni.foundation.services.vector_schema import validate_vector_table_contract
from omni.foundation.utils.asyncio import run_async_blocking
from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

db_app = typer.Typer(
    name="db",
    help="Query and manage Omni databases (knowledge, skills, router, memory)",
    invoke_without_command=False,
)

_console = Console()

DB_TO_DEFAULT_TABLE = {
    "knowledge": "knowledge_chunks",
    "skills": "skills",
    "router": "router",
    "memory": "memory_chunks",
}

TABLE_TO_DB = {
    "knowledge_chunks": "knowledge",
    "knowledge": "knowledge",
    "skills": "skills",
    "skills_data": "skills",
    "router": "router",
    "memory": "memory",
    "memory_chunks": "memory",
}


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


def _get_rust_store(db_name: str):
    """Create a RustVectorStore bound to a specific database path."""
    from omni.foundation.bridge.rust_vector import RustVectorStore

    db_path = get_database_path(db_name)
    return RustVectorStore(db_path, 1024, True)


def _resolve_db_and_table(database: str | None, table: str) -> tuple[str, str]:
    """Resolve database + table pair with sensible defaults."""
    table_key = table.lower()
    db_name = database.lower() if database else TABLE_TO_DB.get(table_key, table_key)
    return db_name, table


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
    results = run_async_blocking(_query_knowledge(query, limit))

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


async def _get_table_info(database: str, table: str) -> dict[str, Any] | None:
    """Fetch table info from Rust vector store."""
    store = _get_rust_store(database)
    return await store.get_table_info(table)


async def _list_versions(database: str, table: str) -> list[dict[str, Any]]:
    """Fetch table versions from Rust vector store."""
    store = _get_rust_store(database)
    return await store.list_versions(table)


async def _get_fragment_stats(database: str, table: str) -> list[dict[str, Any]]:
    """Fetch fragment stats from Rust vector store."""
    store = _get_rust_store(database)
    return await store.get_fragment_stats(table)


async def _add_columns(database: str, table: str, columns: list[dict[str, Any]]) -> bool:
    """Add table columns via Rust schema evolution API."""
    store = _get_rust_store(database)
    return await store.add_columns(table, columns)


async def _alter_columns(database: str, table: str, alterations: list[dict[str, Any]]) -> bool:
    """Alter table columns via Rust schema evolution API."""
    store = _get_rust_store(database)
    return await store.alter_columns(table, alterations)


async def _drop_columns(database: str, table: str, columns: list[str]) -> bool:
    """Drop table columns via Rust schema evolution API."""
    store = _get_rust_store(database)
    return await store.drop_columns(table, columns)


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
    db_to_table = DB_TO_DEFAULT_TABLE

    table_name = db_to_table.get(database.lower())
    if not table_name:
        _console.print(f"[red]Unknown database: {database}[/red]")
        _console.print(f"Available databases: {', '.join(db_to_table.keys())}")
        return

    results = run_async_blocking(_search_db(query, database, table_name, limit))

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


@db_app.command("table-info")
def db_table_info(
    table: str = typer.Argument(..., help="Table name (e.g., skills, knowledge_chunks)"),
    database: str | None = typer.Option(
        None, "--database", "-d", help="Database name (knowledge, skills, router, memory)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show table metadata (version, rows, schema, fragments)."""
    db_name, table_name = _resolve_db_and_table(database, table)
    info = run_async_blocking(_get_table_info(db_name, table_name))

    if json_output:
        print(
            json.dumps(
                {
                    "database": db_name,
                    "table": table_name,
                    "info": info,
                },
                indent=2,
            )
        )
        return

    if not info:
        _console.print(
            f"[yellow]No table info available for '{table_name}' in '{db_name}'.[/yellow]"
        )
        return

    table_view = Table(title=f"Table Info: {table_name} [{db_name}]", box=ROUNDED)
    table_view.add_column("Field", style="cyan")
    table_view.add_column("Value", style="white")
    for key, value in info.items():
        table_view.add_row(
            str(key), json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        )
    _console.print(table_view)


@db_app.command("versions")
def db_versions(
    table: str = typer.Argument(..., help="Table name (e.g., skills, knowledge_chunks)"),
    database: str | None = typer.Option(
        None, "--database", "-d", help="Database name (knowledge, skills, router, memory)"
    ),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum versions to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List table historical versions (snapshot timeline)."""
    db_name, table_name = _resolve_db_and_table(database, table)
    versions = run_async_blocking(_list_versions(db_name, table_name))
    versions = versions[: max(0, limit)]

    if json_output:
        print(
            json.dumps(
                {
                    "database": db_name,
                    "table": table_name,
                    "versions": versions,
                },
                indent=2,
            )
        )
        return

    if not versions:
        _console.print(f"[yellow]No versions found for '{table_name}' in '{db_name}'.[/yellow]")
        return

    table_view = Table(title=f"Versions: {table_name} [{db_name}]", box=ROUNDED)
    table_view.add_column("Version", style="yellow")
    table_view.add_column("Timestamp", style="cyan")
    table_view.add_column("Meta", style="dim")
    for row in versions:
        version_id = row.get("version") or row.get("version_id") or "-"
        ts = row.get("timestamp") or row.get("commit_timestamp") or "-"
        meta = {
            k: v
            for k, v in row.items()
            if k not in {"version", "version_id", "timestamp", "commit_timestamp"}
        }
        table_view.add_row(str(version_id), str(ts), json.dumps(meta) if meta else "-")
    _console.print(table_view)


@db_app.command("fragments")
def db_fragments(
    table: str = typer.Argument(..., help="Table name (e.g., skills, knowledge_chunks)"),
    database: str | None = typer.Option(
        None, "--database", "-d", help="Database name (knowledge, skills, router, memory)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show fragment-level stats for a table."""
    db_name, table_name = _resolve_db_and_table(database, table)
    fragments = run_async_blocking(_get_fragment_stats(db_name, table_name))

    if json_output:
        print(
            json.dumps(
                {
                    "database": db_name,
                    "table": table_name,
                    "fragments": fragments,
                },
                indent=2,
            )
        )
        return

    if not fragments:
        _console.print(
            f"[yellow]No fragment stats found for '{table_name}' in '{db_name}'.[/yellow]"
        )
        return

    table_view = Table(title=f"Fragments: {table_name} [{db_name}]", box=ROUNDED)
    table_view.add_column("Fragment", style="cyan")
    table_view.add_column("Rows", style="yellow")
    table_view.add_column("Files", style="dim")
    for frag in fragments:
        fragment_id = frag.get("id", "-")
        rows = frag.get("num_rows", "-")
        files = frag.get("num_files", "-")
        table_view.add_row(str(fragment_id), str(rows), str(files))
    _console.print(table_view)


@db_app.command("add-columns")
def db_add_columns(
    table: str = typer.Argument(..., help="Target table name"),
    columns_json: str = typer.Option(
        ...,
        "--columns-json",
        help='JSON array, e.g. \'[{"name":"tag","data_type":"Utf8","nullable":true}]\'',
    ),
    database: str | None = typer.Option(
        None, "--database", "-d", help="Database name (knowledge, skills, router, memory)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Add new nullable columns to a table."""
    try:
        columns = json.loads(columns_json)
        if not isinstance(columns, list):
            raise ValueError("columns_json must be a JSON array")
    except Exception as e:
        raise typer.BadParameter(f"Invalid --columns-json: {e}") from e

    db_name, table_name = _resolve_db_and_table(database, table)
    ok = run_async_blocking(_add_columns(db_name, table_name, columns))

    if json_output:
        print(json.dumps({"database": db_name, "table": table_name, "ok": bool(ok)}, indent=2))
        return

    if ok:
        _console.print(f"[green]Added columns on '{table_name}' ({db_name}).[/green]")
    else:
        _console.print(f"[red]Failed to add columns on '{table_name}' ({db_name}).[/red]")


@db_app.command("alter-columns")
def db_alter_columns(
    table: str = typer.Argument(..., help="Target table name"),
    alterations_json: str = typer.Option(
        ...,
        "--alterations-json",
        help='JSON array, e.g. \'[{"type":"rename","old_name":"a","new_name":"b"}]\'',
    ),
    database: str | None = typer.Option(
        None, "--database", "-d", help="Database name (knowledge, skills, router, memory)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Alter table columns (rename / nullability)."""
    try:
        alterations = json.loads(alterations_json)
        if not isinstance(alterations, list):
            raise ValueError("alterations_json must be a JSON array")
    except Exception as e:
        raise typer.BadParameter(f"Invalid --alterations-json: {e}") from e

    db_name, table_name = _resolve_db_and_table(database, table)
    ok = run_async_blocking(_alter_columns(db_name, table_name, alterations))

    if json_output:
        print(json.dumps({"database": db_name, "table": table_name, "ok": bool(ok)}, indent=2))
        return

    if ok:
        _console.print(f"[green]Altered columns on '{table_name}' ({db_name}).[/green]")
    else:
        _console.print(f"[red]Failed to alter columns on '{table_name}' ({db_name}).[/red]")


@db_app.command("drop-columns")
def db_drop_columns(
    table: str = typer.Argument(..., help="Target table name"),
    columns: Annotated[list[str], typer.Option("--column", "-c", help="Column name to drop")] = ...,
    database: str | None = typer.Option(
        None, "--database", "-d", help="Database name (knowledge, skills, router, memory)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Drop columns from a table."""
    db_name, table_name = _resolve_db_and_table(database, table)
    ok = run_async_blocking(_drop_columns(db_name, table_name, columns))

    if json_output:
        print(
            json.dumps(
                {"database": db_name, "table": table_name, "columns": columns, "ok": bool(ok)},
                indent=2,
            )
        )
        return

    if ok:
        _console.print(f"[green]Dropped columns on '{table_name}' ({db_name}).[/green]")
    else:
        _console.print(f"[red]Failed to drop columns on '{table_name}' ({db_name}).[/red]")


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

        with suppress(ValueError, TypeError):
            total_size += info.get("size_mb", 0)

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


@db_app.command("validate-schema")
def db_validate_schema(
    database: str = typer.Argument(
        None,
        help="Database to validate (skills, router). If omitted, validates both.",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Check that vector tables have no legacy 'keywords' in metadata (contract: routing_keywords only).

    Use after reindex or for periodic audit. Fails with non-zero exit if any legacy rows are found.

    Examples:
        omni db validate-schema
        omni db validate-schema skills
        omni db validate-schema router --json
    """
    from omni.foundation.bridge import RustVectorStore

    tables_to_check: list[tuple[str, str]] = []
    if database:
        db_lower = database.lower()
        if db_lower not in ("skills", "router"):
            _console.print(f"[red]Unknown database: {database}. Use skills or router.[/red]")
            raise typer.Exit(1)
        tables_to_check.append((db_lower, db_lower))
    else:
        tables_to_check = [("skills", "skills"), ("router", "router")]

    report: dict[str, Any] = {}
    exit_code = 0
    for db_name, table_name in tables_to_check:
        try:
            db_path = get_database_path(db_name)
            store = RustVectorStore(db_path, enable_keyword_index=True)
            entries = run_async_blocking(store.list_all(table_name))
            val = validate_vector_table_contract(entries)
            report[table_name] = val
            if val.get("legacy_keywords_count", 0) > 0:
                exit_code = 1
        except Exception as e:
            report[table_name] = {
                "total": 0,
                "legacy_keywords_count": 0,
                "sample_ids": [],
                "error": str(e),
            }
            exit_code = 1

    if json_output:
        print(json.dumps(report, indent=2))
        raise typer.Exit(exit_code)

    table = Table(title="Schema contract validation (no legacy 'keywords')", box=ROUNDED)
    table.add_column("Table", style="cyan")
    table.add_column("Total", justify="right", style="dim")
    table.add_column("Legacy keywords", justify="right", style="red")
    table.add_column("Status", style="green")
    for name, info in report.items():
        total = info.get("total", 0)
        legacy = info.get("legacy_keywords_count", 0)
        err = info.get("error")
        if err:
            table.add_row(name, "-", "-", f"[red]Error: {err}[/red]")
        elif legacy > 0:
            sample = info.get("sample_ids", [])[:3]
            table.add_row(name, str(total), str(legacy), f"[red]Fail (e.g. {sample})[/red]")
        else:
            table.add_row(name, str(total), "0", "[green]OK[/green]")
    _console.print(table)
    if exit_code != 0:
        _console.print(
            "[yellow]Contract: metadata must use 'routing_keywords' only; run reindex with --clear if needed.[/yellow]"
        )
        raise typer.Exit(exit_code)


@db_app.command("count")
def db_count(
    table: str = typer.Argument(..., help="Table name (e.g., knowledge_chunks, skills)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Count records in a specific table."""
    # Determine database path based on table name
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


def register_db_command(parent_app: typer.Typer) -> None:
    """Register the db command with the parent app."""
    parent_app.add_typer(db_app, name="db")


__all__ = ["db_app", "register_db_command"]
