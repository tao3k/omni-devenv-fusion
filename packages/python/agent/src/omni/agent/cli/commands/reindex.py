"""reindex.py - Unified Reindex Command

Reindex vector databases (skills, knowledge, memory).

Usage:
    omni reindex                 # Reindex skills to main DB
    omni reindex --all           # Reindex all databases
    omni reindex clear           # Clear all indexes

Databases:
    skills.lance   - Full skill/tool data (routing + discovery)
    router.lance  - Routing-only scores (no duplication of skills content)
    knowledge.lance - Knowledge base
    memory.lance   - Memory index

Unified with sync:
    Same paths (get_database_path) and same indexing API for skills so that
    "omni sync" and "omni reindex skills" write to the same skills.lance
    and keyword index; route test reads from that path.
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
    help="Reindex vector databases (skills, knowledge, memory)",
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
    from omni.foundation.services.index_dimension import get_effective_embedding_dimension

    return {
        "embedding_model": str(get_setting("embedding.model")),
        "embedding_dimension": get_effective_embedding_dimension(),
        "embedding_provider": str(get_setting("embedding.provider")),
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


def _validate_skills_schema() -> dict[str, Any]:
    """Run contract validation on the skills table (no legacy 'keywords' in metadata)."""
    from omni.foundation.bridge import RustVectorStore

    result: dict[str, Any] = {}
    try:
        db_path = get_database_path("skills")
        store = RustVectorStore(db_path, enable_keyword_index=True)
        entries = run_async_blocking(store.list_all("skills"))
        result["skills"] = validate_vector_table_contract(entries)
    except Exception as e:
        result["skills"] = {
            "total": 0,
            "legacy_keywords_count": 0,
            "sample_ids": [],
            "error": str(e),
        }
    return result


def _build_relationship_graph_after_skills_reindex(db_path: str) -> None:
    """Build and persist skill relationship graph from the skills table.

    Uses same-skill and shared-reference edges when metadata is present
    (e.g. after Rust reindex). Idempotent; no-op if path is memory or graph empty.

    Also registers skill entities in the KnowledgeGraph (Bridge 4: Core 2 → Core 1)
    so that ZK entity graph enrichment has data to work with.
    """
    from omni.core.router.skill_relationships import (
        build_graph_from_entries,
        get_relationship_graph_path,
        save_relationship_graph,
    )
    from omni.foundation.bridge import RustVectorStore

    graph_path = get_relationship_graph_path(db_path)
    if graph_path is None:
        return
    try:
        store = RustVectorStore(db_path, enable_keyword_index=True)
        entries = run_async_blocking(store.list_all("skills"))
        graph = build_graph_from_entries(entries)
        if graph:
            save_relationship_graph(graph, graph_path)

        # Bridge 4: Register skill entities in KnowledgeGraph (Core 2 → Core 1)
        try:
            from omni.rag.dual_core import register_skill_entities

            docs = [{"id": e.get("id"), "content": "", "metadata": e} for e in entries]
            kg_result = register_skill_entities(docs)
            if kg_result.get("status") == "success":
                _console.print(
                    f"[dim]KnowledgeGraph: +{kg_result['entities_added']} entities, "
                    f"+{kg_result['relations_added']} relations[/dim]"
                )
        except Exception as e:
            _console.print(f"[dim]KnowledgeGraph registration skipped: {e}[/dim]")

    except Exception as e:
        # Non-fatal; reindex already succeeded
        _console.print(f"[dim]Relationship graph build skipped: {e}[/dim]")


def _reindex_skills_only(clear: bool = False) -> dict[str, Any]:
    """Reindex the single skills table (routing and discovery use this table).

    Pipeline mirrors _sync_skills:
    1. Rust scan → metadata + keyword index (zero vectors)
    2. Embedding → generate real vectors and merge-insert
    3. Relationship graph → build skill→tool and tool→reference edges
    """
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

            # Step 1: Rust scan → metadata + keyword index
            print("Indexing skills table (routing + discovery)...")
            skills_count, _ = run_async_blocking(
                store.index_skill_tools_dual(skills_path, "skills", "skills")
            )

            # Step 2: Generate real embeddings
            print("Generating embeddings...")
            try:
                from omni.agent.cli.commands.sync import _embed_skill_vectors

                embedded = run_async_blocking(_embed_skill_vectors(store, db_path))
                print(f"Embedded {embedded} tool vectors")
            except Exception as e:
                print(f"Embedding step skipped: {e}")

            out = {
                "status": "success",
                "database": "skills.lance",
                "skills_tools_indexed": skills_count,
                "tools_indexed": skills_count,
            }
            validation = _validate_skills_schema()
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
            # Step 3: Build relationship graph from index
            _build_relationship_graph_after_skills_reindex(db_path)
            return out
    except Exception as e:
        return {"status": "error", "error": str(e)}


def ensure_embedding_index_compatibility(auto_fix: bool = True) -> dict[str, Any]:
    """Ensure vector indexes match current embedding settings.

    When embedding model or dimension changes, skills index must be rebuilt.
    """
    enabled = bool(get_setting("embedding.auto_reindex_on_change"))
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
    skills_result = _reindex_skills_only(clear=True)
    if skills_result.get("status") != "success":
        return {
            "status": "error",
            "error": f"skills reindex failed: {skills_result.get('error', 'unknown')}",
            "saved": saved,
            "current": current,
        }

    _write_embedding_signature(current)
    return {
        "status": "reindexed",
        "changed": True,
        "saved": saved,
        "current": current,
        "skills_tools_indexed": int(skills_result.get("skills_tools_indexed", 0)),
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


def _reindex_symbols(clear: bool = False) -> dict[str, Any]:
    """Reindex code symbols (Zero-Token Indexing). Aligns with sync symbols component."""
    from omni.agent.cli.commands.sync import _sync_symbols

    out = run_async_blocking(_sync_symbols(clear=clear))
    # Normalize to reindex shape
    if out.get("status") == "success":
        return {
            "status": "success",
            "details": out.get("details", ""),
            "project_symbols": out.get("project_symbols", 0),
            "external_symbols": out.get("external_symbols", 0),
        }
    return {
        "status": out.get("status", "error"),
        "details": out.get("details", ""),
        "error": out.get("details", ""),
    }


def _reindex_router_init() -> dict[str, Any]:
    """Initialize router DB (scores table). Aligns with sync router component."""
    from omni.agent.cli.commands.sync import _sync_router_init

    return run_async_blocking(_sync_router_init())


def _do_reindex_all(clear: bool, json_output: bool):
    """Internal function to perform full reindex. Five components aligned with sync."""
    results = {}

    # 1. Symbols (Zero-Token Code Index)
    print("=" * 50)
    print("Reindexing symbols...")
    results["symbols"] = _reindex_symbols(clear)

    # 2. Skills (routing + discovery)
    print("=" * 50)
    print("Reindexing skills...")
    skills_result = _reindex_skills_only(clear)
    if skills_result.get("status") == "success":
        results["skills"] = {
            "status": "success",
            "database": "skills.lance",
            "tools_indexed": int(skills_result.get("skills_tools_indexed", 0)),
        }
    else:
        err = skills_result.get("error", "unknown")
        results["skills"] = {"status": "error", "database": "skills.lance", "error": str(err)}

    if results["skills"].get("status") == "success":
        _write_embedding_signature()

    # 3. Router DB (scores table init only)
    print("=" * 50)
    print("Initializing router DB (scores)...")
    router_out = _reindex_router_init()
    results["router"] = {
        "status": router_out.get("status", "skipped"),
        "details": router_out.get("details", "Router DB (scores) initialized"),
    }

    # 4. Knowledge
    print("=" * 50)
    print("Reindexing knowledge...")
    results["knowledge"] = _reindex_knowledge(clear)

    # 5. Memory (info only)
    results["memory"] = _reindex_memory()

    if json_output:
        print(json.dumps(results, indent=2))
    else:
        table = Table(title="Reindex All Results")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Details", style="dim")

        component_order = ("symbols", "skills", "router", "knowledge", "memory")
        for db in component_order:
            info = results.get(db, {})
            status = info.get("status", "unknown")
            if status == "success":
                if db == "skills":
                    details = f"{info.get('tools_indexed', 0)} tools"
                elif db == "knowledge":
                    details = f"{info.get('docs_indexed', 0)} docs"
                elif db == "symbols":
                    details = info.get("details", "")
                elif db == "router":
                    details = info.get("details", "Router DB (scores) initialized")
                else:
                    details = info.get("details", "")
            elif status == "info":
                details = info.get("message", info.get("details", ""))
            else:
                details = info.get("error", info.get("details", "Unknown error"))
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
    """Reindex all vector databases (skills, knowledge).

    If no subcommand is provided, reindexes ALL databases.
    Routing and tool discovery use the single skills table.

    Subcommands:
        skills    - Reindex skills (routing + discovery)
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

    Single database for skill tools (routing + discovery).

    Example:
        omni reindex skills         # Reindex skills
        omni reindex skills --clear # Clear and reindex from scratch
    """
    result = _reindex_skills_only(clear)

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

    for table in ["skills"]:
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
    from omni.foundation.bridge import RustVectorStore
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
    1. Reindex skills (routing + discovery) to skills.lance
    2. Reindex knowledge to knowledge.lance

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
