"""db compact / index / partition / query-metrics / DDL subcommands."""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer
from rich.table import Table

from omni.foundation.utils.asyncio import run_async_blocking

from . import _resolver
from ._resolver import (
    DB_TO_DEFAULT_TABLE,
    _console,
    _resolve_db_and_table,
    db_app,
)


# ---------------------------------------------------------------------------
# Backend helpers
# ---------------------------------------------------------------------------


def _compact_table(database: str, table: str) -> dict[str, Any]:
    store = _resolver._get_rust_store(database)
    return store.compact(table)


def _check_migrations(database: str, table: str) -> list[dict[str, Any]]:
    store = _resolver._get_rust_store(database)
    return store.check_migrations(table)


def _migrate_table(database: str, table: str) -> dict[str, Any]:
    store = _resolver._get_rust_store(database)
    return store.migrate(table)


def _get_query_metrics(database: str, table: str) -> dict[str, Any]:
    store = _resolver._get_rust_store(database)
    return store.get_query_metrics(table)


def _get_index_cache_stats(database: str, table: str) -> dict[str, Any]:
    store = _resolver._get_rust_store(database)
    return store.get_index_cache_stats(table)


def _create_index(
    database: str,
    table: str,
    index_type: str,
    column: str | None = None,
) -> dict[str, Any]:
    store = _resolver._get_rust_store(database)
    kind = index_type.lower()
    if kind == "btree":
        if not column:
            raise ValueError("--column is required for type btree")
        return store.create_btree_index(table, column)
    if kind == "bitmap":
        if not column:
            raise ValueError("--column is required for type bitmap")
        return store.create_bitmap_index(table, column)
    if kind == "hnsw":
        return store.create_hnsw_index(table)
    if kind in ("optimal-vector", "optimal_vector"):
        return store.create_optimal_vector_index(table)
    raise ValueError(
        f"Unknown index type: {index_type}. Use btree, bitmap, hnsw, or optimal-vector."
    )


def _suggest_partition_column(database: str, table: str) -> str | None:
    store = _resolver._get_rust_store(database)
    return store.suggest_partition_column(table)


async def _add_columns(database: str, table: str, columns: list[dict[str, Any]]) -> bool:
    store = _resolver._get_rust_store(database)
    return await store.add_columns(table, columns)


async def _alter_columns(database: str, table: str, alterations: list[dict[str, Any]]) -> bool:
    store = _resolver._get_rust_store(database)
    return await store.alter_columns(table, alterations)


async def _drop_columns(database: str, table: str, columns: list[str]) -> bool:
    store = _resolver._get_rust_store(database)
    return await store.drop_columns(table, columns)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@db_app.command("migrate")
def db_migrate(
    database: str = typer.Argument(..., help="Database (knowledge, skills, memory)"),
    table: str | None = typer.Option(
        None, "--table", "-t", help="Table name (default: DB default)"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Apply migrations; default is dry-run"),
    strategy: str = typer.Option(
        "rewrite",
        "--strategy",
        "-s",
        help="Migration strategy: rewrite (full table rewrite, bounded memory). in-place is planned.",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Check or apply schema migrations for a table (e.g. v1→v2 TOOL_NAME Dictionary)."""
    db_name = database.lower()
    table_name = table or DB_TO_DEFAULT_TABLE.get(db_name, db_name)
    try:
        pending = _check_migrations(db_name, table_name)
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            _console.print(f"[red]check_migrations failed: {e}[/red]")
        raise typer.Exit(1) from e

    if strategy != "rewrite":
        if json_output:
            print(
                json.dumps({"error": f"Unsupported strategy: {strategy}. Use rewrite."}, indent=2)
            )
        else:
            _console.print(f"[red]Unsupported strategy: {strategy}. Use --strategy rewrite.[/red]")
        raise typer.Exit(1)

    if json_output:
        out = {"database": db_name, "table": table_name, "pending": pending, "strategy": strategy}
        if force:
            result = _migrate_table(db_name, table_name)
            out["migrate_result"] = result
        print(json.dumps(out, indent=2))
        return

    if not pending:
        _console.print(
            f"[green]No pending migrations[/green] for [cyan]{db_name}/{table_name}[/cyan]"
        )
        return

    _console.print(f"[yellow]Pending migrations[/yellow] for [cyan]{db_name}/{table_name}[/cyan]:")
    for item in pending:
        _console.print(
            f"  {item.get('from_version', '?')} → {item.get('to_version', '?')}: {item.get('description', '')}"
        )

    if not force:
        _console.print("[dim]Run with --force to apply.[/dim]")
        return

    try:
        result = _migrate_table(db_name, table_name)
    except Exception as e:
        _console.print(f"[red]migrate failed: {e}[/red]")
        raise typer.Exit(1) from e

    applied = result.get("applied", [])
    rows = result.get("rows_processed", 0)
    _console.print(f"[green]Applied {len(applied)} migration(s)[/green], rows_processed={rows}")


@db_app.command("compact")
def db_compact(
    database: str = typer.Argument(..., help="Database to compact (knowledge, skills, memory)"),
    table: str | None = typer.Option(
        None, "--table", "-t", help="Table name (default: DB default)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Run compaction (cleanup + compact_files) on a table to reduce fragments."""
    db_name = database.lower()
    table_name = table or DB_TO_DEFAULT_TABLE.get(db_name, db_name)
    try:
        stats = _compact_table(db_name, table_name)
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            _console.print(f"[red]Compact failed: {e}[/red]")
        raise typer.Exit(1) from e

    if json_output:
        print(json.dumps({"database": db_name, "table": table_name, "compaction": stats}, indent=2))
        return

    if stats.get("error"):
        _console.print(f"[red]{stats['error']}[/red]")
        raise typer.Exit(1)

    _console.print(f"[green]Compacted {db_name}/{table_name}[/green]")
    grid = Table.grid(expand=True)
    grid.add_column(style="dim")
    grid.add_column()
    for k, v in stats.items():
        grid.add_row(k, str(v))
    _console.print(grid)


@db_app.command("index-stats")
def db_index_stats(
    table: str = typer.Argument(..., help="Table name (e.g., skills, knowledge_chunks)"),
    database: str | None = typer.Option(None, "--database", "-d", help="Database name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show index cache stats (entry count, hit rate) for a table."""
    db_name, table_name = _resolve_db_and_table(database, table)
    try:
        stats = _get_index_cache_stats(db_name, table_name)
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            _console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if json_output:
        print(
            json.dumps({"database": db_name, "table": table_name, "index_cache": stats}, indent=2)
        )
        return

    _console.print(f"[cyan]{db_name}/{table_name}[/cyan] index cache")
    grid = Table.grid(expand=True)
    grid.add_column(style="dim")
    grid.add_column()
    for k, v in stats.items():
        grid.add_row(k, str(v))
    _console.print(grid)


index_app = typer.Typer(
    name="index",
    help="Create indices (btree, bitmap, hnsw, optimal-vector). Uses LanceDB 2.x APIs.",
)
db_app.add_typer(index_app, name="index")


@index_app.command("create")
def db_index_create(
    table: str = typer.Argument(..., help="Table name (e.g., skills, knowledge_chunks)"),
    type: str = typer.Option(
        ..., "--type", "-t", help="Index type: btree, bitmap, hnsw, optimal-vector"
    ),
    column: str | None = typer.Option(
        None, "--column", "-c", help="Column name (required for btree and bitmap)"
    ),
    database: str | None = typer.Option(None, "--database", "-d", help="Database name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Create an index on a table."""
    db_name, table_name = _resolve_db_and_table(database, table)
    try:
        result = _create_index(db_name, table_name, type, column)
    except (ValueError, Exception) as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            _console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if json_output:
        print(
            json.dumps(
                {"database": db_name, "table": table_name, "type": type, "result": result},
                indent=2,
            )
        )
        return

    _console.print(f"[green]Created {type} index[/green] on [cyan]{db_name}/{table_name}[/cyan]")
    grid = Table.grid(expand=True)
    grid.add_column(style="dim")
    grid.add_column()
    for k, v in result.items():
        grid.add_row(k, str(v))
    _console.print(grid)


@db_app.command("partition-suggest")
def db_partition_suggest(
    table: str = typer.Argument(..., help="Table name (e.g., skills, knowledge_chunks)"),
    database: str | None = typer.Option(None, "--database", "-d", help="Database name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Suggest a partition column for pre-partition decisions."""
    db_name, table_name = _resolve_db_and_table(database, table)
    try:
        column = _suggest_partition_column(db_name, table_name)
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            _console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if json_output:
        print(
            json.dumps(
                {"database": db_name, "table": table_name, "suggested_column": column}, indent=2
            )
        )
        return

    if column:
        _console.print(f"[green]Suggested partition column:[/green] [cyan]{column}[/cyan]")
        _console.print(f"[dim]{db_name}/{table_name}[/dim]")
    else:
        _console.print(
            "[dim]No partition suggestion (table too small or schema not suitable).[/dim]"
        )
        _console.print(f"[dim]{db_name}/{table_name}[/dim]")


@db_app.command("query-metrics")
def db_query_metrics(
    table: str = typer.Argument(..., help="Table name (e.g., skills, knowledge_chunks)"),
    database: str | None = typer.Option(None, "--database", "-d", help="Database name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show per-table query metrics."""
    db_name, table_name = _resolve_db_and_table(database, table)
    try:
        metrics = _get_query_metrics(db_name, table_name)
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            _console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if json_output:
        print(json.dumps({"database": db_name, "table": table_name, "metrics": metrics}, indent=2))
        return

    _console.print(f"[cyan]{db_name}/{table_name}[/cyan] query metrics")
    grid = Table.grid(expand=True)
    grid.add_column(style="dim")
    grid.add_column()
    for k, v in metrics.items():
        grid.add_row(k, str(v))
    _console.print(grid)


@db_app.command("add-columns")
def db_add_columns(
    table: str = typer.Argument(..., help="Target table name"),
    columns_json: str = typer.Option(
        ...,
        "--columns-json",
        help='JSON array, e.g. \'[{"name":"tag","data_type":"Utf8","nullable":true}]\'',
    ),
    database: str | None = typer.Option(None, "--database", "-d", help="Database name"),
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
    database: str | None = typer.Option(None, "--database", "-d", help="Database name"),
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
    database: str | None = typer.Option(None, "--database", "-d", help="Database name"),
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
