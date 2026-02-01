"""reindex.py - Unified Reindex Command

Reindex all vector databases (skills, router, knowledge, memory).

Usage:
    omni reindex                 # Reindex skills to main DB
    omni reindex --all           # Reindex all databases
    omni reindex router          # Reindex router database
    omni reindex clear           # Clear all indexes

Databases:
    skills.lance   - Main skill tools database
    router.lance   - Router/hybrid search index
    knowledge.lance - Knowledge base
    memory.lance   - Memory index
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.fs import find_markdown_files

reindex_app = typer.Typer(
    name="reindex",
    help="Reindex vector databases (skills, router, knowledge, memory)",
    invoke_without_command=True,
)

# Console for printing tables
_console = Console()


# =============================================================================
# Database Path Management - Unified for all LanceDB databases
# =============================================================================


def get_database_paths() -> dict[str, str]:
    """Get all database paths used by Omni.

    Returns a dict with database name -> absolute path.
    All paths are relative to the vector DB base directory.

    Databases:
        skills.lance   - Main skill tools database
        router.lance   - Router/hybrid search index
        knowledge.lance - Knowledge base
        memory.lance   - Memory index
    """
    from omni.foundation.config.dirs import get_vector_db_path

    base = get_vector_db_path()
    return {
        "skills": str(base / "skills.lance"),
        "router": str(base / "router.lance"),
        "knowledge": str(base / "knowledge.lance"),
        "memory": str(base / "memory.lance"),
    }


def get_database_path(name: str) -> str:
    """Get the path for a specific database.

    Args:
        name: Database name (skills, router, knowledge, memory)

    Returns:
        Absolute path to the database directory
    """
    paths = get_database_paths()
    if name not in paths:
        raise ValueError(f"Unknown database: {name}. Valid: {list(paths.keys())}")
    return paths[name]


# =============================================================================
# Reindex Functions
# =============================================================================


def _reindex_skills(clear: bool = False) -> dict[str, Any]:
    """Reindex skills to the main skills.lance database."""
    from omni.foundation.bridge import RustVectorStore
    from omni.foundation.config.skills import SKILLS_DIR

    skills_path = str(SKILLS_DIR())
    db_path = get_database_path("skills")

    try:
        store = RustVectorStore(db_path, enable_keyword_index=True)

        if clear:
            print("Dropping existing skills table...")
            asyncio.run(store.drop_table("skills"))

        print("Indexing skills...")
        count = asyncio.run(store.index_skill_tools(skills_path))

        return {
            "status": "success",
            "database": "skills.lance",
            "tools_indexed": count,
        }
    except Exception as e:
        return {"status": "error", "database": "skills.lance", "error": str(e)}


def _sync_router_from_skills() -> dict[str, Any]:
    """Sync router.lance from skills.lance (or directly from filesystem)."""
    from omni.foundation.bridge import get_vector_store
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        router_path = get_database_path("router")
        skills_path = str(SKILLS_DIR())

        router_store = get_vector_store(router_path, enable_keyword_index=True)

        print("Syncing router database from skills...")
        count = asyncio.run(router_store.index_skill_tools(skills_path))

        return {
            "status": "success",
            "database": "router.lance",
            "tools_indexed": count,
        }
    except Exception as e:
        return {"status": "error", "database": "router.lance", "error": str(e)}


def _reindex_knowledge(clear: bool = False) -> dict[str, Any]:
    """Reindex knowledge base."""
    from omni.core.knowledge.librarian import Librarian

    try:
        librarian = Librarian(collection="knowledge")
        if not librarian.is_ready:
            return {"status": "error", "database": "knowledge.lance", "error": "Not ready"}

        if clear:
            librarian.clear()

        sources = ["docs", "assets/knowledge", "assets/how-to"]
        all_files = []
        for src in sources:
            all_files.extend(find_markdown_files(src))

        total_indexed = 0
        for file_path in all_files:
            if librarian.ingest_file(file_path, {"type": "documentation"}):
                total_indexed += 1

        committed = asyncio.run(librarian.commit())

        return {
            "status": "success",
            "database": "knowledge.lance",
            "docs_indexed": total_indexed,
            "entries_committed": committed,
        }
    except Exception as e:
        return {"status": "error", "database": "knowledge.lance", "error": str(e)}


def _reindex_memory(clear: bool = False) -> dict[str, Any]:
    """Reindex memory."""
    # Memory typically doesn't need reindexing - it's populated during conversation
    # This is a placeholder for future implementation
    return {
        "status": "info",
        "database": "memory.lance",
        "message": "Memory is populated during conversations, not reindexed",
    }


# =============================================================================
# CLI Commands
# =============================================================================


def _do_reindex_all(clear: bool, json_output: bool):
    """Internal function to perform full reindex."""
    results = {}

    # Reindex skills (main database)
    print("=" * 50)
    print("Reindexing skills...")
    results["skills"] = _reindex_skills(clear)

    # Sync router from skills
    print("=" * 50)
    print("Syncing router...")
    results["router"] = _sync_router_from_skills()

    # Reindex knowledge
    print("=" * 50)
    print("Reindexing knowledge...")
    results["knowledge"] = _reindex_knowledge(clear)

    # Memory doesn't need reindexing
    results["memory"] = _reindex_memory()

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        table = Table(title="Reindex All Results")
        table.add_column("Database", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Details", style="dim")

        for db, info in results.items():
            status = info.get("status", "unknown")
            if status == "success":
                if db == "skills":
                    details = f"{info.get('tools_indexed', 0)} tools"
                elif db == "router":
                    details = f"{info.get('tools_indexed', 0)} tools"
                elif db == "knowledge":
                    details = f"{info.get('docs_indexed', 0)} docs"
                else:
                    details = ""
            elif status == "info":
                details = info.get("message", "")
            else:
                details = info.get("error", "Unknown error")
            table.add_row(db, status, details)

        _console.print(
            Panel(
                table,
                title="✅ Reindex Complete",
                style="green",
            )
        )


@reindex_app.callback(invoke_without_command=True)
def reindex_main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear all databases first"),
):
    """Reindex all vector databases (skills, router, knowledge).

    If no subcommand is provided, reindexes ALL databases.

    Subcommands:
        skills    - Reindex skills only
        router    - Sync router from skills
        knowledge - Reindex knowledge base
        status    - Show database status
        clear     - Clear all databases
    """
    # If a subcommand is called (e.g. 'omni reindex skills'), let it handle execution
    if ctx.invoked_subcommand is not None:
        return

    # Default action: Reindex All
    _do_reindex_all(clear, json_output)


@reindex_app.command("skills")
def reindex_skills(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Reindex skill tools to skills.lance.

    This is the main database for skill tools. The router and other
    components sync from this database.

    Example:
        omni reindex skills         # Reindex skills
        omni reindex skills --clear # Clear and reindex from scratch
    """
    result = _reindex_skills(clear)

    if json_output:
        print(json.dumps(result, indent=2))
    elif result["status"] == "success":
        print(
            Panel(
                f"Indexed {result['tools_indexed']} tools to {result['database']}",
                title="✅ Success",
                style="green",
            )
        )
    else:
        print(
            Panel(
                f"Failed: {result.get('error', 'Unknown error')}",
                title="❌ Error",
                style="red",
            )
        )


@reindex_app.command("router")
def reindex_router(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Reindex/sync router database from skills.

    The router database is used for hybrid search (semantic + keyword).
    It should be kept in sync with skills.lance.

    Example:
        omni reindex router
    """
    result = _sync_router_from_skills()

    if json_output:
        print(json.dumps(result, indent=2))
    elif result["status"] == "success":
        print(
            Panel(
                f"Synced {result['tools_indexed']} tools to {result['database']}",
                title="✅ Success",
                style="green",
            )
        )
    else:
        print(
            Panel(
                f"Failed: {result.get('error', 'Unknown error')}",
                title="❌ Error",
                style="red",
            )
        )


@reindex_app.command("knowledge")
def reindex_knowledge(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear existing index first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Reindex documentation to knowledge.lance.

    Scans docs/, assets/knowledge/, and assets/how-to/ for markdown files.

    Example:
        omni reindex knowledge
        omni reindex knowledge --clear
    """
    result = _reindex_knowledge(clear)

    if json_output:
        print(json.dumps(result, indent=2))
    elif result["status"] == "success":
        print(
            Panel(
                f"Indexed {result['docs_indexed']} docs, committed {result['entries_committed']} entries",
                title="✅ Success",
                style="green",
            )
        )
    else:
        print(
            Panel(
                f"Failed: {result.get('error', 'Unknown error')}",
                title="❌ Error",
                style="red",
            )
        )


@reindex_app.command("clear")
def reindex_clear(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Clear all vector databases.

    WARNING: This removes all indexed data. Use with caution.

    Example:
        omni reindex clear
    """
    from omni.foundation.bridge import RustVectorStore

    cleared = []

    for table in ["skills", "router"]:
        try:
            store = RustVectorStore(enable_keyword_index=True)
            asyncio.run(store.drop_table(table))
            cleared.append(table)
        except Exception:
            pass

    # Clear knowledge
    try:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(collection="knowledge")
        if librarian.is_ready:
            librarian.clear()
            cleared.append("knowledge")
    except Exception:
        pass

    result = {"status": "success", "cleared": cleared}

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(
            Panel(
                f"Cleared databases: {', '.join(cleared) if cleared else 'none'}",
                title="🗑️ Cleared",
                style="yellow",
            )
        )


@reindex_app.command("status")
def reindex_status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Show status of all vector databases.

    Example:
        omni reindex status
    """
    from omni.foundation.bridge import RustVectorStore, get_vector_store
    from omni.core.knowledge.librarian import Librarian

    db_paths = get_database_paths()
    stats = {}

    # Check skills.lance
    try:
        store = RustVectorStore(db_paths["skills"], enable_keyword_index=True)
        tools = asyncio.run(store.list_all_tools())
        stats["skills.lance"] = {
            "status": "ready",
            "tools": len(tools),
            "path": db_paths["skills"],
        }
    except Exception as e:
        stats["skills.lance"] = {"status": "error", "error": str(e)}

    # Check router.lance
    try:
        router_store = get_vector_store(db_paths["router"], enable_keyword_index=True)
        router_tools = asyncio.run(router_store.list_all_tools())
        stats["router.lance"] = {
            "status": "ready",
            "tools": len(router_tools),
            "path": db_paths["router"],
        }
    except Exception as e:
        stats["router.lance"] = {"status": "error", "error": str(e)}

    # Check knowledge.lance
    try:
        librarian = Librarian(collection="knowledge")
        if librarian.is_ready:
            count = asyncio.run(librarian.count())
            stats["knowledge.lance"] = {
                "status": "ready",
                "entries": count,
                "path": db_paths["knowledge"],
            }
        else:
            stats["knowledge.lance"] = {"status": "not_ready"}
    except Exception as e:
        stats["knowledge.lance"] = {"status": "error", "error": str(e)}

    if json_output:
        print(json.dumps(stats, indent=2))
    else:
        table = Table(title="Database Status")
        table.add_column("Database", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Details", style="dim")

        for db, info in stats.items():
            status = info.get("status", "unknown")
            if status == "ready":
                details = f"Tools: {info.get('tools', info.get('entries', 0))}"
            elif status == "not_ready":
                details = "Not initialized"
            else:
                details = info.get("error", "Unknown error")
            table.add_row(db, status, details)

        _console.print(table)


@reindex_app.command("all")
def reindex_all(
    clear: bool = typer.Option(False, "--clear", "-c", help="Clear all databases first"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Reindex all vector databases.

    Performs:
    1. Reindex skills to skills.lance
    2. Sync to router.lance
    3. Reindex knowledge to knowledge.lance

    Example:
        omni reindex all          # Full reindex
        omni reindex all --clear  # Clear all first
    """
    _do_reindex_all(clear, json_output)


def register_reindex_command(parent_app: typer.Typer) -> None:
    """Register the reindex command with the parent app."""
    parent_app.add_typer(reindex_app, name="reindex")


__all__ = [
    "reindex_app",
    "register_reindex_command",
    "get_database_paths",
    "get_database_path",
]
