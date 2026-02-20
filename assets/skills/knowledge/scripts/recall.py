"""
assets/skills/knowledge/scripts/recall.py
The Neural Matrix - Unified Knowledge Recall System

Provides semantic + keyword hybrid search over project knowledge.
Uses Rust-powered LanceDB for high-performance retrieval.

Commands:
- recall: Semantic search with hybrid ranking
- ingest: Add content to knowledge base
- stats: Get knowledge base statistics

Performance: recall latency is dominated by embedding (one HTTP call per query when using
vector search). Use embedding.provider=client and a running MCP embedding server for best
first-call speed; avoid extra health check by setting provider in settings.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import structlog

from omni.foundation import PRJ_CACHE, get_vector_store
from omni.foundation.api.decorators import skill_command
from omni.foundation.api.mcp_schema import parse_result_payload
from omni.foundation.api.response_payloads import (
    build_status_error_response,
    build_status_message_response,
)
from omni.foundation.context_delivery import (
    ChunkedSessionStore,
    normalize_chunked_action_name,
)
from omni.foundation.runtime.skill_optimization import (
    is_low_signal_query,
    is_markdown_index_chunk,
    normalize_chunk_window,
    normalize_min_score,
    normalize_snippet_chars,
)
from omni.langgraph.chunked import (
    build_chunked_action_error_payload,
    build_chunked_dispatch_error_payload,
    build_chunked_session_store_adapters,
    build_chunked_unavailable_payload,
    create_chunked_lazy_start_payload,
    persist_chunked_lazy_start_state,
    run_chunked_full_document_action,
    run_chunked_lazy_start_batch_dispatch,
    run_chunked_preview_action,
)
from omni.rag.retrieval.executor import run_recall_query_rows
from omni.rag.retrieval.postprocess import apply_recall_postprocess
from omni.rag.retrieval.response import (
    build_recall_error_response,
    build_recall_search_response,
)

logger = structlog.get_logger(__name__)

_RECALL_CHUNKED_WORKFLOW_TYPE = "recall_chunked"
_RECALL_CHUNKED_STORE = ChunkedSessionStore(_RECALL_CHUNKED_WORKFLOW_TYPE)
(
    _LOAD_RECALL_CHUNKED_STATE,
    _LOAD_RECALL_SESSION_STATE,
    _SAVE_RECALL_SESSION_STATE,
) = build_chunked_session_store_adapters(_RECALL_CHUNKED_STORE)


@contextmanager
def _suspend_skills_monitor():
    """Suppress nested skill_command.execute phases for internal recall recursion."""
    try:
        from omni.foundation.runtime.skills_monitor import suppress_skill_command_phase_events
    except Exception:
        yield
        return

    with suppress_skill_command_phase_events():
        yield


def _get_image_paths_for_source(source_suffix: str) -> list[str]:
    """Return image paths for a source from the ingest image manifest (suffix match).
    Lets the LLM read PDF-extracted images by path when doing full_document recall.
    """
    if not source_suffix or not source_suffix.strip():
        return []
    try:
        manifest_path = PRJ_CACHE("omni-vector", "image_manifests.json")
        path = Path(manifest_path) if not isinstance(manifest_path, Path) else manifest_path
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        suffix = source_suffix.strip()
        for key, paths in data.items():
            if key.endswith(suffix) or key == suffix:
                if isinstance(paths, list):
                    return [p for p in paths if isinstance(p, str)]
                return []
    except Exception:
        pass
    return []


def _unwrap_mcp_recall_result(out: Any) -> dict:
    """Extract inner recall payload when @skill_command wrapped it as MCP content+isError."""
    return parse_result_payload(out)


def _get_run_chunked_recall():
    """Resolve run_chunked_recall from paper_workflow via loader's package (same scripts dir)."""
    try:
        from paper_workflow import run_chunked_recall

        return run_chunked_recall
    except ImportError:
        pass
    # Use same package as this module (set by skill loader when loading scripts)
    pkg = __package__
    if pkg:
        mod = importlib.import_module(".paper_workflow", package=pkg)
        return mod.run_chunked_recall
    raise ImportError("Could not load run_chunked_recall from paper_workflow")


async def _apply_filter_and_preview(
    result_dicts: list[dict],
    query: str,
    limit: int,
    min_score: float,
    preview: bool,
    snippet_chars: int,
    *,
    apply_dual_core_boost: bool = True,
) -> list[dict]:
    """Single pipeline: dual-core boost (if not preview), filter, optional preview truncation."""
    return await apply_recall_postprocess(
        result_dicts,
        query=query,
        limit=limit,
        min_score=min_score,
        preview=preview,
        snippet_chars=snippet_chars,
        apply_boost=apply_dual_core_boost,
        boost_rows=_apply_dual_core_recall_boost,
        index_detector=is_markdown_index_chunk,
    )


# =============================================================================
# Knowledge Recall Commands (The Neural Matrix)
# =============================================================================


@skill_command(
    name="recall",
    category="search",
    description="""
    Semantic + Keyword Hybrid Search over Project Knowledge (The Neural Matrix).

    PRIMARY interface for retrieving knowledge from the vector store.
    Recalled content is usually long (papers, manuals, docs), so the default is a chunked
    workflow (preview → fetch → batches); the model reads each batch in memory in turn.

    Use guidance for Agent (infer parameters from user intent):
    - User wants FULL document (e.g. "整篇论文", "complete paper", "全文"): First recall(query=..., limit=5) to get top result, extract "source" from result (e.g. "2601.03192.pdf"); then recall(action="full_document", source=that_source, full_document_batch_size=15) to get batch 0; call again with full_document_batch_index=1,2,... until batch_index >= batch_count-1 (balances token limit and call count).
    - User wants snippet/summary only: recall(query=..., chunked=False, limit=3~5).
    - User wants long doc in batches: action="start" then action="batch" with session_id; set batch_size (e.g. 5) and max_chunks (e.g. 40 for papers) based on expected length.
    - batch_size, max_chunks, limit: Infer from context (short doc→smaller, long paper→larger).

    Args:
        - query: str - Natural language query (required)
        - chunked: bool = True - If True (default), run preview→fetch→batches workflow for long content; if False, single-call search only.
        - limit: int = 5 - With chunked: preview list size and max_chunks; with chunked=False: how many items to return. Default is conservative to avoid LLM context overflow.
        - preview_limit: int = 10 - When chunked=True, items in preview list (accuracy check).
        - batch_size: int = 5 - When chunked=True, chunks per batch (feed batches[i] to LLM in turn).
        - max_chunks: int = 15 - When chunked=True, max full chunks to fetch then split into batches. Conservative default to avoid LLM overflow.
        - action: str = "" - When chunked=True: "start" = preview only, returns session_id (no full fetch); "batch" = lazy-fetch one batch (session_id, batch_index); "full_document" = return chunks for source in batches (no omission; use full_document_batch_size + full_document_batch_index).
        - source: str = "" - When action="full_document", source path/identifier (e.g. 2601.03192.pdf).
        - full_document_batch_size: int = 15 - When action="full_document", chunks per batch (balances token limit vs call count); 0 = return all at once.
        - full_document_batch_index: int = 0 - When action="full_document", which batch (0-based); call repeatedly with 0,1,... until batch_index >= batch_count-1.
        - session_id: str = "" - When action="batch", the session_id returned by action="start".
        - batch_index: int = -1 - When action="batch", which batch to return (0-based).
        - preview: bool = False - When chunked=False, if True return only title/source and first snippet_chars per result.
        - snippet_chars: int = 150 - When preview=True, max characters of content per result.
        - keywords: Optional[list[str]] - Keywords to boost precision (used when chunked=False or inside workflow).
        - retrieval_mode: str = hybrid - Retrieval policy mode: graph_only | hybrid | vector_only.
        - min_score: float = 0.0 - Minimum relevance score (0-1)
        - collection: str = knowledge_chunks - Collection to search
        - optimization_profile: str = balanced - Tuning profile: balanced | latency | throughput

    Returns:
        When chunked=True: action="start" returns session_id; action="batch" returns one chunk batch (avoids memory accumulation). action="" or "auto" = one-shot full result. When chunked=False: JSON with results.
    """,
)
async def recall(
    query: str = "",
    chunked: bool = True,
    limit: int = 5,
    preview_limit: int = 10,
    batch_size: int = 5,
    max_chunks: int = 15,
    action: str = "",
    source: str = "",
    full_document_batch_size: int = 15,
    full_document_batch_index: int = 0,
    session_id: str = "",
    batch_index: int = -1,
    preview: bool = False,
    snippet_chars: int = 150,
    keywords: list[str] | None = None,
    retrieval_mode: str = "hybrid",
    min_score: float = 0.0,
    collection: str = "knowledge_chunks",
    optimization_profile: str = "balanced",
) -> str:
    """
    Recall knowledge. Default: chunked workflow so the LLM can read long docs in batches.
    Set chunked=False for single-call search only (e.g. when you need one short list).
    Use action=preview / fetch / batch when chunked=True to run one step per MCP call and avoid timeout.
    """
    # Validate and normalize parameters (shared policy in foundation runtime).
    normalized = normalize_chunk_window(
        limit=limit,
        preview_limit=preview_limit,
        batch_size=batch_size,
        max_chunks=max_chunks,
        chunked=chunked,
        profile=optimization_profile,
        enforce_limit_cap=True,
    )
    limit = normalized.limit
    preview_limit = normalized.preview_limit
    batch_size = normalized.batch_size
    max_chunks = normalized.max_chunks

    snippet_chars = normalize_snippet_chars(snippet_chars, profile=optimization_profile)
    min_score = normalize_min_score(min_score, default=0.0)
    # Keep DB query count aligned with user-facing `limit`.
    fetch_limit = limit

    act = normalize_chunked_action_name(action) if chunked else ""
    if chunked and act in ("preview", "fetch", "start") and not (query or "").strip():
        return json.dumps(
            build_chunked_action_error_payload(
                action=act,
                message="query required for action preview/fetch/start",
            ),
            indent=2,
        )
    if chunked and act == "full_document" and not (source or "").strip():
        return json.dumps(
            build_chunked_action_error_payload(
                action="full_document",
                message="source required for action=full_document (e.g. 2601.03192.pdf)",
            ),
            indent=2,
        )

    try:
        vector_store = get_vector_store()
        active_store = vector_store.get_store_for_collection(collection)
        if not active_store:
            return json.dumps(
                build_chunked_unavailable_payload(
                    query=query,
                    message="Vector store not initialized. Run 'omni skill reload' first.",
                ),
                indent=2,
            )
    except Exception:
        return json.dumps(
            build_chunked_unavailable_payload(
                query=query,
                message="Vector store not initialized.",
            ),
            indent=2,
        )

    # Chunked workflow: action-based steps (smart_commit pattern) to avoid memory accumulation.
    # Each action returns one small result; LLM reads slice by slice.
    # - start: preview only, returns session_id + batch_count (no full fetch)
    # - batch: lazy-fetch one batch on demand (no full state in checkpoint)
    if chunked:
        if act == "full_document":
            store = vector_store.get_store_for_collection(collection)
            if not store or not hasattr(store, "list_all"):
                return json.dumps(
                    build_chunked_unavailable_payload(
                        action="full_document",
                        message="Store does not support list_all for full_document recall.",
                    ),
                    indent=2,
                )
            fd_payload = await run_chunked_full_document_action(
                source=source,
                list_all_entries=lambda source_suffix: store.list_all(
                    collection,
                    source_filter=source_suffix,
                ),
                batch_size=full_document_batch_size,
                batch_index=full_document_batch_index,
                action="full_document",
                batch_index_param="full_document_batch_index",
                extra_payload_factory=lambda source_suffix: (
                    {"image_paths": paths}
                    if (paths := _get_image_paths_for_source(source_suffix))
                    else None
                ),
            )
            return json.dumps(
                fd_payload,
                indent=2,
                ensure_ascii=False,
            )
        if act == "preview":

            async def _run_preview() -> Any:
                with _suspend_skills_monitor():
                    return await recall(
                        query=query,
                        chunked=False,
                        limit=preview_limit,
                        preview=True,
                        snippet_chars=min(500, max(50, int(snippet_chars))),
                        retrieval_mode=retrieval_mode,
                        collection=collection,
                        optimization_profile=optimization_profile,
                    )

            payload = await run_chunked_preview_action(
                query=query,
                run_preview=_run_preview,
                parse_preview_payload=_unwrap_mcp_recall_result,
                timeout_seconds=15,
                action="preview",
                success_message=(
                    "Call action=start to get session_id, then action=batch with "
                    "session_id and batch_index to read each chunk."
                ),
                timeout_message=(
                    "Recall preview timed out after 15s. Check embedding server "
                    "(e.g. provider: client and client_url) or reduce load."
                ),
            )
            return json.dumps(payload, indent=2, ensure_ascii=False)

        async def _on_start() -> dict[str, Any]:
            # Start workflow: preview only; batch calls fetch full rows once and persist cache.
            local_max_chunks = max(batch_size, max_chunks)

            try:
                with _suspend_skills_monitor():
                    out = await asyncio.wait_for(
                        recall(
                            query=query,
                            chunked=False,
                            limit=preview_limit,
                            preview=True,
                            snippet_chars=min(500, max(50, int(snippet_chars))),
                            retrieval_mode=retrieval_mode,
                            collection=collection,
                            optimization_profile=optimization_profile,
                        ),
                        timeout=15,
                    )
            except TimeoutError:
                return build_chunked_action_error_payload(
                    action=act,
                    message="Preview timed out. Check embedding server.",
                    preview_results=[],
                )
            data = _unwrap_mcp_recall_result(out)
            preview_list = data.get("results", [])

            state = {
                "query": query,
                "collection": collection,
                "batch_size": batch_size,
                "max_chunks": local_max_chunks,
                "preview_results": preview_list,
                "retrieval_mode": retrieval_mode,
                "optimization_profile": optimization_profile,
                # Filled lazily by first action=batch call to avoid duplicate DB queries.
                "cached_results_ready": False,
                "cached_results": [],
            }

            return create_chunked_lazy_start_payload(
                query=query,
                batch_size=batch_size,
                max_items=local_max_chunks,
                preview_results=preview_list,
                status=str(data.get("status", "success")),
                state=state,
                persist_state=lambda session_key, workflow_state: persist_chunked_lazy_start_state(
                    store=_RECALL_CHUNKED_STORE,
                    session_id=session_key,
                    state=workflow_state,
                ),
                session_id_factory=lambda: str(uuid.uuid4()),
                action="start",
            )

        if act in ("start", "fetch", "batch"):

            async def _fetch_rows(state: dict[str, Any]) -> list[Any]:
                local_query = state.get("query", "")
                local_collection = state.get("collection", "knowledge_chunks")
                local_max_chunks = state.get("max_chunks", 30)
                local_retrieval_mode = state.get("retrieval_mode", "hybrid")
                local_profile = state.get("optimization_profile", "balanced")

                with _suspend_skills_monitor():
                    out = await asyncio.wait_for(
                        recall(
                            query=local_query,
                            chunked=False,
                            limit=local_max_chunks,
                            preview=False,
                            retrieval_mode=local_retrieval_mode,
                            collection=local_collection,
                            optimization_profile=local_profile,
                        ),
                        timeout=30,
                    )
                data = _unwrap_mcp_recall_result(out)
                rows = data.get("results", [])
                return rows if isinstance(rows, list) else []

            dispatch_result = await run_chunked_lazy_start_batch_dispatch(
                action=act,
                session_id=session_id,
                batch_index=batch_index,
                workflow_type=_RECALL_CHUNKED_WORKFLOW_TYPE,
                load_state=_LOAD_RECALL_CHUNKED_STATE,
                on_start=_on_start,
                load_session_state=_LOAD_RECALL_SESSION_STATE,
                save_session_state=_SAVE_RECALL_SESSION_STATE,
                fetch_rows=_fetch_rows,
                batch_action="batch",
                batch_size_key="batch_size",
                max_items_key="max_chunks",
                cache_ready_key="cached_results_ready",
                cache_rows_key="cached_results",
                default_batch_size=5,
                default_max_items=30,
                missing_session_template="session_id not found: {session_id}",
                invalid_batch_template="batch_index must be 0..{max_index}",
                fetch_timeout_message="Recall timed out for this batch.",
                session_required_error="session_id required for action=batch",
                session_missing_error="session_id not found: {session_id}",
            )
            if isinstance(dispatch_result, dict) and dispatch_result.get("success") is False:
                return json.dumps(
                    build_chunked_dispatch_error_payload(
                        action="batch" if act == "batch" else act,
                        dispatch_result=dispatch_result,
                        fallback_message="chunked action dispatch failed",
                    ),
                    indent=2,
                    ensure_ascii=False,
                )
            return json.dumps(dispatch_result, indent=2, ensure_ascii=False)

        # action="" or "auto" or unknown: one-shot full chunked result (original behavior)
        run_chunked_recall = _get_run_chunked_recall()
        result = await run_chunked_recall(
            query=query,
            preview_limit=preview_limit,
            batch_size=batch_size,
            max_chunks=max_chunks,
            collection=collection,
            profile=optimization_profile,
        )
        return json.dumps(result, indent=2, ensure_ascii=False)

    keywords = keywords or []

    try:
        retrieval_path = "vector_only"
        retrieval_reason = "vector_default"
        graph_backend = ""
        graph_hit_count = 0
        graph_confidence_score = 0.0
        graph_confidence_level = "none"
        retrieval_plan_record: dict[str, Any] | None = None
        retrieval_plan_schema_id = ""
        enable_dual_core_boost = retrieval_mode != "vector_only"

        if keywords and retrieval_mode == "graph_only":
            retrieval_reason = "keywords_force_vector"

        if (
            not keywords
            and not is_low_signal_query(query, min_non_space_chars=2)
            and (query or "").strip()
        ):
            try:
                from omni.rag.link_graph import evaluate_link_graph_recall_policy

                policy = await evaluate_link_graph_recall_policy(
                    query=query,
                    limit=limit,
                    retrieval_mode=retrieval_mode,
                    store=vector_store.get_store_for_collection(collection),
                    collection=collection,
                )

                retrieval_path = policy.retrieval_path
                retrieval_reason = policy.retrieval_reason
                graph_backend = policy.graph_backend
                graph_hit_count = policy.graph_hit_count
                graph_confidence_score = policy.graph_confidence_score
                graph_confidence_level = policy.graph_confidence_level
                retrieval_plan_schema_id = policy.retrieval_plan_schema_id
                retrieval_plan_record = policy.retrieval_plan

                if policy.graph_rows:
                    result_dicts = await _apply_filter_and_preview(
                        list(policy.graph_rows),
                        query,
                        limit,
                        min_score,
                        preview,
                        snippet_chars,
                        apply_dual_core_boost=False,
                    )
                    response = build_recall_search_response(
                        query=query,
                        keywords=keywords,
                        collection=collection,
                        preview=preview,
                        retrieval_mode=retrieval_mode,
                        retrieval_path=retrieval_path,
                        retrieval_reason=retrieval_reason,
                        graph_backend=graph_backend,
                        graph_hit_count=graph_hit_count,
                        graph_confidence_score=graph_confidence_score,
                        graph_confidence_level=graph_confidence_level,
                        retrieval_plan_schema_id=retrieval_plan_schema_id,
                        retrieval_plan=retrieval_plan_record,
                        results=result_dicts,
                    )
                    return json.dumps(response, indent=2, ensure_ascii=False)

                if policy.graph_only_empty:
                    response = build_recall_search_response(
                        query=query,
                        keywords=keywords,
                        collection=collection,
                        preview=preview,
                        retrieval_mode=retrieval_mode,
                        retrieval_path=retrieval_path,
                        retrieval_reason=retrieval_reason,
                        graph_backend=graph_backend,
                        graph_hit_count=graph_hit_count,
                        graph_confidence_score=graph_confidence_score,
                        graph_confidence_level=graph_confidence_level,
                        retrieval_plan_schema_id=retrieval_plan_schema_id,
                        retrieval_plan=retrieval_plan_record,
                        results=[],
                    )
                    return json.dumps(response, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.debug("LinkGraph policy retrieval skipped: %s", e)
                retrieval_path = "vector_only"
                retrieval_reason = "policy_error_fallback_vector"

        # Single-call search (chunked=False)
        result_dicts = await run_recall_query_rows(
            vector_store=vector_store,
            query=query,
            keywords=keywords,
            collection=collection,
            fetch_limit=fetch_limit,
            use_semantic_cache=False,
            on_parse_error=lambda exc: logger.debug("Failed to parse search result: %s", exc),
        )
        result_dicts = await _apply_filter_and_preview(
            result_dicts,
            query,
            limit,
            min_score,
            preview,
            snippet_chars,
            apply_dual_core_boost=enable_dual_core_boost,
        )
        response = build_recall_search_response(
            query=query,
            keywords=keywords,
            collection=collection,
            preview=preview,
            retrieval_mode=retrieval_mode,
            retrieval_path=retrieval_path,
            retrieval_reason=retrieval_reason,
            graph_backend=graph_backend,
            graph_hit_count=graph_hit_count,
            graph_confidence_score=graph_confidence_score,
            graph_confidence_level=graph_confidence_level,
            retrieval_plan_schema_id=retrieval_plan_schema_id,
            retrieval_plan=retrieval_plan_record,
            results=result_dicts,
        )

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error("Recall failed: %s", e)
        return json.dumps(
            build_recall_error_response(
                query=query,
                error=str(e),
                results=[],
            ),
            indent=2,
            ensure_ascii=False,
        )


@skill_command(
    name="ingest",
    category="write",
    description="""
    Add content to the knowledge base for semantic retrieval.

    Args:
        - content: str - Text content to embed and store (required)
        - source: str - Source path/identifier (e.g., docs/guide.md) (required)
        - metadata: Optional[Dict[str, Any]] - Dictionary of metadata (tags, title, etc.)
        - collection: str = knowledge - Collection name

    Returns:
        JSON with ingestion status, document_id, source, and content_length.
    """,
)
async def ingest(
    content: str,
    source: str,
    metadata: dict[str, Any] | None = None,
    collection: str = "knowledge",
) -> str:
    """
    Ingest content into the knowledge base.

    Args:
        content: Text content to embed and store.
        source: Source identifier (file path, URL, etc.).
        metadata: Optional metadata dictionary.
        collection: Collection name.

    Returns:
        JSON with ingestion result.
    """
    try:
        vector_store = get_vector_store()

        if not vector_store.store:
            return json.dumps(
                build_status_message_response(
                    status="unavailable",
                    message="Vector store not initialized.",
                ),
                indent=2,
            )

        # Add via VectorStoreClient
        success = await vector_store.add(content, metadata, collection)

        if success:
            doc_id = f"doc_{hash(source) % 100000:05d}"
            return json.dumps(
                {
                    "status": "success",
                    "document_id": doc_id,
                    "source": source,
                    "content_length": len(content),
                    "collection": collection,
                },
                indent=2,
            )
        else:
            return json.dumps(
                build_status_error_response(
                    error="Failed to add content to vector store",
                ),
                indent=2,
            )

    except Exception as e:
        logger.error(f"Ingest failed: {e}")
        return json.dumps(
            build_status_error_response(error=str(e)),
            indent=2,
        )


@skill_command(
    name="stats",
    category="view",
    description="""
    Get knowledge base statistics including document count and vector dimension.

    Args:
        - collection: str = knowledge - Collection name

    Returns:
        JSON with status, collection, document_count, and vector_dimension.
    """,
)
async def stats(collection: str = "knowledge_chunks") -> str:
    """
    Get knowledge base statistics.

    Args:
        collection: Collection name.

    Returns:
        JSON with statistics.
    """
    try:
        vector_store = get_vector_store()

        if not vector_store.store:
            return json.dumps(
                build_status_message_response(
                    status="unavailable",
                    message="Vector store not initialized.",
                ),
                indent=2,
            )

        count = await vector_store.count(collection)

        # Get dimension from embedding service
        from omni.foundation.services.embedding import get_embedding_service

        dimension = get_embedding_service().dimension

        return json.dumps(
            {
                "status": "success",
                "collection": collection,
                "document_count": count,
                "vector_dimension": dimension,
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Stats failed: {e}")
        return json.dumps(
            build_status_error_response(error=str(e)),
            indent=2,
        )


@skill_command(
    name="clear",
    category="write",
    description="""
    Clear all knowledge from a collection. WARNING: Permanently deletes indexed knowledge.

    Args:
        - collection: str = knowledge - Collection name to clear

    Returns:
        JSON with status and message.
    """,
)
async def clear(collection: str = "knowledge_chunks") -> str:
    """
    Clear all knowledge from a collection.

    Args:
        collection: Collection name.

    Returns:
        JSON with operation status.
    """
    try:
        vector_store = get_vector_store()

        if not vector_store.store:
            return json.dumps(
                build_status_message_response(
                    status="unavailable",
                    message="Vector store not initialized.",
                ),
                indent=2,
            )

        # Drop and recreate the table
        store = vector_store.get_store_for_collection(collection)
        if store:
            store.drop_table(collection)

        return json.dumps(
            {
                "status": "success",
                "message": f"Collection '{collection}' cleared.",
            },
            indent=2,
        )

    except Exception as e:
        logger.error(f"Clear failed: {e}")
        return json.dumps(
            build_status_error_response(error=str(e)),
            indent=2,
        )


# =============================================================================
# Dual-Core Recall Bridges (LinkGraph + KG Entity)
# =============================================================================


async def _apply_dual_core_recall_boost(
    result_dicts: list[dict],
    query: str,
) -> list[dict]:
    """Apply all dual-core bridges to recall results (non-blocking).

    Pipeline:
    1. Compute dynamic fusion weights from Rust intent extractor.
    2. Bridge 1: LinkGraph proximity boost (scaled by fusion weights).
    3. Bridge 1b: KG entity boost (scaled by fusion weights).

    If any bridge is unavailable, results pass through unchanged.
    """
    # Low-signal probes (e.g. "x") should avoid heavy bridge work.
    if is_low_signal_query(query, min_non_space_chars=2):
        return result_dicts

    try:
        from omni.rag.dual_core import apply_kg_recall_boost, compute_fusion_weights
        from omni.rag.link_graph import apply_link_graph_proximity_boost

        # Shared intent analysis — computed once, used by all bridges
        fusion = compute_fusion_weights(query)

        # Bridge 1: common LinkGraph proximity
        result_dicts = await apply_link_graph_proximity_boost(
            result_dicts, query, fusion_scale=fusion.link_graph_proximity_scale
        )

        # Bridge 1b: KG entity boost
        result_dicts = apply_kg_recall_boost(
            result_dicts, query, fusion_scale=fusion.link_graph_entity_scale
        )

    except Exception as e:
        logger.debug("Dual-core recall boost skipped: %s", e)

    return result_dicts


# =============================================================================
# Helper Functions
# =============================================================================


def format_recall_results(json_output: str) -> str:
    """Format recall results as markdown for display."""
    try:
        data = json.loads(json_output)

        if "error" in data or data.get("status") == "error":
            return f"**Recall Error**: {data.get('error', 'Unknown error')}"

        if data.get("status") == "unavailable":
            return f"**Knowledge Base Unavailable**: {data.get('message', '')}"

        results = data.get("results", [])
        if not results:
            return f"**No knowledge found for**: `{data.get('query', '')}`"

        lines = [
            "# Knowledge Recall",
            f"**Query**: `{data.get('query', '')}`",
            f"**Found**: {data.get('found', 0)} results",
            "",
            "---",
        ]

        for i, result in enumerate(results, 1):
            title = result.get("title", "Unknown")
            section = result.get("section", "")
            source = result.get("source", "")
            score = result.get("score", 0)
            content = result.get("content", "")

            lines.append(f"## {i}. {title}")
            if section:
                lines.append(f"**Section**: {section}")
            lines.append(f"**Relevance**: {score:.1%}")
            lines.append(f"**Source**: `{source}`")
            lines.append("")
            lines.append(f"> {content}")
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    except json.JSONDecodeError:
        return json_output


__all__ = ["clear", "format_recall_results", "ingest", "recall", "stats"]
