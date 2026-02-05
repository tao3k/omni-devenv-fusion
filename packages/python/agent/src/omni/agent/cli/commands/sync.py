"""sync.py - Unified Sync Protocol

The "One Ring" command to synchronize all vector indexes and system state.
Consolidates 'ingest knowledge', 'ingest skills', and memory indexing.

Usage:
    omni sync                # Sync EVERYTHING (Default)
    omni sync knowledge      # Sync documentation only
    omni sync skills         # Sync skill registry (Cortex) only
    omni sync router         # Sync router database (Hybrid Search) only
    omni sync memory         # Optimize memory index
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

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


async def _sync_symbols(clear: bool = False) -> dict[str, Any]:
    """Internal logic to sync code symbols using Zero-Token Indexing.

    Uses omni-tags (Rust) to extract symbols without LLM tokens.
    This replaces LLM-based summarization for code files.
    """
    try:
        from omni.core.knowledge.symbol_indexer import SymbolIndexer
        from omni.foundation.runtime.gitops import get_project_root

        # Get project root
        try:
            project_root = str(get_project_root())
        except Exception:
            project_root = "."

        indexer = SymbolIndexer(
            project_root=project_root,
            extensions=[".py", ".rs", ".js", ".ts", ".go", ".java"],
        )

        # Build the symbol index
        result = indexer.build(clean=clear)

        return {
            "status": "success",
            "details": f"Symbols: {result['unique_symbols']} in {result['indexed_files']} files",
        }
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def _sync_knowledge(clear: bool = False, include_code: bool = False) -> dict[str, Any]:
    """Internal logic to sync knowledge base (Librarian).

    By default, this only indexes documentation (markdown files).
    Code files are indexed via _sync_symbols (Zero-Token).

    Args:
        clear: Clear existing index first
        include_code: Also index code files (NOT recommended - use _sync_symbols instead)
    """
    from pathlib import Path

    from omni.core.knowledge.librarian import Librarian
    from omni.foundation.runtime.path_filter import should_skip_path, SKIP_DIRS

    try:
        librarian = Librarian()

        # Configure FileIngestor to use globs from knowledge_dirs config
        original_discover = librarian.ingestor.discover_files

        def knowledge_discover(project_root: Path, **kwargs):
            """Discover files using globs from knowledge_dirs config."""
            files = []
            for entry in librarian.config.knowledge_dirs:
                dir_path = project_root / entry.get("path", "")
                globs = entry.get("globs", [])

                # Support both single glob and list of globs
                if isinstance(globs, str):
                    globs = [globs]

                if not dir_path.exists():
                    continue

                for glob_pattern in globs:
                    for f in dir_path.glob(glob_pattern):
                        if f.is_file() and not should_skip_path(
                            f, skip_hidden=True, skip_dirs=SKIP_DIRS
                        ):
                            files.append(f)
            return sorted(set(files))

        librarian.ingestor.discover_files = knowledge_discover

        # Use ingest() which handles file discovery, chunking, and indexing
        result = librarian.ingest(clean=clear)

        # Restore original method
        librarian.ingestor.discover_files = original_discover

        return {
            "status": "success",
            "details": f"Indexed {result['files_processed']} docs, {result['chunks_indexed']} chunks (code: use 'omni sync symbols')",
        }
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def _sync_skills() -> dict[str, Any]:
    """Internal logic to sync skill registry (Cortex) and skills table."""
    from omni.foundation.bridge import get_vector_store
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        skills_path = str(SKILLS_DIR())
        if not Path(skills_path).exists():
            return {"status": "skipped", "details": "Skills dir not found"}

        # Index tools to skills table (for omni db search)
        store = get_vector_store()
        count = await store.index_skill_tools(skills_path, "skills")

        # Also update the skill discovery service
        from omni.core.skills.discovery import SkillDiscoveryService

        discovery = SkillDiscoveryService()
        skills = await discovery.discover_all()

        return {
            "status": "success",
            "details": f"Indexed {count} tools, registered {len(skills)} skills",
        }
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


async def _sync_router() -> dict[str, Any]:
    """Internal logic to sync router database from skills."""
    from omni.foundation.bridge import get_vector_store
    from omni.foundation.config.dirs import get_database_path
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        router_path = get_database_path("router")
        skills_path = str(SKILLS_DIR())

        router_store = get_vector_store(router_path, enable_keyword_index=True)
        count = await router_store.index_skill_tools(skills_path, "router")

        return {"status": "success", "details": f"Synced {count} tools to router"}
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

    async def run_sync_all():
        if not json_output:
            console.print("[dim]Running full system sync...[/dim]")

        stats = {}

        # 1. Symbols (Zero-Token Code Index) - NEW!
        stats["symbols"] = await _sync_symbols()

        # 2. Skills (Cortex)
        stats["skills"] = await _sync_skills()

        # 3. Router (Hybrid Search Index)
        stats["router"] = await _sync_router()

        # 4. Knowledge (Librarian - Docs only)
        stats["knowledge"] = await _sync_knowledge()

        # 5. Memory (Hippocampus)
        stats["memory"] = await _sync_memory()

        _print_sync_report("Full System Sync", stats, json_output)

    asyncio.run(run_sync_all())


def _run_async(coro):
    """Run async code, handling event loop properly."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Use nest_asyncio pattern for running in existing loop
            import nest_asyncio

            nest_asyncio.apply()
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    # No event loop exists
    return asyncio.run(coro)


@sync_app.command("knowledge")
def sync_knowledge_cmd(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync documentation into the knowledge base.
    """
    stats = {"knowledge": _run_async(_sync_knowledge(clear))}
    _print_sync_report("Knowledge Base", stats, json_output)


@sync_app.command("skills")
def sync_skills_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync skill registry (Cortex).
    """
    stats = {"skills": _run_async(_sync_skills())}
    _print_sync_report("Skill Cortex", stats, json_output)


@sync_app.command("memory")
def sync_memory_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Optimize and sync memory index.
    """
    stats = {"memory": _run_async(_sync_memory())}
    _print_sync_report("Memory Index", stats, json_output)


@sync_app.command("router")
def sync_router_cmd(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync router database from skills (Hybrid Search Index).
    """
    stats = {"router": _run_async(_sync_router())}
    _print_sync_report("Router Index", stats, json_output)


@sync_app.command("symbols")
def sync_symbols_cmd(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing symbol index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Sync code symbols using Zero-Token Indexing.

    This uses omni-tags (Rust AST extraction) to index functions,
    classes, and other symbols without using LLM tokens.

    Examples:
        omni sync symbols
        omni sync symbols --clear
    """
    import asyncio

    stats = {"symbols": asyncio.run(_sync_symbols(clear))}
    _print_sync_report("Symbol Index (Zero-Token)", stats, json_output)


def register_sync_command(parent_app: typer.Typer) -> None:
    """Register the sync command with the parent app."""
    parent_app.add_typer(sync_app, name="sync")


__all__ = ["sync_app", "register_sync_command"]
