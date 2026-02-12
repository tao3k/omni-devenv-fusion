"""Shared normalization helpers for retrieval backends."""

from __future__ import annotations

from collections.abc import Iterable

from .interface import RetrievalResult


def normalize_ranked_results(
    results: Iterable[RetrievalResult],
    *,
    score_threshold: float = 0.0,
) -> list[RetrievalResult]:
    """Apply common post-processing: thresholding, dedupe, stable ranking.

    Dedupe key priority:
    1. `id` if present.
    2. `content` fallback for rows without durable ids.
    """
    best_by_key: dict[str, RetrievalResult] = {}
    for result in results:
        if result.score < score_threshold:
            continue

        result_id = result.id.strip()
        result_content = result.content.strip()
        if not result_id and not result_content:
            continue

        dedupe_key = result_id or result_content
        prev = best_by_key.get(dedupe_key)
        if prev is None or result.score > prev.score:
            best_by_key[dedupe_key] = result

    ranked = list(best_by_key.values())
    ranked.sort(key=lambda item: (-item.score, item.id or item.content))
    return ranked


__all__ = ["normalize_ranked_results"]
