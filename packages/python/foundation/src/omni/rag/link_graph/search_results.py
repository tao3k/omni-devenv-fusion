"""Common conversion helpers for LinkGraph search payloads."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import LinkGraphDirection

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .models import LinkGraphHit


def _as_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, *, default: int = 0, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(minimum, parsed)


def normalize_link_graph_direction(direction: Any) -> LinkGraphDirection:
    """Normalize CLI direction aliases into LinkGraphDirection."""
    raw = str(getattr(direction, "value", direction) or "both").strip().lower()
    if raw in {"to", "incoming"}:
        return LinkGraphDirection.INCOMING
    if raw in {"from", "outgoing"}:
        return LinkGraphDirection.OUTGOING
    return LinkGraphDirection.BOTH


def neighbors_to_link_rows(
    neighbors: Iterable[Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert neighbor rows into `link_graph_links` payload shape (outgoing, incoming)."""
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []

    for neighbor in neighbors:
        direction = normalize_link_graph_direction(getattr(neighbor, "direction", "both"))
        base = {
            "id": str(getattr(neighbor, "stem", "") or ""),
            "title": str(getattr(neighbor, "title", "") or ""),
            "path": str(getattr(neighbor, "path", "") or ""),
        }
        if direction in {LinkGraphDirection.INCOMING, LinkGraphDirection.BOTH}:
            incoming.append({**base, "type": "incoming"})
        if direction in {LinkGraphDirection.OUTGOING, LinkGraphDirection.BOTH}:
            outgoing.append({**base, "type": "outgoing"})

    return outgoing, incoming


def _note_stem_from_path(path_value: str) -> str:
    path = str(path_value or "").strip()
    if not path:
        return ""
    stem = Path(path).stem
    return stem or path


def link_graph_hits_to_search_results(
    hits: Iterable[LinkGraphHit],
    *,
    source: str = "graph_search",
    reasoning: str = "LinkGraph search hit",
) -> list[dict[str, Any]]:
    """Convert backend hits into stable search-result rows."""
    out: list[dict[str, Any]] = []
    for hit in hits:
        stem = str(getattr(hit, "stem", "") or "").strip()
        if not stem:
            continue
        title = str(getattr(hit, "title", "") or "")
        path = str(getattr(hit, "path", "") or "")
        score = max(0.0, _as_float(getattr(hit, "score", 0.0), default=0.0))
        match_reason = str(getattr(hit, "match_reason", "") or "").strip()
        best_section = str(getattr(hit, "best_section", "") or "").strip()
        row_reasoning = match_reason or reasoning
        out.append(
            {
                "title": title,
                "id": stem,
                "path": path,
                "score": score,
                "source": source,
                "distance": 0,
                "reasoning": row_reasoning,
                "lead": "",
            }
        )
        if best_section:
            out[-1]["section"] = best_section
    return out


def link_graph_hits_to_hybrid_results(
    hits: Iterable[LinkGraphHit],
    *,
    source: str = "graph_search",
    reasoning: str = "LinkGraph search hit",
) -> list[dict[str, Any]]:
    """Convert backend hits to hybrid rows (`note` + `score`)."""
    search_rows = link_graph_hits_to_search_results(hits, source=source, reasoning=reasoning)
    out: list[dict[str, Any]] = []
    for row in search_rows:
        out.append(
            {
                "note": {
                    "id": row["id"],
                    "title": row["title"],
                    "path": row["path"],
                },
                "score": row["score"],
                "source": row["source"],
                "distance": row["distance"],
                "reasoning": row["reasoning"],
            }
        )
    return out


def vector_rows_to_hybrid_results(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert vector rows (`source/content/score`) into hybrid rows."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_path = str(row.get("source") or row.get("path") or row.get("id") or "").strip()
        note_id = str(
            row.get("id") or row.get("note_id") or _note_stem_from_path(source_path)
        ).strip()
        score = _as_float(row.get("score"), default=-1.0)
        if score < 0.0:
            distance = _as_float(row.get("distance"), default=1.0)
            score = max(0.0, 1.0 - distance)
        entry: dict[str, Any] = {
            "note": {
                "id": note_id,
                "title": str(row.get("title") or ""),
                "path": source_path,
            },
            "score": max(0.0, float(score)),
            "source": "vector",
            "distance": _as_int(row.get("distance"), default=0, minimum=0),
            "reasoning": str(row.get("reasoning") or "Vector recall hit"),
        }
        content = row.get("content")
        if isinstance(content, str):
            entry["content"] = content
        section = row.get("section")
        if isinstance(section, str):
            entry["section"] = section
        out.append(entry)
    return out


def _hybrid_key(row: dict[str, Any], index: int) -> str:
    note = row.get("note")
    if isinstance(note, dict):
        note_id = str(note.get("id") or "").strip()
        if note_id:
            return f"id:{note_id}"
        note_path = str(note.get("path") or "").strip()
        if note_path:
            return f"path:{note_path}"
    fallback = f"{row.get('source', '')}|{row.get('title', '')}|{row.get('content', '')[:64]}"
    return f"row:{index}:{fallback}"


def _merge_reasoning(a: str, b: str) -> str:
    left = str(a or "").strip()
    right = str(b or "").strip()
    if left and right and left != right:
        return f"{left} | {right}"
    return left or right


def merge_hybrid_results(
    graph_results: Iterable[dict[str, Any]],
    vector_results: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge graph/vector rows by best score and mark overlaps as `hybrid`."""
    merged: dict[str, dict[str, Any]] = {}
    ordered_rows = [*graph_results, *vector_results]

    for idx, raw in enumerate(ordered_rows):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row["score"] = max(0.0, _as_float(row.get("score"), default=0.0))
        row["distance"] = _as_int(row.get("distance"), default=0, minimum=0)
        row["source"] = str(row.get("source") or "")
        row["reasoning"] = str(row.get("reasoning") or "")
        key = _hybrid_key(row, idx)
        current = merged.get(key)
        if current is None:
            merged[key] = row
            continue

        if row["score"] > current.get("score", 0.0):
            primary, secondary = row, current
        else:
            primary, secondary = current, row

        combined = dict(primary)
        for field in ("note", "content", "section", "title"):
            existing_value = combined.get(field)
            if existing_value in ("", None, {}, []):
                combined[field] = secondary.get(field)

        source_a = str(current.get("source") or "").strip()
        source_b = str(row.get("source") or "").strip()
        if source_a and source_b and source_a != source_b:
            combined["source"] = "hybrid"
        else:
            combined["source"] = source_a or source_b

        combined["score"] = max(
            _as_float(current.get("score"), default=0.0),
            _as_float(row.get("score"), default=0.0),
        )
        combined["distance"] = min(
            _as_int(current.get("distance"), default=0, minimum=0),
            _as_int(row.get("distance"), default=0, minimum=0),
        )
        combined["reasoning"] = _merge_reasoning(
            str(current.get("reasoning") or ""),
            str(row.get("reasoning") or ""),
        )
        merged[key] = combined

    return sorted(merged.values(), key=lambda item: float(item.get("score", 0.0)), reverse=True)


__all__ = [
    "link_graph_hits_to_hybrid_results",
    "link_graph_hits_to_search_results",
    "merge_hybrid_results",
    "neighbors_to_link_rows",
    "normalize_link_graph_direction",
    "vector_rows_to_hybrid_results",
]
