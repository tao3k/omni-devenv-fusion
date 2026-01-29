"""sync.py - Unified Sync Protocol

The "One Ring" command to synchronize all vector indexes and system state.
Consolidates 'ingest knowledge', 'ingest skills', and memory indexing.

Usage:
    omni sync                # Sync EVERYTHING (Default)
    omni sync knowledge      # Sync documentation only
    omni sync skills         # Sync skill registry (Cortex) only
    omni sync memory         # Optimize memory index
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.common import setup_import_paths

# Setup paths before importing omni modules
setup_import_paths()

console = Console()

sync_app = typer.Typer(
    name="sync",
    help="Synchronize system state and vector indexes (knowledge, skills, memory)",
    invoke_without_command=True,  # Allow 'omni sync' to run default action
)


def _print_sync_report(title: str, stats: dict[str, Any], json_output: bool = False):
    """Print a standardized sync report."""
    if json_output:
        import json

        print(json.dumps(stats, indent=2))
        return

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(f"[bold cyan]Sync Operation:[/bold cyan] {title}")
    grid.add_row("")

    metrics = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
    metrics.add_column("Component")
    metrics.add_column("Status", style="yellow")
    metrics.add_column("Details", style="dim")

    for component, info in stats.items():
        status = info.get("status", "unknown")
        icon = "[green]✓[/green]" if status == "success" else "[red]✗[/red]"
        details = info.get("details", "")
        metrics.add_row(f"{component.title()} {icon}", status, str(details))

    grid.add_row(metrics)
    console.print(Panel(grid, title="✨ System Sync Complete ✨", border_style="green"))


def _find_markdown_files(directory: str) -> list[str]:
    """Find all markdown files recursively."""
    path = Path(directory)
    if not path.is_dir():
        return []

    files = []
    # Use walk if available (Python 3.12+), else rglob
    if hasattr(path, "walk"):
        for root, _, filenames in path.walk():
            for filename in filenames:
                if filename.endswith((".md", ".markdown")):
                    files.append(str(root / filename))
    else:
        for p in path.rglob("*"):
            if p.suffix in (".md", ".markdown") and p.is_file():
                files.append(str(p))
    return files


def _sync_knowledge(clear: bool = False) -> dict[str, Any]:
    """Internal logic to sync knowledge base."""
    import asyncio
    from omni.core.knowledge.librarian import Librarian
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeElapsedColumn,
    )

    try:
        librarian = Librarian(collection="knowledge")
        if not librarian.is_ready:
            return {"status": "error", "details": "Knowledge base not ready"}

        if clear:
            librarian.clear()

        # Define source directories
        sources = ["docs", "assets/knowledge", "assets/how-to"]

        # Collect all files first
        all_files = []
        for src in sources:
            all_files.extend(_find_markdown_files(src))

        total_found = len(all_files)
        total_indexed = 0

        if total_found > 0:
            # Use detailed progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Indexing knowledge...", total=total_found)
                for file_path in all_files:
                    if librarian.ingest_file(file_path, {"type": "documentation"}):
                        total_indexed += 1
                    progress.advance(task)

        # Commit cached entries to vector store
        committed = asyncio.run(librarian.commit())

        return {
            "status": "success",
            "details": f"Indexed {total_indexed}/{total_found} docs, committed {committed} entries",
        }
    except Exception as e:
        return {"status": "error", "details": str(e)}


def _sync_skills() -> dict[str, Any]:
    """Internal logic to sync skill registry (Cortex)."""
    from omni.core.skills.discovery import SkillDiscoveryService
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        skills_path = SKILLS_DIR()
        if not skills_path.exists():
            return {"status": "skipped", "details": "Skills dir not found"}

        discovery = SkillDiscoveryService()
        # This triggers the Rust scanner to update the index
        skills = discovery.discover_all()

        return {"status": "success", "details": f"Registered {len(skills)} skills"}
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def _sync_memory() -> dict[str, Any]:
    """Internal logic to optimize memory index."""
    # This usually just needs an optimization run
    from omni.foundation.services.vector import get_vector_store

    try:
        store = get_vector_store()
        # Create/Optimize index
        await store.create_index("memory")
        count = await store.count("memory")
        return {"status": "success", "details": f"Optimized index ({count} memories)"}
    except Exception as e:
        return {"status": "error", "details": str(e)}


@sync_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed logs"),
):
    """
    Synchronize system state and vector indexes.

    If no subcommand is provided, syncs EVERYTHING (Knowledge + Skills + Memory).
    """
    # If a subcommand is called (e.g. 'omni sync knowledge'), let it handle execution
    if ctx.invoked_subcommand is not None:
        return

    # Default action: Sync All
    import asyncio

    if not json_output:
        console.print("[dim]Running full system sync...[/dim]")

    stats = {}

    # 1. Skills (Cortex)
    stats["skills"] = _sync_skills()

    # 2. Knowledge (Librarian)
    stats["knowledge"] = _sync_knowledge()

    # 3. Memory (Hippocampus)
    stats["memory"] = asyncio.run(_sync_memory())

    _print_sync_report("Full System Sync", stats, json_output)


@sync_app.command("knowledge")
def sync_knowledge_cmd(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync documentation into the knowledge base.
    """
    stats = {"knowledge": _sync_knowledge(clear)}
    _print_sync_report("Knowledge Base", stats, json_output)


@sync_app.command("skills")
def sync_skills_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync skill registry (Cortex).
    """
    stats = {"skills": _sync_skills()}
    _print_sync_report("Skill Cortex", stats, json_output)


@sync_app.command("memory")
def sync_memory_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Optimize and sync memory index.
    """
    import asyncio

    stats = {"memory": asyncio.run(_sync_memory())}
    _print_sync_report("Memory Index", stats, json_output)


def register_sync_command(parent_app: typer.Typer) -> None:
    """Register the sync command with the parent app."""
    parent_app.add_typer(sync_app, name="sync")


__all__ = ["sync_app", "register_sync_command"]
