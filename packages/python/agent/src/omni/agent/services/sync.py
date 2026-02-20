"""Sync service - implementation for omni sync commands.

CLI should only parse args and call these functions; no business logic in CLI.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.foundation.runtime.gitops import get_project_root
from omni.foundation.utils.common import setup_import_paths

setup_import_paths()

from rich.console import Console

console = Console()


class SyncLogger:
    """Structured logger for sync operations with timestamps and phases."""

    def __init__(self, name: str = "sync"):
        self.name = name
        self.start_times: dict[str, float] = {}
        self.phase_stack: list[str] = []

    def _now(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def phase(self, name: str) -> None:
        self.phase_stack.append(name)
        self.start_times[name] = time.time()
        icon = ">>>" if len(self.phase_stack) == 1 else "..."
        console.print(f"\n{icon} [bold cyan]{name}[/bold cyan]")

    def end_phase(self, name: str, status: str = "done") -> float:
        elapsed = time.time() - self.start_times.get(name, 0)
        if name in self.phase_stack:
            self.phase_stack.pop()
        icon = "<<<"
        status_color = {"done": "green", "skip": "yellow", "error": "red"}.get(status, "white")
        console.print(f"{icon} [bold {status_color}]{name}[/bold {status_color}] - {elapsed:.2f}s")
        return elapsed

    def info(self, msg: str, phase: str = "main") -> None:
        console.print(f"[{self._now()}] [INFO] [{phase}] {msg}")

    def success(self, msg: str, phase: str = "main") -> None:
        console.print(f"  [green]✓[/green] {msg}")

    def error(self, msg: str, phase: str = "main", exc: Exception | None = None) -> None:
        console.print(f"  [red]✗[/red] {msg}")
        if exc:
            console.print(f"     [dim]Exception: {type(exc).__name__}: {exc}[/dim]")

    def warn(self, msg: str, phase: str = "main") -> None:
        console.print(f"  [yellow]![/yellow] {msg}")


sync_log = SyncLogger()


def _resolve_references_config_path() -> str:
    from omni.foundation.services.reference import get_references_config_path

    return str(get_references_config_path())


async def sync_symbols(clear: bool = False, verbose: bool | None = None) -> dict[str, Any]:
    """Sync code symbols (Zero-Token Indexing) and external crate deps."""
    from omni.core.knowledge.symbol_indexer import SymbolIndexer
    from omni.foundation.config.logging import is_verbose

    if verbose is None:
        verbose = is_verbose()
    sync_log.phase("Symbols Indexing")
    try:
        try:
            project_root = str(get_project_root())
        except Exception:
            project_root = "."
        sync_log.info(f"Project root: {project_root}")
        sync_log.info("Extensions: [py, rs, js, ts, go, java]")
        sync_log.info(f"Clear mode: {clear}")
        if verbose:
            sync_log.info("Verbose mode: enabled")
        config_path = _resolve_references_config_path()
        ext_crates = 0
        ext_symbols = 0
        if os.path.exists(config_path):
            sync_log.info("Syncing external dependencies...")
            try:
                from omni_core_rs import PyDependencyIndexer

                indexer = PyDependencyIndexer(project_root, config_path)
                result_json = indexer.build(clean=clear, verbose=verbose)
                result = json.loads(result_json)
                ext_crates = result.get("crates_indexed", 0)
                ext_symbols = result.get("total_symbols", 0)
                errors = result.get("errors", 0)
                if errors > 0:
                    sync_log.warn(f"External deps errors: {errors}")
                sync_log.success(f"External: {ext_crates} crates, {ext_symbols} symbols")
            except Exception as e:
                sync_log.warn(f"External deps skipped: {e}")
        else:
            sync_log.info("External deps: config not found")
        indexer = SymbolIndexer(
            project_root=project_root,
            extensions=[".py", ".rs", ".js", ".ts", ".go", ".java"],
        )
        sync_log.info("Extracting project symbols...")
        result = indexer.build(clean=clear)
        sync_log.success(
            f"Project: {result['unique_symbols']} symbols in {result['indexed_files']} files"
        )
        elapsed = sync_log.end_phase("Symbols Indexing", "done")
        return {
            "status": "success",
            "details": f"Project: {result['unique_symbols']} | External: {ext_symbols}",
            "project_symbols": result["unique_symbols"],
            "project_files": result["indexed_files"],
            "external_crates": ext_crates,
            "external_symbols": ext_symbols,
            "elapsed": elapsed,
        }
    except Exception as e:
        sync_log.error(f"Symbol indexing failed: {e}", exc=e)
        sync_log.end_phase("Symbols Indexing", "error")
        return {"status": "error", "details": str(e)}


async def sync_knowledge(clear: bool = False, verbose: bool = False) -> dict[str, Any]:
    """Sync knowledge base (Librarian docs)."""
    from omni.core.knowledge.librarian import Librarian
    from omni.foundation.runtime.path_filter import should_skip_path, SKIP_DIRS
    from omni.foundation.services.embedding import get_embedding_service

    try:
        # Pre-flight: ensure embedding service is initialized and HTTP client reachable
        embed_svc = get_embedding_service()
        embed_svc.initialize()
        if getattr(embed_svc, "_client_mode", False) and getattr(embed_svc, "_client_url", None):
            if not embed_svc._check_http_server_healthy(embed_svc._client_url, timeout=2.0):
                sync_log.warn(
                    "Embedding HTTP server unreachable before knowledge sync. "
                    "Will retry on first embed; if it times out, local model will load. "
                    "Start MCP (omni mcp) for faster sync.",
                )
        librarian = Librarian()
        original_discover = librarian.ingestor.discover_files

        def knowledge_discover(project_root: Path, **kwargs):
            files = []
            for entry in librarian.config.knowledge_dirs:
                dir_path = project_root / entry.get("path", "")
                globs = entry.get("globs", [])
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
        result = librarian.ingest(clean=clear, verbose=verbose)
        librarian.ingestor.discover_files = original_discover
        return {
            "status": "success",
            "details": f"Indexed {result['files_processed']} docs, {result['chunks_indexed']} chunks (code: use 'omni sync symbols')",
        }
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def _embed_skill_vectors(store: Any, skills_db_path: str) -> int:
    """Generate real embeddings for skills table. Async version for sync flow."""
    import asyncio
    import json as _json
    from concurrent.futures import ThreadPoolExecutor

    from omni.foundation.services.embedding import get_embedding_service

    try:
        entries = await store.list_all("skills")
        if not entries:
            return 0
        ids, contents, metadatas = [], [], []
        for entry in entries:
            data = _json.loads(entry) if isinstance(entry, str) else entry
            entry_id = data.get("id", "")
            content = data.get("content", "")
            if not entry_id or not content:
                continue
            ids.append(entry_id)
            contents.append(content)
            meta = {k: v for k, v in data.items() if k not in ("id", "content")}
            metadatas.append(_json.dumps(meta))
        if not ids:
            return 0
        embed_service = get_embedding_service()
        if getattr(embed_service, "_client_mode", False):
            sync_log.info(
                "Skipping embedding during sync (client mode). "
                "Embedding will happen lazily when MCP server starts."
            )
            return 0
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="sync-embed") as executor:
            embeddings = await loop.run_in_executor(
                executor, lambda: list(embed_service.embed_batch(contents))
            )
        await store.replace_documents(
            table_name="skills",
            ids=ids,
            vectors=embeddings,
            contents=contents,
            metadatas=metadatas,
        )
        sync_log.info(f"Embedded {len(ids)} tool vectors into skills table")
        return len(ids)
    except Exception as e:
        sync_log.warn(f"Embedding step skipped (non-fatal): {e}")
        return 0


async def sync_skills() -> dict[str, Any]:
    """Sync skill registry (Cortex) and skills table."""
    from omni.foundation.bridge import get_vector_store
    from omni.foundation.config.database import get_database_path
    from omni.foundation.config.skills import SKILLS_DIR

    try:
        skills_path = str(SKILLS_DIR())
        if not Path(skills_path).exists():
            return {"status": "skipped", "details": "Skills dir not found"}
        skills_db_path = get_database_path("skills")
        store = get_vector_store(skills_db_path)
        skills_count, _ = await store.index_skill_tools_dual(skills_path, "skills", "skills")
        embedded_count = await _embed_skill_vectors(store, skills_db_path)
        try:
            from omni.agent.services.reindex import _build_relationship_graph_after_skills_reindex

            _build_relationship_graph_after_skills_reindex(skills_db_path)
        except Exception as e:
            sync_log.warn(f"Relationship graph build skipped: {e}")
        from omni.foundation.services.index_dimension import ensure_embedding_signature_written

        ensure_embedding_signature_written()
        from omni.core.skills.discovery import SkillDiscoveryService

        discovery = SkillDiscoveryService()
        skills = await discovery.discover_all()
        embed_info = f", embedded {embedded_count}" if embedded_count else ""
        return {
            "status": "success",
            "details": f"Indexed {skills_count} tools{embed_info}, registered {len(skills)} skills",
        }
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def sync_router_init() -> dict[str, Any]:
    """Initialize router DB (scores table)."""
    from omni.foundation.config.database import get_database_path
    from omni.foundation.services.embedding import get_embedding_service
    from omni.foundation.services.router_scores import init_router_db

    try:
        router_path = get_database_path("router")
        embed_service = get_embedding_service()
        dimension = embed_service.dimension
        ok = await init_router_db(router_path, dimension=dimension)
        if ok:
            return {"status": "success", "details": "Router DB (scores) initialized"}
        return {"status": "skipped", "details": "Router DB init skipped"}
    except Exception as e:
        return {"status": "skipped", "details": f"Router init skipped: {e}"}


async def sync_memory() -> dict[str, Any]:
    """Optimize memory index."""
    from omni.foundation.services.vector import get_vector_store

    try:
        store = get_vector_store()
        await store.create_index("memory")
        count = await store.count("memory")
        return {"status": "success", "details": f"Optimized index ({count} memories)"}
    except Exception as e:
        return {"status": "error", "details": str(e)}


async def sync_all(verbose: bool = False) -> tuple[dict[str, Any], float]:
    """Run full sync (dimension check, symbols, skills, router, knowledge, memory).
    Returns (stats dict, total_elapsed seconds).
    """
    start_time = datetime.now()
    stats: dict[str, Any] = {}
    from omni.foundation.services.index_dimension import (
        check_all_vector_stores_dimension,
        ensure_embedding_signature_written,
        repair_vector_store_dimension,
    )

    sync_log.phase("FULL SYSTEM SYNC")
    dim_report = check_all_vector_stores_dimension()
    if not dim_report.is_consistent:
        sync_log.warn("Vector store dimension issues detected:")
        for issue in dim_report.issues:
            sync_log.warn(f"  - {issue}")
        for store_name, store_info in dim_report.stores.items():
            if store_info.get("status") != "mismatch":
                continue
            expected = store_info.get("expected_dimension")
            if not isinstance(expected, int):
                continue
            sync_log.info(f"Repairing {store_name} (target dimension {expected})...")
            result = await repair_vector_store_dimension(store_name, expected)
            if result.get("status") == "success":
                sync_log.success(f"{store_name}: {result.get('details', 'repaired')}")
            else:
                sync_log.warn(f"{store_name}: {result.get('details', 'repair skipped')}")
        dim_report = check_all_vector_stores_dimension()
        if not dim_report.is_consistent:
            sync_log.warn(
                "Some dimension issues may remain; sync will overwrite with current dimension."
            )
    ensure_embedding_signature_written()
    sync_log.info("Starting symbols sync...")
    stats["symbols"] = await sync_symbols(verbose=verbose)
    sync_log.info("Starting skills sync...")
    stats["skills"] = await sync_skills()
    sync_log.info("Initializing router DB (scores)...")
    stats["router"] = await sync_router_init()
    sync_log.info("Starting knowledge sync...")
    stats["knowledge"] = await sync_knowledge(verbose=verbose)
    sync_log.info("Starting memory sync...")
    stats["memory"] = await sync_memory()
    total_elapsed = (datetime.now() - start_time).total_seconds()
    final_report = check_all_vector_stores_dimension()
    if final_report.is_consistent:
        sync_log.info("✓ All vector stores dimension consistent")
    else:
        sync_log.warn("⚠ Some vector stores have dimension issues:")
        for issue in final_report.issues:
            sync_log.warn(f"  - {issue}")
    return stats, total_elapsed
