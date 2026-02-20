"""Common post-processing pipeline for recall retrieval rows."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omni.foundation.runtime.skill_optimization import filter_ranked_chunks, is_markdown_index_chunk

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def filter_recall_rows(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    min_score: float = 0.0,
    index_detector: Callable[[str], bool] = is_markdown_index_chunk,
) -> list[dict[str, Any]]:
    """Filter + rank recall rows with shared TOC/index demotion policy."""
    return filter_ranked_chunks(
        rows,
        limit=limit,
        min_score=min_score,
        index_detector=index_detector,
    )


async def apply_recall_postprocess(
    rows: list[dict[str, Any]],
    *,
    query: str,
    limit: int,
    min_score: float,
    preview: bool,
    snippet_chars: int,
    apply_boost: bool = True,
    boost_rows: Callable[[list[dict[str, Any]], str], Awaitable[list[dict[str, Any]]]]
    | None = None,
    index_detector: Callable[[str], bool] = is_markdown_index_chunk,
) -> list[dict[str, Any]]:
    """
    Run recall post-process pipeline: optional boost -> filter -> preview truncation.

    Behavior matches legacy `knowledge.recall`:
    - boost only when not preview
    - preview mode bypasses min_score threshold (effective -1.0)
    - if filtered result is empty, fallback to first `limit` rows
    """
    result_rows = rows
    if not preview and apply_boost and boost_rows is not None:
        result_rows = await boost_rows(result_rows, query)

    effective_min_score = -1.0 if preview else min_score
    filtered = filter_recall_rows(
        result_rows,
        limit=limit,
        min_score=effective_min_score,
        index_detector=index_detector,
    )
    result_rows = filtered if filtered else result_rows[:limit]

    if preview:
        for row in result_rows:
            content = str(row.get("content") or "")
            row["content"] = (
                f"{content[:snippet_chars]}…" if len(content) > snippet_chars else content
            )
            row["preview"] = True
    return result_rows


__all__ = [
    "apply_recall_postprocess",
    "filter_recall_rows",
]
