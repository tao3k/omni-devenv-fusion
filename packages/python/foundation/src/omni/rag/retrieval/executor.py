"""Common execution helpers for recall retrieval query paths."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from omni.foundation.runtime.skills_monitor.phase import (
    record_phase_with_memory,
    start_phase_sample,
)

from .rows import recall_rows_from_hybrid_json, recall_rows_from_vector_results

if TYPE_CHECKING:
    from collections.abc import Callable


def _normalize_fetch_limit(fetch_limit: int) -> int:
    """Normalize fetch_limit into a safe positive integer."""
    try:
        return max(1, int(fetch_limit))
    except (TypeError, ValueError):
        return 1


def _cap_rows(rows: list[dict[str, Any]], fetch_limit: int) -> list[dict[str, Any]]:
    """Enforce hard cap on normalized rows to avoid backend over-fetch leaks."""
    limit = _normalize_fetch_limit(fetch_limit)
    if len(rows) <= limit:
        return rows
    return rows[:limit]


async def run_recall_semantic_rows(
    *,
    vector_store: Any,
    query: str,
    collection: str,
    fetch_limit: int,
    use_cache: bool = False,
) -> list[dict[str, Any]]:
    """Run semantic-only recall query and return normalized rows."""
    started_at, rss_before, rss_peak_before = start_phase_sample()
    limit = _normalize_fetch_limit(fetch_limit)
    raw_rows_count = 0
    parsed_rows_count = 0
    returned_rows_count = 0
    try:
        raw_results = await vector_store.search(query, limit, collection, use_cache=use_cache)
        if isinstance(raw_results, list):
            raw_rows_count = len(raw_results)
        rows = recall_rows_from_vector_results(raw_results)
        parsed_rows_count = len(rows)
        capped = _cap_rows(rows, limit)
        returned_rows_count = len(capped)
        return capped
    finally:
        record_phase_with_memory(
            "retrieval.rows.semantic",
            started_at,
            rss_before,
            rss_peak_before,
            mode="semantic",
            collection=collection,
            fetch_limit=limit,
            rows_fetched=raw_rows_count,
            rows_parsed=parsed_rows_count,
            rows_returned=returned_rows_count,
            rows_capped=max(0, parsed_rows_count - returned_rows_count),
        )


async def run_recall_hybrid_rows(
    *,
    vector_store: Any,
    query: str,
    keywords: list[str] | None,
    collection: str,
    fetch_limit: int,
    on_parse_error: Callable[[Exception], None] | None = None,
) -> list[dict[str, Any]]:
    """Run hybrid recall query (embedding + Rust hybrid search) and return normalized rows."""
    from omni.foundation.services.embedding import EmbeddingUnavailableError, get_embedding_service
    from omni.foundation.services.vector import _search_embed_timeout

    started_at, rss_before, rss_peak_before = start_phase_sample()
    limit = _normalize_fetch_limit(fetch_limit)
    raw_rows_count = 0
    parsed_rows_count = 0
    returned_rows_count = 0
    embed_timeout = _search_embed_timeout()
    embedding_service = get_embedding_service()
    try:
        try:
            embed_result = await asyncio.wait_for(
                asyncio.to_thread(embedding_service.embed, query),
                timeout=embed_timeout,
            )
            vector = embed_result[0]
        except TimeoutError as err:
            raise EmbeddingUnavailableError(
                f"Embedding timed out after {embed_timeout}s for recall. "
                "Ensure MCP embedding service is running and responsive."
            ) from err
        except EmbeddingUnavailableError:
            raise

        store = vector_store.get_store_for_collection(collection)
        json_results = (
            store.search_hybrid(collection, vector, keywords or [], limit) if store else []
        )
        if isinstance(json_results, list):
            raw_rows_count = len(json_results)
        rows = recall_rows_from_hybrid_json(
            json_results,
            on_parse_error=on_parse_error,
        )
        parsed_rows_count = len(rows)
        capped = _cap_rows(
            rows,
            limit,
        )
        returned_rows_count = len(capped)
        return capped
    finally:
        record_phase_with_memory(
            "retrieval.rows.hybrid",
            started_at,
            rss_before,
            rss_peak_before,
            mode="hybrid",
            collection=collection,
            fetch_limit=limit,
            rows_fetched=raw_rows_count,
            rows_parsed=parsed_rows_count,
            rows_returned=returned_rows_count,
            rows_capped=max(0, parsed_rows_count - returned_rows_count),
            rows_parse_dropped=max(0, raw_rows_count - parsed_rows_count),
        )


async def run_recall_query_rows(
    *,
    vector_store: Any,
    query: str,
    keywords: list[str] | None,
    collection: str,
    fetch_limit: int,
    use_semantic_cache: bool = False,
    on_parse_error: Callable[[Exception], None] | None = None,
) -> list[dict[str, Any]]:
    """Dispatch recall retrieval by query mode and return normalized rows."""
    limit = _normalize_fetch_limit(fetch_limit)
    mode = "hybrid" if keywords else "semantic"
    input_rows_count = 0
    returned_rows_count = 0
    if keywords:
        rows = await run_recall_hybrid_rows(
            vector_store=vector_store,
            query=query,
            keywords=keywords,
            collection=collection,
            fetch_limit=limit,
            on_parse_error=on_parse_error,
        )
    else:
        rows = await run_recall_semantic_rows(
            vector_store=vector_store,
            query=query,
            collection=collection,
            fetch_limit=limit,
            use_cache=use_semantic_cache,
        )
    input_rows_count = len(rows)
    cap_started_at, cap_rss_before, cap_rss_peak_before = start_phase_sample()
    capped = _cap_rows(rows, limit)
    returned_rows_count = len(capped)
    record_phase_with_memory(
        "retrieval.rows.query",
        cap_started_at,
        cap_rss_before,
        cap_rss_peak_before,
        mode=mode,
        collection=collection,
        fetch_limit=limit,
        rows_input=input_rows_count,
        rows_returned=returned_rows_count,
        rows_capped=max(0, input_rows_count - returned_rows_count),
    )
    return capped


__all__ = [
    "run_recall_hybrid_rows",
    "run_recall_query_rows",
    "run_recall_semantic_rows",
]
