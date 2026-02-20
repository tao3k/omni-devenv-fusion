"""knowledge.py - Knowledge Base Management

Commands for managing project knowledge base.

This module provides bridges between:
- link-graph backend for notebook graph management
- Librarian for code indexing
- Rust Knowledge Graph for entity extraction

Usage:
    omni knowledge stats             # Show statistics
    omni knowledge ingest <path>    # Ingest project code to Librarian
    omni knowledge analyze         # Analyze knowledge graph (PyArrow)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

knowledge_app = typer.Typer(
    name="knowledge",
    help="Manage knowledge base (LinkGraph + Librarian + Knowledge Graph)",
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
    """Show knowledge base statistics from configured LinkGraph backend.

    Examples:
        omni knowledge stats
    """
    try:
        from omni.foundation.config.link_graph import get_link_graph_notebook_dir
        from omni.foundation.utils.asyncio import run_async_blocking
        from omni.rag.link_graph import get_link_graph_backend

        knowledge_dir = get_link_graph_notebook_dir()

        backend = get_link_graph_backend(notebook_dir=str(knowledge_dir))
        stats = run_async_blocking(backend.stats())

        _print_stats(stats)

    except ImportError as e:
        console.print("[red]LinkGraph backend is not available[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e


@knowledge_app.command("recall")
def knowledge_recall(
    query: str = typer.Argument(..., help="Natural language query"),
    limit: int = typer.Option(5, "--limit", "-l", help="Max results (1-10)"),
    collection: str = typer.Option(
        "knowledge_chunks", "--collection", "-c", help="Vector collection"
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON only"),
) -> None:
    """Semantic recall over the knowledge vector store.

    Delegates to skill runner (fast path or kernel). For full dual-core boost
    the runner loads the knowledge skill.

    Examples:
        omni knowledge recall "RAG Anything"
        omni knowledge recall "how does routing work" --limit 3 --json
    """
    from omni.core.skills import run_skill
    from omni.foundation.utils.asyncio import run_async_blocking

    limit = min(max(1, int(limit)), 10)
    cmd_args = {"query": query, "limit": limit, "collection": collection}

    try:
        out = run_async_blocking(run_skill("knowledge", "recall", cmd_args))
        if isinstance(out, dict):
            out = json.dumps(out, indent=2, ensure_ascii=False)
        out_str = out if isinstance(out, str) else json.dumps(out, indent=2)
        if json_output:
            console.print(out_str)
            return
        data = json.loads(out_str)
        if data.get("status") == "unavailable":
            console.print(f"[red]{data.get('message', 'Unavailable')}[/red]")
            raise typer.Exit(1)
        console.print(f"[bold]Recall[/bold] query={query!r} limit={limit}")
        for i, r in enumerate(data.get("results", [])[:limit], 1):
            src = r.get("source", "")
            score = r.get("score", 0)
            content = (r.get("content") or "")[:200]
            if len(r.get("content") or "") > 200:
                content += "..."
            console.print(f"  [dim]{i}. [{score:.2f}] {src}[/dim]")
            console.print(f"    {content}")
    except Exception as e:
        console.print(f"[red]Recall failed: {e}[/red]")
        raise typer.Exit(1) from e


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
        raise typer.Exit(1) from e


def register_knowledge_command(parent_app: typer.Typer) -> None:
    """Register the knowledge command with the parent app."""
    from omni.agent.cli.load_requirements import register_requirements

    register_requirements("knowledge", ollama=True, embedding_index=True)
    parent_app.add_typer(knowledge_app, name="knowledge")


__all__ = ["knowledge_app", "register_knowledge_command"]
