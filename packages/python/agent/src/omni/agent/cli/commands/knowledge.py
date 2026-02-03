"""knowledge.py - Knowledge Base Management

Commands to view and manage the knowledge base (Librarian).

Usage:
    omni knowledge list              # List all knowledge entries
    omni knowledge list -n 20        # Show 20 entries
    omni knowledge list --json       # JSON output
    omni knowledge search <query>    # Search knowledge
    omni knowledge stats             # Show statistics
"""

from __future__ import annotations

from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

knowledge_app = typer.Typer(
    name="knowledge",
    help="Manage knowledge base (Librarian)",
)


def _print_stats(stats: dict[str, Any], json_output: bool = False):
    """Print knowledge base statistics."""
    if json_output:
        import json

        print(json.dumps(stats, indent=2))
        return

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row("[bold cyan]📚 Knowledge Base Statistics[/bold cyan]")
    grid.add_row("")

    metrics = Table(show_header=True, header_style="bold magenta")
    metrics.add_column("Metric", style="dim")
    metrics.add_column("Value", style="yellow")

    metrics.add_row("Total Entries", str(stats.get("total", 0)))
    metrics.add_row("Storage Path", stats.get("storage_path", "N/A"))
    metrics.add_row("Collection", stats.get("collection", "N/A"))
    metrics.add_row(
        "Status", "[green]Ready[/green]" if stats.get("ready") else "[red]Not Ready[/red]"
    )

    grid.add_row(metrics)
    console.print(Panel(grid, border_style="cyan"))


@knowledge_app.command("list")
def knowledge_list(
    limit: int = typer.Option(30, "-n", "--number", help="Maximum entries to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    show_content: bool = typer.Option(False, "-c", "--content", help="Show content preview"),
):
    """
    List all knowledge entries in the knowledge base.

    Examples:
        omni knowledge list
        omni knowledge list -n 50
        omni knowledge list --json
    """
    import asyncio

    try:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(collection="knowledge")
        if not librarian.is_ready:
            console.print("[red]Knowledge base not ready. Run 'omni sync knowledge' first.[/]")
            raise typer.Exit(1)

        entries = asyncio.run(librarian.list_entries(limit=limit))
        total = asyncio.run(librarian.count())

        if json_output:
            import json

            print(
                json.dumps({"total": total, "showing": len(entries), "entries": entries}, indent=2)
            )
            return

        # Clean UX - just show count
        console.print(f"[bold]📚 Knowledge Base[/bold] - [yellow]{total}[/yellow] entries total\n")

        if not entries:
            console.print("[dim]No entries found. Run 'omni sync knowledge' to ingest docs.[/dim]")
            return

        # Simplified table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File", style="cyan", width=35)
        table.add_column("Type", style="yellow", width=12)
        table.add_column("Preview", style="dim")

        for entry in entries:
            source = entry.get("source", "N/A")
            # Shorten path
            if len(source) > 35:
                source = "..." + source[-32:]

            entry_type = entry.get("type", "-")

            if show_content:
                # Try to get content preview from metadata
                preview = "[content hidden]"
            else:
                preview = ""

            table.add_row(source, entry_type, preview)

        console.print(table)
        console.print(
            f"\n[dim]Showing {len(entries)} of {total} entries. Use -n to see more.[/dim]"
        )

    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@knowledge_app.command("analyze")
def knowledge_analyze(
    collection: str = typer.Option("knowledge", "-c", "--collection", help="Collection to analyze"),
    limit: Optional[int] = typer.Option(
        None, "-n", "--number", help="Limit number of top sources to show"
    ),
    export_json: bool = typer.Option(False, "-j", "--json", help="Export analysis as JSON"),
) -> None:
    """Analyze knowledge base statistics using Arrow-native operations.

    Provides insights into document distribution, content size, and coverage.

    Examples:
        omni knowledge analyze
        omni knowledge analyze -n 20
        omni knowledge analyze --json
    """
    try:
        from omni.core.knowledge.analyzer import analyze_knowledge
    except ImportError as e:
        console.print(f"[red]Error: Could not import analyzer module: {e}[/]")
        raise typer.Exit(1)

    try:
        import pyarrow as pa
    except ImportError:
        console.print("[red]Error: pyarrow is required. Install with: pip install pyarrow[/]")
        raise typer.Exit(1)

    # Run analysis
    try:
        result = analyze_knowledge(collection=collection, limit=limit)
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)

    total_entries = result["total_entries"]
    type_dist = result["type_distribution"]
    source_dist = result["source_distribution"]
    total_size = result["total_size_bytes"]
    avg_len = result["avg_content_length"]

    if total_entries == 0:
        console.print("[yellow]No knowledge entries found.[/]")
        console.print("[cyan]Tip: Run 'omni sync knowledge' to index your documentation.[/]")
        raise typer.Exit(0)

    # Display results
    if export_json:
        import json
        from datetime import datetime

        output = {
            "timestamp": datetime.now().isoformat(),
            "collection": collection,
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "avg_content_length": avg_len,
            "type_distribution": type_dist,
            "source_distribution": source_dist,
        }
        console.print(json.dumps(output, indent=2))
        raise typer.Exit(0)

    # Pretty display
    console.print(
        Panel.fit(
            f"[bold]Knowledge Analytics Report[/]\n\n"
            f"Total Entries: [cyan]{total_entries}[/]\n"
            f"Unique Types: [cyan]{len(type_dist)}[/]\n"
            f"Total Size: [cyan]{total_size / 1024:.1f} KB[/]\n"
            f"Avg Length: [cyan]{avg_len:.0f} chars[/]",
            title=f"Analytics: {collection}",
            border_style="blue",
        )
    )

    # Type distribution table
    if type_dist:
        type_table = Table(title="Type Distribution", show_header=True)
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", justify="right", style="green")
        type_table.add_column("Percentage", justify="right", style="yellow")

        sorted_types = sorted(type_dist.items(), key=lambda x: x[1], reverse=True)
        for t_name, count in sorted_types:
            pct = (count / total_entries * 100) if total_entries > 0 else 0
            type_table.add_row(t_name or "unknown", str(count), f"{pct:.1f}%")

        console.print(type_table)

    # Source distribution table
    if source_dist:
        title = f"Top {len(source_dist)} Sources" if limit else "All Sources"
        src_table = Table(title=title, show_header=True)
        src_table.add_column("Source", style="cyan")
        src_table.add_column("Chunks", justify="right", style="green")

        for src, count in source_dist.items():
            # Shorten path
            display_src = src
            if len(display_src) > 50:
                display_src = "..." + display_src[-47:]
            src_table.add_row(display_src, str(count))

        console.print(src_table)


@knowledge_app.command("stats")
def knowledge_stats(json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")):
    """
    Show knowledge base statistics.

    Examples:
        omni knowledge stats
        omni knowledge stats --json
    """
    import asyncio

    try:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(collection="knowledge")
        total = asyncio.run(librarian.count())

        stats = {
            "total": total,
            "storage_path": librarian._storage_path,
            "collection": librarian._collection,
            "ready": librarian.is_ready,
        }

        _print_stats(stats, json_output)

    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "-n", "--number", help="Maximum results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Search the knowledge base.

    Examples:
        omni knowledge search "testing workflow"
        omni knowledge search "commit" -n 5 --json
    """
    import asyncio

    try:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(collection="knowledge")
        if not librarian.is_ready:
            console.print("[red]Knowledge base not ready.[/]")
            raise typer.Exit(1)

        results = asyncio.run(librarian.search(query, limit=limit))

        if json_output:
            import json

            print(
                json.dumps(
                    {
                        "query": query,
                        "total": len(results),
                        "results": [
                            {
                                "id": r.entry.id,
                                "source": r.entry.source,
                                "content": r.entry.content[:200],
                            }
                            for r in results
                        ],
                    },
                    indent=2,
                )
            )
            return

        console.print(
            f"[bold]🔍 Search:[/bold] '{query}' - [yellow]{len(results)}[/yellow] results\n"
        )

        if not results:
            console.print("[dim]No matches found.[/dim]")
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File", style="cyan", width=35)
        table.add_column("Content Preview", style="dim")

        for r in results:
            content = (
                r.entry.content[:100] + "..." if len(r.entry.content) > 100 else r.entry.content
            )
            source = r.entry.source
            if len(source) > 35:
                source = "..." + source[-32:]
            table.add_row(source, content)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        raise typer.Exit(1)


@knowledge_app.command("ingest")
def knowledge_ingest(
    path: str = typer.Argument(".", help="Root directory to ingest"),
    clean: bool = typer.Option(False, "--clean", "-c", help="Drop existing table first"),
    batch_size: int = typer.Option(50, "--batch", "-b", help="Batch size"),
    limit: int = typer.Option(200, "--limit", "-l", help="Maximum files to process (default: 200)"),
) -> None:
    """
    Ingest project code into Knowledge Graph using AST chunking.

    Examples:
        omni knowledge ingest
        omni knowledge ingest --limit 100
        omni knowledge ingest --path /path/to/project --clean
    """
    from pathlib import Path

    project_path = Path(path).resolve()

    if not project_path.exists():
        console.print(f"[red]❌ Path does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold blue]🚀 Librarian[/bold blue] - {project_path}")
    console.print(f"[dim]Processing up to {limit} source files (py, rs, js, ts, go, java)...[/dim]")

    try:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(
            project_root=str(project_path),
            batch_size=batch_size,
            max_files=limit,
        )
        result = librarian.ingest(clean=clean)

        table = Table(title="Ingestion Results")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("Files Processed", str(result["files_processed"]))
        table.add_row("Chunks Indexed", str(result["chunks_indexed"]))
        table.add_row("Errors", str(result["errors"]))

        console.print(Panel.fit(table, title="✅ Complete"))

    except Exception as e:
        console.print(f"[red]❌ Ingestion failed: {e}[/red]")
        raise typer.Exit(1)


@knowledge_app.command("context")
def knowledge_context(
    query: str = typer.Argument(..., help="Query to get context for"),
    limit: int = typer.Option(3, "--limit", "-l", help="Number of context blocks"),
    path: str = typer.Option(".", "--path", help="Project path"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output to file for pasting into prompts"
    ),
) -> None:
    """
    Get formatted context blocks for LLM consumption.

    Examples:
        omni knowledge context "How does the router work?"
        omni knowledge context "AST chunking" -l 5 -o context.md
    """
    import asyncio
    from pathlib import Path

    project_path = Path(path).resolve()

    try:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(project_root=str(project_path))
        context = asyncio.run(librarian.get_context(query, limit=limit))

        if output:
            Path(output).write_text(context)
            console.print(f"[green]Context written to {output}[/green]")
        else:
            console.print(context)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


def register_knowledge_command(parent_app: typer.Typer) -> None:
    """Register the knowledge command with the parent app."""
    parent_app.add_typer(knowledge_app, name="knowledge")


__all__ = ["knowledge_app", "register_knowledge_command"]
