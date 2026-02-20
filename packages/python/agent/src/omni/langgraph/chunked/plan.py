"""
Plan utilities for fan-out chunked workflows.

Reusable helpers for skills that maintain a master chunk plan and child sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def build_chunk_plan_from_queue(
    queue: list[dict[str, Any]],
    *,
    id_prefix: str = "c",
    id_key: str = "chunk_id",
    name_key: str = "name",
    description_key: str = "description",
    targets_key: str = "targets",
) -> list[dict[str, Any]]:
    """Build deterministic chunk plan rows from a queue definition."""
    plan: list[dict[str, Any]] = []
    for idx, item in enumerate(queue, start=1):
        if not isinstance(item, dict):
            continue
        plan.append(
            {
                id_key: f"{id_prefix}{idx}",
                name_key: item.get(name_key, f"Shard {idx}"),
                description_key: item.get(description_key, ""),
                targets_key: item.get(targets_key, []),
            }
        )
    return plan


def extract_chunk_plan(
    state: dict[str, Any],
    *,
    plan_key: str = "chunk_plan",
    id_key: str = "chunk_id",
) -> list[dict[str, Any]]:
    """Extract and validate chunk plan rows from state."""
    raw = state.get(plan_key)
    if not isinstance(raw, list):
        return []
    plan: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict) and isinstance(item.get(id_key), str):
            plan.append(item)
    return plan


def normalize_selected_ids(
    single_id: str = "",
    selected_ids: list[str] | None = None,
) -> list[str]:
    """Merge single and list selectors into one deduplicated ordered list."""
    normalized: list[str] = []
    for item_id in selected_ids or []:
        value = str(item_id).strip()
        if value and value not in normalized:
            normalized.append(value)
    one = str(single_id).strip()
    if one and one not in normalized:
        normalized.append(one)
    return normalized


def collect_chunk_progress(
    session_id: str,
    chunk_plan: list[dict[str, Any]],
    load_state: Callable[[str], dict[str, Any] | None],
    *,
    build_child_id: Callable[[str, str], str],
    id_key: str = "chunk_id",
    queue_key: str = "shards_queue",
    summaries_key: str = "shard_analyses",
) -> dict[str, Any]:
    """Collect pending/completed ids and ordered one-line summaries."""
    pending_chunk_ids: list[str] = []
    completed_chunk_ids: list[str] = []
    ordered_summaries: list[str] = []

    for item in chunk_plan:
        chunk_id = str(item.get(id_key, "")).strip()
        if not chunk_id:
            continue
        child_state = load_state(build_child_id(session_id, chunk_id))
        if not child_state:
            pending_chunk_ids.append(chunk_id)
            continue

        queue = child_state.get(queue_key, [])
        summaries = child_state.get(summaries_key, [])
        if queue:
            pending_chunk_ids.append(chunk_id)
            continue
        completed_chunk_ids.append(chunk_id)
        if summaries:
            ordered_summaries.extend(summaries[:1])

    return {
        "pending_chunk_ids": pending_chunk_ids,
        "completed_chunk_ids": completed_chunk_ids,
        "ordered_summaries": ordered_summaries,
    }


def build_child_work_items(
    session_id: str,
    chunk_plan: list[dict[str, Any]],
    base_state: dict[str, Any],
    *,
    build_child_id: Callable[[str, str], str],
    id_key: str = "chunk_id",
    queue_key: str = "shards_queue",
    current_key: str = "current_shard",
    summaries_key: str = "shard_analyses",
    parent_key: str = "parent_session_id",
    name_key: str = "name",
    targets_key: str = "targets",
    description_key: str = "description",
) -> list[tuple[str, dict[str, Any]]]:
    """Build (child_id, child_state) pairs from a master chunk plan."""
    work_items: list[tuple[str, dict[str, Any]]] = []
    for item in chunk_plan:
        chunk_id = str(item.get(id_key, "")).strip()
        if not chunk_id:
            continue
        child_state = {
            **base_state,
            queue_key: [
                {
                    name_key: item.get(name_key, chunk_id),
                    targets_key: item.get(targets_key, []),
                    description_key: item.get(description_key, ""),
                }
            ],
            current_key: None,
            summaries_key: [],
            id_key: chunk_id,
            parent_key: session_id,
        }
        work_items.append((build_child_id(session_id, chunk_id), child_state))
    return work_items


__all__ = [
    "build_child_work_items",
    "build_chunk_plan_from_queue",
    "collect_chunk_progress",
    "extract_chunk_plan",
    "normalize_selected_ids",
]
