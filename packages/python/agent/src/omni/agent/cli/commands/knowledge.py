"""knowledge.py - Knowledge Base Management

Commands for managing project knowledge base.

This module provides bridges between:
- zk CLI tool for notebook management
- Librarian for code indexing
- Rust Knowledge Graph for entity extraction

Usage:
    omni knowledge stats             # Show statistics
    omni knowledge ingest <path>    # Ingest project code to Librarian
    omni knowledge analyze         # Analyze knowledge graph (PyArrow)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

knowledge_app = typer.Typer(
    name="knowledge",
    help="Manage knowledge base (zk notebook + Librarian + Knowledge Graph)",
)


def _print_stats(stats: dict[str, Any]) -> None:
    """Print knowledge base statistics."""
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row("[bold cyan]📚 Knowledge Base Statistics[/bold cyan]")
    grid.add_row("")

    metrics = Table(show_header=True, header_style="bold magenta")
    metrics.add_column("Metric", style="dim")
    metrics.add_column("Value", style="yellow")

    metrics.add_row("Total Notes", str(stats.get("total_notes", 0)))
    metrics.add_row("Orphaned Notes", str(stats.get("orphans", 0)))
    metrics.add_row("Links", str(stats.get("links_in_graph", 0)))
    metrics.add_row("Graph Nodes", str(stats.get("nodes_in_graph", 0)))

    grid.add_row(metrics)
    console.print(Panel(grid, border_style="cyan"))


@knowledge_app.command("stats")
def knowledge_stats():
    """Show knowledge base statistics from zk notebook.

    Examples:
        omni knowledge stats
    """
    try:
        from omni.rag.zk_integration import ZkClient
        from omni.foundation.config.zk import get_zk_notebook_dir

        knowledge_dir = get_zk_notebook_dir()

        if not knowledge_dir.exists():
            console.print("[yellow]Knowledge notebook not found at:[/yellow]")
            console.print(f"  {knowledge_dir}")
            raise typer.Exit(1)

        client = ZkClient(str(knowledge_dir))
        stats = client.get_stats()

        _print_stats(stats)

    except ImportError:
        console.print("[red]ZkClient not available[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@knowledge_app.command("ingest")
def knowledge_ingest(
    path: str = typer.Argument(".", help="Root directory to ingest"),
    clean: bool = typer.Option(False, "--clean", help="Drop existing table first"),
    batch_size: int = typer.Option(50, "--batch", "-b", help="Batch size"),
    limit: int = typer.Option(200, "--limit", "-l", help="Maximum files to process"),
) -> None:
    """Ingest project code into Librarian for code indexing.

    Uses AST-based chunking to index Python and Rust source files.

    Examples:
        omni knowledge ingest
        omni knowledge ingest --limit 100
        omni knowledge ingest /path/to/project --clean
    """
    project_path = Path(path).resolve()

    if not project_path.exists():
        console.print(f"[red]Path does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold blue]🚀 Librarian[/bold blue] - {project_path}")
    console.print(f"[dim]Processing up to {limit} source files...[/dim]")

    try:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(
            project_root=str(project_path),
            batch_size=batch_size,
            max_files=limit,
        )
        result = librarian.ingest(clean=clean)

        result_table = Table(title="Ingestion Results")
        result_table.add_column("Metric")
        result_table.add_column("Value")
        result_table.add_row("Files Processed", str(result["files_processed"]))
        result_table.add_row("Chunks Indexed", str(result["chunks_indexed"]))
        result_table.add_row("Errors", str(result["errors"]))

        console.print(Panel.fit(result_table, title="Complete"))

    except Exception as e:
        console.print(f"[red]Ingestion failed: {e}[/red]")
        raise typer.Exit(1)


@knowledge_app.command("analyze")
def knowledge_analyze():
    """Analyze knowledge graph using PyArrow/Polars.

    Provides statistics and insights about entities and relations.

    Examples:
        omni knowledge analyze
    """
    try:
        from omni.rag import KnowledgeGraphAnalyzer

        analyzer = KnowledgeGraphAnalyzer()
        stats = analyzer.get_stats()

        console.print("[bold]📊 Knowledge Graph Analysis[/bold]\n")
        console.print(f"Entities: {stats.get('total_entities', 0)}")
        console.print(f"Relations: {stats.get('total_relations', 0)}")
        console.print(f"Connectivity: {stats.get('connectivity_ratio', 0):.1%}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def register_knowledge_command(parent_app: typer.Typer) -> None:
    """Register the knowledge command with the parent app."""
    parent_app.add_typer(knowledge_app, name="knowledge")


__all__ = ["knowledge_app", "register_knowledge_command"]
