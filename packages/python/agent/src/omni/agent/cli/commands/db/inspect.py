"""db table-info / versions / fragments / health / validate-schema subcommands."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.box import ROUNDED
from rich.table import Table

from omni.foundation.config import get_database_path
from omni.foundation.services.vector_schema import validate_vector_table_contract
from omni.foundation.utils.asyncio import run_async_blocking

from . import _resolver
from ._resolver import (
    DB_TO_DEFAULT_TABLE,
    _console,
    _resolve_db_and_table,
    db_app,
)


# ---------------------------------------------------------------------------
# Async backend helpers
# ---------------------------------------------------------------------------


async def _get_table_info(database: str, table: str) -> dict[str, Any] | None:
    store = _resolver._get_rust_store(database)
    return await store.get_table_info(table)


async def _list_versions(database: str, table: str) -> list[dict[str, Any]]:
    store = _resolver._get_rust_store(database)
    return await store.list_versions(table)


async def _get_fragment_stats(database: str, table: str) -> list[dict[str, Any]]:
    store = _resolver._get_rust_store(database)
    return await store.get_fragment_stats(table)


def _get_table_health(database: str, table: str) -> dict[str, Any]:
    store = _resolver._get_rust_store(database)
    return store.analyze_table_health(table)


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@db_app.command("table-info")
def db_table_info(
    table: str = typer.Argument(..., help="Table name (e.g., skills, knowledge_chunks)"),
    database: str | None = typer.Option(
        None, "--database", "-d", help="Database name (knowledge, skills, memory)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show table metadata (version, rows, schema, fragments)."""
    db_name, table_name = _resolve_db_and_table(database, table)
    info = run_async_blocking(_get_table_info(db_name, table_name))

    if json_output:
        print(json.dumps({"database": db_name, "table": table_name, "info": info}, indent=2))
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
        None, "--database", "-d", help="Database name (knowledge, skills, memory)"
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
            json.dumps({"database": db_name, "table": table_name, "versions": versions}, indent=2)
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
        None, "--database", "-d", help="Database name (knowledge, skills, memory)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show fragment-level stats for a table."""
    db_name, table_name = _resolve_db_and_table(database, table)
    fragments = run_async_blocking(_get_fragment_stats(db_name, table_name))

    if json_output:
        print(
            json.dumps({"database": db_name, "table": table_name, "fragments": fragments}, indent=2)
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


@db_app.command("health")
def db_health(
    database: str | None = typer.Argument(
        None,
        help="Database to check (knowledge, skills, memory). If omitted, all DBs.",
    ),
    table: str | None = typer.Option(
        None, "--table", "-t", help="Table name (default: DB default)"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show table health: row count, fragments, fragmentation ratio, indices, recommendations."""
    if database:
        db_names = [database.lower()]
    else:
        db_names = list(DB_TO_DEFAULT_TABLE.keys())

    all_reports: dict[str, dict[str, Any]] = {}
    for db_name in db_names:
        table_name = table or DB_TO_DEFAULT_TABLE.get(db_name, db_name)
        try:
            report = _get_table_health(db_name, table_name)
            if report:
                all_reports[f"{db_name}/{table_name}"] = report
            else:
                all_reports[f"{db_name}/{table_name}"] = {"error": "empty or missing table"}
        except Exception as e:
            all_reports[f"{db_name}/{table_name or '?'}"] = {"error": str(e)}

    if json_output:
        print(json.dumps(all_reports, indent=2))
        return

    for key, report in all_reports.items():
        if report.get("error"):
            _console.print(f"[red]{key}[/red]: {report['error']}")
            continue
        tbl = Table(title=f"Health: {key}", box=ROUNDED)
        tbl.add_column("Metric", style="cyan")
        tbl.add_column("Value", style="white")
        tbl.add_row("row_count", str(report.get("row_count", "-")))
        tbl.add_row("fragment_count", str(report.get("fragment_count", "-")))
        tbl.add_row("fragmentation_ratio", str(report.get("fragmentation_ratio", "-")))
        indices = report.get("indices_status") or []
        tbl.add_row("indices_status", json.dumps(indices) if indices else "-")
        recs = report.get("recommendations") or []
        tbl.add_row("recommendations", json.dumps(recs) if recs else "none")
        _console.print(tbl)


@db_app.command("validate-schema")
def db_validate_schema(
    database: str = typer.Argument(
        None, help="Database to validate (skills). If omitted, validates skills."
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Check that vector tables have no legacy 'keywords' in metadata."""
    from omni.foundation.bridge import RustVectorStore

    tables_to_check: list[tuple[str, str]] = []
    if database:
        db_lower = database.lower()
        if db_lower != "skills":
            _console.print("[red]Unknown database. Use: skills.[/red]")
            raise typer.Exit(1)
        tables_to_check.append(("skills", "skills"))
    else:
        tables_to_check = [("skills", "skills")]

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

    tbl = Table(title="Schema contract validation (no legacy 'keywords')", box=ROUNDED)
    tbl.add_column("Table", style="cyan")
    tbl.add_column("Total", justify="right", style="dim")
    tbl.add_column("Legacy keywords", justify="right", style="red")
    tbl.add_column("Status", style="green")
    for name, info in report.items():
        total = info.get("total", 0)
        legacy = info.get("legacy_keywords_count", 0)
        err = info.get("error")
        if err:
            tbl.add_row(name, "-", "-", f"[red]Error: {err}[/red]")
        elif legacy > 0:
            sample = info.get("sample_ids", [])[:3]
            tbl.add_row(name, str(total), str(legacy), f"[red]Fail (e.g. {sample})[/red]")
        else:
            tbl.add_row(name, str(total), "0", "[green]OK[/green]")
    _console.print(tbl)
    if exit_code != 0:
        _console.print(
            "[yellow]Contract: metadata must use 'routing_keywords' only;"
            " run reindex with --clear if needed.[/yellow]"
        )
        raise typer.Exit(exit_code)
