"""ingest.py - Ingest Command for Knowledge/Memory Indexing

Provides commands to index documentation and memories into vector store.

Usage:
    omni ingest knowledge    # Index documentation
    omni ingest all          # Index everything
"""

from __future__ import annotations

import asyncio
import typer

from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED

from common.lib import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

ingest_app = typer.Typer(
    name="ingest",
    help="Index content into vector store (knowledge, skills, memory)",
)


def _print_ingest_result(name: str, stats: dict, json_output: bool = False):
    """Print ingest result with stats."""
    if json_output:
        import json

        print(json.dumps({name: stats}, indent=2))
        return

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(f"[bold cyan]Ingest:[/bold cyan] {name}")
    grid.add_row("")

    metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
    metrics.add_column("Metric")
    metrics.add_column("Value", style="yellow")

    for key, value in stats.items():
        metrics.add_row(key.title(), str(value))

    grid.add_row(metrics)
    Panel(grid, title="Ingest Complete", border_style="green")


@ingest_app.command("knowledge", help="Index documentation into knowledge table")
def ingest_knowledge(
    docs_dir: str = typer.Option("docs/", "--dir", "-d", help="Documentation directory"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logs"),
):
    """
    Index Markdown documentation into the knowledge vector table.

    Scans the specified directory for .md files and indexes them
    for semantic search.

    Examples:
        omni ingest knowledge                     # Index docs/
        omni ingest knowledge --dir assets/how-to # Index assets/how-to
        omni ingest knowledge --json              # JSON output
    """
    import logging

    from agent.core.knowledge.indexer import sync_knowledge, scan_markdown_files
    from agent.core.vector_store import get_vector_memory

    # Setup logging
    if not verbose:
        logging.getLogger("agent.core.vector_store").setLevel(logging.WARNING)

    try:
        vm = get_vector_memory()

        # Scan first to show count
        records = scan_markdown_files(docs_dir)
        if not records:
            print(f"No Markdown files found in {docs_dir}")
            return

        print(f"Found {len(records)} documents in {docs_dir}")

        # Sync knowledge
        stats = asyncio.run(sync_knowledge(vm, docs_dir, "knowledge"))

        _print_ingest_result("knowledge", stats, json_output)

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


@ingest_app.command("skills", help="Index skills into skills table")
def ingest_skills(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logs"),
):
    """
    Index skill tools into the skills vector table.

    This is equivalent to 'omni skill reindex' but as an ingest subcommand.

    Examples:
        omni ingest skills                # Incremental sync
        omni ingest skills --clear        # Full rebuild
        omni ingest skills --json         # JSON output
    """
    import logging

    from agent.core.vector_store import get_vector_memory
    from common.skills_path import SKILLS_DIR

    if not verbose:
        logging.getLogger("agent.core.vector_store").setLevel(logging.WARNING)

    try:
        vm = get_vector_memory()
        skills_path = str(SKILLS_DIR())

        if clear:
            vm.store.drop_table("skills")

        count = asyncio.run(vm.index_skill_tools_with_schema(skills_path, "skills"))

        stats = {"total_tools_indexed": count}
        _print_ingest_result("skills", stats, json_output)

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


@ingest_app.command("all", help="Index knowledge and skills")
def ingest_all(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing indexes first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logs"),
):
    """
    Index all content: documentation and skills.

    Combines 'omni ingest knowledge' and 'omni ingest skills' into one command.

    Examples:
        omni ingest all                   # Index everything
        omni ingest all --clear           # Full rebuild
        omni ingest all --json            # JSON output
    """
    import logging

    from agent.core.vector_store import get_vector_memory
    from agent.core.knowledge.indexer import sync_knowledge, scan_markdown_files
    from common.skills_path import SKILLS_DIR

    if not verbose:
        logging.getLogger("agent.core.vector_store").setLevel(logging.WARNING)

    combined_stats = {}

    try:
        vm = get_vector_memory()

        # Index knowledge
        print("Indexing knowledge...")
        records = scan_markdown_files("docs/")
        if records:
            k_stats = asyncio.run(sync_knowledge(vm, "docs/", "knowledge"))
            combined_stats["knowledge"] = k_stats
            print(
                f"  Knowledge: {k_stats.get('added', 0)} added, {k_stats.get('updated', 0)} updated"
            )
        else:
            print("  No documents found in docs/")
            combined_stats["knowledge"] = {"added": 0, "updated": 0, "deleted": 0, "total": 0}

        # Index skills
        print("Indexing skills...")
        skills_path = str(SKILLS_DIR())

        if clear:
            vm.store.drop_table("skills")

        count = asyncio.run(vm.index_skill_tools_with_schema(skills_path, "skills"))
        combined_stats["skills"] = {"total_tools_indexed": count}
        print(f"  Skills: {count} tools indexed")

        # Print summary
        if json_output:
            import json

            print(json.dumps(combined_stats, indent=2))
        else:
            grid = Table.grid(expand=True)
            grid.add_column()
            grid.add_row("[bold cyan]Ingest:[/bold cyan] All Content")
            grid.add_row("")

            for category, stats in combined_stats.items():
                metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
                metrics.add_column(category.title())
                metrics.add_column("Value", style="yellow")

                for key, value in stats.items():
                    metrics.add_row(key.title(), str(value))

                grid.add_row(metrics)
                grid.add_row("")

            Panel(grid, title="Ingest Complete", border_style="green")

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


@ingest_app.command("status", help="Show ingest status")
def ingest_status(json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")):
    """
    Show current ingest status for all tables.

    Displays the number of indexed items in each table.

    Examples:
        omni ingest status               # Show counts
        omni ingest status --json        # JSON output
    """
    from agent.core.vector_store import get_vector_memory

    try:
        vm = get_vector_memory()

        stats = {}

        # Knowledge count
        try:
            if hasattr(vm.store, "query_table"):
                vm.store.query_table("knowledge", limit=1)  # Just verify table exists
                stats["knowledge"] = {"count": "N/A (LanceDB)"}
        except Exception:
            stats["knowledge"] = {"count": "0"}

        # Skills count
        try:
            if hasattr(vm.store, "query_table"):
                stats["skills"] = {"count": "N/A (LanceDB)"}
        except Exception:
            stats["skills"] = {"count": "0"}

        if json_output:
            import json

            print(json.dumps(stats, indent=2))
        else:
            grid = Table.grid(expand=True)
            grid.add_column()
            grid.add_row("[bold]Ingest Status[/bold]")
            grid.add_row("")

            for table_name, table_stats in stats.items():
                metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
                metrics.add_column("Table")
                metrics.add_column("Count", style="yellow")
                metrics.add_row(table_name.title(), list(table_stats.values())[0])

                grid.add_row(metrics)

            Panel(grid, title="Status", border_style="blue")

    except Exception as e:
        print(f"Error: {e}")
        raise typer.Exit(1)


def register_ingest_command(parent_app: typer.Typer) -> None:
    """Register the ingest command with the parent app."""
    parent_app.add_typer(ingest_app, name="ingest")


__all__ = ["ingest_app", "register_ingest_command"]
