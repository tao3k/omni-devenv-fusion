"""Reindex service - implementation for omni reindex commands.

CLI should only parse args and call these functions; no business logic in CLI.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from omni.foundation.utils.asyncio import run_async_blocking
from omni.foundation.config import get_database_path, get_database_paths
from omni.foundation.config.settings import get_setting
from omni.foundation.config.dirs import get_vector_db_path
from omni.foundation.services.vector_schema import validate_vector_table_contract


@contextmanager
def _reindex_lock():
    """Process-level lock to avoid concurrent reindex races."""
    import fcntl

    lock_file = Path(get_vector_db_path()) / ".reindex.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("w") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _embedding_signature_path() -> Path:
    return Path(get_vector_db_path()) / ".embedding_signature.json"


def _current_embedding_signature() -> dict[str, Any]:
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


def _validate_skills_schema() -> dict[str, Any]:
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
    """Build and persist skill relationship graph from the skills table."""
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
        try:
            from omni.rag.dual_core import register_skill_entities

            docs = [{"id": e.get("id"), "content": "", "metadata": e} for e in entries]
            register_skill_entities(docs)
        except Exception:
            pass
    except Exception:
        pass


def _embed_skill_vectors(store: Any, _skills_db_path: str, skills_path: str | None = None) -> int:
    """Generate real embeddings for skills table. Used by reindex (and sync imports from here).

    Robustness: If replace_documents fails (e.g. add_documents error after drop),
    re-runs index_skill_tools_dual to restore tools from filesystem (without embeddings).
    """
    import json as _json

    from omni.foundation.config.logging import get_logger
    from omni.foundation.config.skills import SKILLS_DIR
    from omni.foundation.services.embedding import get_embedding_service

    log = get_logger(__name__)
    try:
        entries = run_async_blocking(store.list_all("skills"))
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
            return 0
        embeddings = list(embed_service.embed_batch(contents))
        try:
            run_async_blocking(
                store.replace_documents(
                    table_name="skills",
                    ids=ids,
                    vectors=embeddings,
                    contents=contents,
                    metadatas=metadatas,
                )
            )
        except Exception as replace_err:
            log.warning(
                "replace_documents_failed_restoring",
                error=str(replace_err),
            )
            path = skills_path or str(SKILLS_DIR())
            run_async_blocking(store.index_skill_tools_dual(path, "skills", "skills"))
            log.info("Restored skills table from filesystem (without embeddings)")
            return 0
        return len(ids)
    except Exception as e:
        log.warning("embed_skill_vectors_skipped", error=str(e))
        return 0


def reindex_skills_only(clear: bool = False) -> dict[str, Any]:
    """Reindex the single skills table (routing + discovery)."""
    from omni.foundation.bridge import RustVectorStore
    from omni.foundation.config.skills import SKILLS_DIR

    skills_path = str(SKILLS_DIR())
    db_path = get_database_path("skills")
    try:
        with _reindex_lock():
            store = RustVectorStore(db_path, enable_keyword_index=True)
            # Do NOT drop here: Rust index_skill_tools_dual drops when it has tools.
            # Dropping first would leave empty table if index fails (e.g. scan error).
            skills_count, _ = run_async_blocking(
                store.index_skill_tools_dual(skills_path, "skills", "skills")
            )
            embedded = _embed_skill_vectors(store, db_path, skills_path)
            if embedded:
                pass  # optional log
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
            _build_relationship_graph_after_skills_reindex(db_path)
            return out
    except Exception as e:
        return {"status": "error", "error": str(e)}


def ensure_embedding_index_compatibility(auto_fix: bool = True) -> dict[str, Any]:
    """Ensure vector indexes match current embedding settings."""
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
    skills_result = reindex_skills_only(clear=True)
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


def reindex_knowledge(clear: bool = False) -> dict[str, Any]:
    """Reindex knowledge base."""
    from omni.core.knowledge.librarian import Librarian

    try:
        librarian = Librarian(table_name="knowledge")
        if clear:
            librarian.ingest(clean=True)
            return {
                "status": "success",
                "database": "knowledge.lance",
                "docs_indexed": 0,
                "chunks_indexed": 0,
            }
        result = librarian.ingest()
        return {
            "status": "success",
            "database": "knowledge.lance",
            "docs_indexed": result.get("files_processed", 0),
            "chunks_indexed": result.get("chunks_indexed", 0),
        }
    except Exception as e:
        return {"status": "error", "database": "knowledge.lance", "error": str(e)}


def reindex_memory(_clear: bool = False) -> dict[str, Any]:
    """Memory is populated during conversations, not reindexed."""
    return {
        "status": "info",
        "database": "memory.lance",
        "message": "Memory is populated during conversations, not reindexed",
    }


def reindex_all(
    clear: bool,
    sync_symbols: Callable[[bool], dict[str, Any]] | None = None,
    sync_router_init: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run full reindex (symbols, skills, router, knowledge, memory).
    Caller may pass sync_symbols(clear) and sync_router_init() to avoid service->cli deps.
    """
    results: dict[str, Any] = {}
    if sync_symbols is not None:
        results["symbols"] = sync_symbols(clear)
    else:
        results["symbols"] = {"status": "skipped", "details": "no sync_symbols"}
    skills_result = reindex_skills_only(clear)
    if skills_result.get("status") == "success":
        results["skills"] = {
            "status": "success",
            "database": "skills.lance",
            "tools_indexed": int(skills_result.get("skills_tools_indexed", 0)),
        }
        _write_embedding_signature()
    else:
        results["skills"] = {
            "status": "error",
            "database": "skills.lance",
            "error": str(skills_result.get("error", "unknown")),
        }
    if sync_router_init is not None:
        router_out = sync_router_init()
        results["router"] = {
            "status": router_out.get("status", "skipped"),
            "details": router_out.get("details", "Router DB (scores) initialized"),
        }
    else:
        results["router"] = {"status": "skipped", "details": "no sync_router_init"}
    results["knowledge"] = reindex_knowledge(clear)
    results["memory"] = reindex_memory()
    return results


def reindex_status() -> dict[str, Any]:
    """Return status of all vector databases."""
    from omni.foundation.bridge import RustVectorStore
    from omni.core.knowledge.librarian import Librarian

    db_paths = get_database_paths()
    stats = {}
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
    return stats


def reindex_clear() -> dict[str, Any]:
    """Clear all vector databases."""
    from omni.foundation.bridge import RustVectorStore

    cleared = []
    for table in ["skills"]:
        try:
            store = RustVectorStore(enable_keyword_index=True)
            run_async_blocking(store.drop_table(table))
            cleared.append(table)
        except Exception:
            pass
    try:
        from omni.core.knowledge.librarian import Librarian

        librarian = Librarian(collection="knowledge")
        if librarian.is_ready:
            librarian.clear()
            cleared.append("knowledge")
    except Exception:
        pass
    return {"status": "success", "cleared": cleared}
