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

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from omni.foundation.utils.fs import find_markdown_files
from omni.foundation.utils.asyncio import run_async_blocking
from omni.foundation.config import get_database_path, get_database_paths
from omni.foundation.config.settings import get_setting
from omni.foundation.config.dirs import get_vector_db_path
from omni.foundation.services.vector_schema import validate_vector_table_contract

reindex_app = typer.Typer(
    name="reindex",
    help="Reindex vector databases (skills, router, knowledge, memory)",
    invoke_without_command=True,
)

# Console for printing tables
_console = Console()


@contextmanager
def _reindex_lock():
    """Process-level lock to avoid concurrent reindex races across xdist workers."""
    import fcntl

    from omni.foundation.config.dirs import get_vector_db_path

    lock_file = Path(get_vector_db_path()) / ".reindex.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _embedding_signature_path() -> Path:
    """Path to persisted embedding/index compatibility signature."""
    return Path(get_vector_db_path()) / ".embedding_signature.json"


def _current_embedding_signature() -> dict[str, Any]:
    """Current embedding signature derived from settings."""
    return {
        "embedding_model": str(get_setting("embedding.model", "")),
        "embedding_dimension": int(get_setting("embedding.dimension", 1024)),
        "embedding_provider": str(get_setting("embedding.provider", "")),
    }


def _read_embedding_signature() -> dict[str, Any] | None:
    path = _embedding_signature_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _write_embedding_signature(signature: dict[str, Any] | None = None) -> None:
    path = _embedding_signature_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = signature or _current_embedding_signature()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


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
        with _reindex_lock():
            store = RustVectorStore(db_path, enable_keyword_index=True)

            if clear:
                print("Dropping existing skills table...")
                run_async_blocking(store.drop_table("skills"))

            print("Indexing skills...")
            count = run_async_blocking(store.index_skill_tools(skills_path))

            out = {
                "status": "success",
                "database": "skills.lance",
                "tools_indexed": count,
            }
            entries = run_async_blocking(store.list_all("skills"))
            val = validate_vector_table_contract(entries)
            out["schema_validation"] = {"skills": val}
            if val.get("legacy_keywords_count", 0) > 0:
                out["schema_validation_warning"] = (
                    "Some rows still have legacy 'keywords' in metadata; use routing_keywords only."
                )
            return out
    except Exception as e:
        return {"status": "error", "database": "skills.lance", "error": str(e)}


def _validate_skills_router_schema() -> dict[str, Any]:
    """Run contract validation on skills and router tables (no legacy 'keywords' in metadata)."""
    from omni.foundation.bridge import RustVectorStore

    result: dict[str, Any] = {}
    for db_name, table_name in [("skills", "skills"), ("router", "router")]:
        try:
            db_path = get_database_path(db_name)
            store = RustVectorStore(db_path, enable_keyword_index=True)
            entries = run_async_blocking(store.list_all(table_name))
            result[table_name] = validate_vector_table_contract(entries)
        except Exception as e:
            result[table_name] = {
                "total": 0,
                "legacy_keywords_count": 0,
                "sample_ids": [],
                "error": str(e),
            }
    return result


def _reindex_skills_and_router(clear: bool = False) -> dict[str, Any]:
    """Reindex skills/router in one Rust scan for snapshot consistency."""
    from omni.foundation.bridge import RustVectorStore
    from omni.foundation.config.skills import SKILLS_DIR

    skills_path = str(SKILLS_DIR())
    db_path = get_database_path("skills")

    try:
        with _reindex_lock():
            store = RustVectorStore(db_path, enable_keyword_index=True)

            if clear:
                print("Dropping existing skills/router tables...")
                run_async_blocking(store.drop_table("skills"))
                run_async_blocking(store.drop_table("router"))

            print("Indexing skills/router from single snapshot...")
            skills_count, router_count = run_async_blocking(
                store.index_skill_tools_dual(skills_path, "skills", "router")
            )

            out = {
                "status": "success",
                "skills_tools_indexed": skills_count,
                "router_tools_indexed": router_count,
            }
            validation = _validate_skills_router_schema()
            out["schema_validation"] = validation
            legacy_total = sum(
                v.get("legacy_keywords_count", 0)
                for v in validation.values()
                if isinstance(v, dict)
            )
            if legacy_total > 0:
                out["schema_validation_warning"] = (
                    "Some rows still have legacy 'keywords' in metadata; use routing_keywords only."
                )
            return out
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _sync_router_lance_from_skills() -> dict[str, Any]:
    """Sync the separate router.lance directory from current skills (no refresh).

    Call after _reindex_skills_and_router so that router.lance stays in sync
    and omni db validate-schema passes for both skills and router.
    """
    from omni.foundation.bridge import get_vector_store
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        router_path = get_database_path("router")
        skills_path = str(SKILLS_DIR())
        with _reindex_lock():
            router_store = get_vector_store(router_path, enable_keyword_index=True)
            count = run_async_blocking(router_store.index_skill_tools(skills_path, "router"))
        entries = run_async_blocking(router_store.list_all("router"))
        val = validate_vector_table_contract(entries)
        out = {
            "status": "success",
            "database": "router.lance",
            "tools_indexed": count,
            "schema_validation": {"router": val},
        }
        if val.get("legacy_keywords_count", 0) > 0:
            out["schema_validation_warning"] = (
                "Some rows still have legacy 'keywords' in metadata; use routing_keywords only."
            )
        return out
    except Exception as e:
        return {"status": "error", "database": "router.lance", "error": str(e)}


def _sync_router_from_skills(refresh_skills: bool = True) -> dict[str, Any]:
    """Sync router.lance from the latest skills snapshot.

    This function always refreshes ``skills.lance`` first, then indexes
    ``router.lance`` from the same skills directory snapshot to keep counts
    and metadata in lockstep.
    """
    from omni.foundation.bridge import get_vector_store
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        router_path = get_database_path("router")
        skills_path = str(SKILLS_DIR())

        # Ensure skills database is refreshed first so router sync uses
        # the same source snapshot and does not drift from skills.lance.
        if refresh_skills:
            atomic = _reindex_skills_and_router(clear=False)
            if atomic.get("status") != "success":
                return {
                    "status": "error",
                    "database": "router.lance",
                    "error": f"skills/router atomic reindex failed: {atomic.get('error', 'unknown')}",
                }
            out = {
                "status": "success",
                "database": "router.lance",
                "tools_indexed": int(atomic.get("router_tools_indexed", 0)),
            }
            if "schema_validation" in atomic:
                out["schema_validation"] = atomic["schema_validation"]
            if atomic.get("schema_validation_warning"):
                out["schema_validation_warning"] = atomic["schema_validation_warning"]
            return out

        with _reindex_lock():
            router_store = get_vector_store(router_path, enable_keyword_index=True)

            print("Syncing router database from skills...")
            count = run_async_blocking(router_store.index_skill_tools(skills_path, "router"))

        entries = run_async_blocking(router_store.list_all("router"))
        val = validate_vector_table_contract(entries)
        out = {
            "status": "success",
            "database": "router.lance",
            "tools_indexed": count,
            "schema_validation": {"router": val},
        }
        if val.get("legacy_keywords_count", 0) > 0:
            out["schema_validation_warning"] = (
                "Some rows still have legacy 'keywords' in metadata; use routing_keywords only."
            )
        return out
    except Exception as e:
        return {"status": "error", "database": "router.lance", "error": str(e)}


def ensure_embedding_index_compatibility(auto_fix: bool = True) -> dict[str, Any]:
    """Ensure vector indexes match current embedding settings.

    When embedding model or dimension changes, skills/router indexes must be rebuilt.
    """
    enabled = bool(get_setting("embedding.auto_reindex_on_change", True))
    if not enabled:
        return {"status": "disabled"}

    current = _current_embedding_signature()
    saved = _read_embedding_signature()

    if saved == current:
        return {"status": "ok", "changed": False}

    if saved is None:
        _write_embedding_signature(current)
        return {"status": "initialized", "changed": False}

    if not auto_fix:
        return {"status": "mismatch", "changed": True, "saved": saved, "current": current}

    # Rebuild from scratch on signature drift.
    atomic_result = _reindex_skills_and_router(clear=True)
    if atomic_result.get("status") != "success":
        return {
            "status": "error",
            "error": f"skills/router reindex failed: {atomic_result.get('error', 'unknown')}",
            "saved": saved,
            "current": current,
        }

    _write_embedding_signature(current)
    return {
        "status": "reindexed",
        "changed": True,
        "saved": saved,
        "current": current,
        "skills_tools_indexed": int(atomic_result.get("skills_tools_indexed", 0)),
        "router_tools_indexed": int(atomic_result.get("router_tools_indexed", 0)),
    }


def _reindex_knowledge(clear: bool = False) -> dict[str, Any]:
    """Reindex knowledge base."""
    from omni.core.knowledge.librarian import Librarian

    try:
        librarian = Librarian(table_name="knowledge")

        if clear:
            librarian.ingest(clean=True)
            # Return empty counts for clean ingest
            return {
                "status": "success",
                "database": "knowledge.lance",
                "docs_indexed": 0,
                "chunks_indexed": 0,
            }

        result = librarian.ingest()
        # Return the processed counts from incremental ingestion
        return {
            "status": "success",
            "database": "knowledge.lance",
            "docs_indexed": result.get("files_processed", 0),
            "chunks_indexed": result.get("chunks_indexed", 0),
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

    # Reindex skills (main database) and sync separate router.lance
    print("=" * 50)
    print("Reindexing skills/router...")
    atomic_result = _reindex_skills_and_router(clear)
    if atomic_result.get("status") == "success":
        results["skills"] = {
            "status": "success",
            "database": "skills.lance",
            "tools_indexed": int(atomic_result.get("skills_tools_indexed", 0)),
        }
        # Sync the separate router.lance directory so omni db validate-schema passes for both
        router_sync = _sync_router_lance_from_skills()
        if router_sync.get("status") == "success":
            results["router"] = {
                "status": "success",
                "database": "router.lance",
                "tools_indexed": int(router_sync.get("tools_indexed", 0)),
            }
        else:
            results["router"] = {
                "status": "error",
                "database": "router.lance",
                "error": router_sync.get("error", "sync failed"),
            }
    else:
        err = atomic_result.get("error", "unknown")
        results["skills"] = {"status": "error", "database": "skills.lance", "error": str(err)}
        results["router"] = {"status": "error", "database": "router.lance", "error": str(err)}

    if (
        results["skills"].get("status") == "success"
        and results["router"].get("status") == "success"
    ):
        _write_embedding_signature()

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
        _console.print(
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
    only_router: bool = typer.Option(
        False,
        "--only-router",
        help="Rebuild router table only (skip atomic skills+router snapshot reindex).",
    ),
):
    """
    Reindex/sync router database from skills.

    The router database is used for hybrid search (semantic + keyword).
    It should be kept in sync with skills.lance.

    Example:
        omni reindex router
    """
    # Default path is atomic dual reindex to keep router/skills perfectly aligned.
    # Only use router-only mode for explicit operator workflows.
    result = _sync_router_from_skills(refresh_skills=not only_router)

    if json_output:
        print(json.dumps(result, indent=2))
    elif result["status"] == "success":
        _console.print(
            Panel(
                f"Synced {result['tools_indexed']} tools to {result['database']}",
                title="✅ Success",
                style="green",
            )
        )
    else:
        _console.print(
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
        _console.print(
            Panel(
                f"Indexed {result['docs_indexed']} docs, {result.get('chunks_indexed', 0)} chunks",
                title="✅ Success",
                style="green",
            )
        )
    else:
        _console.print(
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
            run_async_blocking(store.drop_table(table))
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
        tools = store.list_all_tools()
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
        router_tools = router_store.list_all_tools()
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
            count = run_async_blocking(librarian.count())
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
