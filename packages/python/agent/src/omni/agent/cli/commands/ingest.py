"""ingest.py - Ingest Command for Knowledge Indexing

Provides commands to index documentation into vector store using the new Librarian.

Usage:
    omni ingest knowledge    # Index documentation
    omni ingest skills       # Index skills
    omni ingest all          # Index everything
    omni ingest status       # Show ingest status
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

console = Console()

ingest_app = typer.Typer(
    name="ingest",
    help="Index content into knowledge base (documentation, skills)",
    invoke_without_command=True,
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
    console.print(Panel(grid, title="Ingest Complete", border_style="green"))


def _find_markdown_files(directory: str) -> list[str]:
    """Find all markdown files in a directory using Path.walk() (Python 3.12+)."""
    path = Path(directory)
    if not path.is_dir():
        return []

    files = []
    for root, _, filenames in path.walk():
        for filename in filenames:
            if filename.endswith((".md", ".markdown")):
                files.append(str(root / filename))
    return files


@ingest_app.command("knowledge", help="Index documentation into knowledge base")
def ingest_knowledge(
    docs_dir: str = typer.Option("docs/", "--dir", "-d", help="Documentation directory"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logs"),
):
    """
    Index Markdown documentation into the knowledge vector store.

    Scans the specified directory for .md files and indexes them
    for semantic search.

    Examples:
        omni ingest knowledge                     # Index docs/
        omni ingest knowledge --dir assets/how-to # Index assets/how-to
        omni ingest knowledge --json              # JSON output
    """
    from omni.core.knowledge.librarian import Librarian

    try:
        librarian = Librarian(collection="knowledge")

        if not librarian.is_ready:
            console.print("[red]Error: Knowledge base not ready[/red]")
            raise typer.Exit(1)

        # Find markdown files
        files = _find_markdown_files(docs_dir)
        if not files:
            console.print(f"No Markdown files found in {docs_dir}")
            return

        console.print(f"Found {len(files)} documents in {docs_dir}")

        # Ingest files
        added = 0
        for file_path in files:
            if librarian.ingest_file(file_path, {"type": "documentation"}):
                added += 1

        stats = {"files_found": len(files), "files_indexed": added}
        _print_ingest_result("knowledge", stats, json_output)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@ingest_app.command("skills", help="Index skills into skills table")
def ingest_skills(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logs"),
):
    """
    Index skill tools into the skills vector table.

    Scans the skills directory and indexes skill metadata for routing.

    Examples:
        omni ingest skills                # Incremental sync
        omni ingest skills --clear        # Full rebuild
        omni ingest skills --json         # JSON output
    """
    from omni.core.skills.discovery import SkillDiscoveryService
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        skills_path = str(SKILLS_DIR())

        if not Path(skills_path).is_dir():
            console.print(f"[yellow]Skills directory not found: {skills_path}[/yellow]")
            return

        discovery = SkillDiscoveryService()

        # discover_all uses the Rust-First Indexing from the scanner
        skills = discovery.discover_all()

        stats = {"skills_found": len(skills)}
        _print_ingest_result("skills", stats, json_output)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


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
    from omni.core.knowledge.librarian import Librarian
    from omni.core.skills.discovery import SkillDiscoveryService
    from omni.foundation.config.skills import SKILLS_DIR

    combined_stats = {}

    try:
        # Index knowledge
        console.print("Indexing knowledge...")
        librarian = Librarian(collection="knowledge")

        if librarian.is_ready:
            if clear:
                librarian.clear()

            files = _find_markdown_files("docs/")
            added = 0
            for file_path in files:
                if librarian.ingest_file(file_path, {"type": "documentation"}):
                    added += 1

            combined_stats["knowledge"] = {"files_found": len(files), "files_indexed": added}
            console.print(f"  Knowledge: {added} files indexed")
        else:
            console.print("  [yellow]Knowledge base not available[/yellow]")
            combined_stats["knowledge"] = {"files_found": 0, "files_indexed": 0}

        # Index skills
        console.print("Indexing skills...")
        discovery = SkillDiscoveryService()
        skills_path = str(SKILLS_DIR())

        if Path(skills_path).is_dir():
            skills = discovery.discover_all()
            combined_stats["skills"] = {"skills_found": len(skills)}
            console.print(f"  Skills: {len(skills)} skills indexed")
        else:
            console.print("  [yellow]Skills directory not found[/yellow]")
            combined_stats["skills"] = {"skills_found": 0}

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

            console.print(Panel(grid, title="Ingest Complete", border_style="green"))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


@ingest_app.command("status", help="Show ingest status")
def ingest_status(json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")):
    """
    Show current ingest status for all tables.

    Displays the number of indexed items in each table.

    Examples:
        omni ingest status               # Show counts
        omni ingest status --json        # JSON output
    """
    from omni.core.knowledge.librarian import Librarian

    try:
        # Knowledge status
        librarian = Librarian(collection="knowledge")
        k_stats = librarian.get_stats()

        stats = {
            "knowledge": {
                "ready": k_stats.get("ready", False),
                "collection": k_stats.get("collection", "knowledge"),
            }
        }

        if json_output:
            import json

            print(json.dumps(stats, indent=2))
        else:
            grid = Table.grid(expand=True)
            grid.add_column()
            grid.add_row("[bold]Ingest Status[/bold]")
            grid.add_row("")

            for _table_name, table_stats in stats.items():
                metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
                metrics.add_column("Component")
                metrics.add_column("Status", style="yellow")

                for key, value in table_stats.items():
                    status_icon = "[green]✓[/green]" if value else "[red]✗[/red]"
                    metrics.add_row(f"{key.title()} {status_icon}", str(value))

                grid.add_row(metrics)

            console.print(Panel(grid, title="Status", border_style="blue"))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e


def register_ingest_command(parent_app: typer.Typer) -> None:
    """Register the ingest command with the parent app."""
    parent_app.add_typer(ingest_app, name="ingest")


__all__ = ["ingest_app", "register_ingest_command"]
