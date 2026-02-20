"""Row conversion helpers for knowledge recall retrieval outputs."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


def build_recall_row(
    *,
    content: str,
    source: str,
    score: float,
    title: str = "",
    section: str = "",
) -> dict[str, Any]:
    """Build one normalized recall row."""
    return {
        "content": content,
        "source": source,
        "score": round(score, 4),
        "title": title,
        "section": section,
    }


def recall_rows_from_vector_results(raw_results: Iterable[Any]) -> list[dict[str, Any]]:
    """Convert vector search result objects into normalized recall rows."""
    rows: list[dict[str, Any]] = []
    for item in raw_results:
        distance = getattr(item, "distance", 0.0)
        score = max(0.0, 1.0 - distance)
        metadata = item.metadata if isinstance(getattr(item, "metadata", None), dict) else {}
        rows.append(
            build_recall_row(
                content=getattr(item, "content", ""),
                source=str(metadata.get("source") or getattr(item, "id", "")),
                score=score,
                title=str(metadata.get("title", "")),
                section=str(metadata.get("section", "")),
            )
        )
    return rows


def recall_rows_from_hybrid_json(
    json_results: Iterable[str],
    *,
    on_parse_error: Callable[[Exception], None] | None = None,
) -> list[dict[str, Any]]:
    """Convert hybrid JSON string results into normalized recall rows."""
    rows: list[dict[str, Any]] = []
    for json_str in json_results:
        try:
            data = json.loads(json_str)
            distance = data.get("distance", 1.0)
            score = max(0.0, 1.0 - distance)
            metadata = data.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            rows.append(
                build_recall_row(
                    content=str(metadata.get("content", data.get("content", ""))),
                    source=str(metadata.get("source", data.get("id", ""))),
                    score=score,
                    title=str(metadata.get("title", "")),
                    section=str(metadata.get("section", "")),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            if on_parse_error is not None:
                on_parse_error(exc)
            continue
    return rows


__all__ = [
    "build_recall_row",
    "recall_rows_from_hybrid_json",
    "recall_rows_from_vector_results",
]
