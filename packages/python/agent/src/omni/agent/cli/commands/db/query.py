"""db query / list / search subcommands."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.box import ROUNDED
from rich.table import Table

from omni.foundation.config import get_database_path
from omni.foundation.utils.asyncio import run_async_blocking

from ._resolver import DB_TO_DEFAULT_TABLE, _console, _list_databases, db_app


async def _query_knowledge(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Query the knowledge base using Librarian."""
    from omni.core.knowledge.librarian import Librarian

    librarian = Librarian()
    results = librarian.query(query, limit=limit)

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
    store = RustVectorStore(db_path, 1024, True)

    embed_service = get_embedding_service()
    vectors = embed_service.embed(query)
    query_vector = vectors[0] if vectors else []

    results = await store.search_tools(
        table_name=table_name,
        query_vector=query_vector,
        query_text=query,
        limit=limit,
        threshold=0.0,
    )

    return results


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

    table = Table(title=f"Query Results: {query}", box=ROUNDED)
    table.add_column("Score", style="yellow", width=8)
    table.add_column("File", style="cyan")
    table.add_column("Lines", style="dim", width=8)
    table.add_column("Preview", style="white")

    for res in results:
        preview = res["text"].replace("\n", " ")[:100]
        table.add_row(f"{res['score']:.4f}", res["path"], res["lines"], preview)

    _console.print(table)


@db_app.command("search")
def db_search(
    query: str = typer.Argument(..., help="Search query"),
    database: str = typer.Argument("skills", help="Database to search (knowledge, skills, memory)"),
    limit: int = typer.Option(1, "--limit", "-n", help="Maximum results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Search any database (knowledge, skills, memory).

    Examples:
        omni db search "skill.discover" skills
        omni db search "python async" knowledge
        omni db search "git commit" skills
    """
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

    if database == "skills":
        for i, res in enumerate(results):
            if i > 0:
                _console.print()

            name = res.get("tool_name", res.get("name", "-"))
            skill = res.get("skill_name", "-")
            score = res.get("score", 0.0)
            _console.print(
                f"[bold cyan]{name}[/bold cyan] [magenta]({skill})[/magenta]"
                f" [yellow]score={score:.4f}[/yellow]"
            )

            grid = Table.grid(expand=True)
            grid.add_column(style="dim", width=18)
            grid.add_column()

            for key, value in res.items():
                if key == "score":
                    continue
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
