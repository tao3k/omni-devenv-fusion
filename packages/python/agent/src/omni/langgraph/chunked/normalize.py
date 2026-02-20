"""
Generic chunk/shard normalization: split oversized, cap total, merge tiny.

Keeps each chunk under max_per_chunk so LLM/timeout stays bounded, and total
work under max_total. Consecutive small chunks are merged up to max_per_chunk.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from omni.foundation.config.logging import get_logger
from omni.langgraph.chunked.state import (
    ChunkConfig,
    DEFAULT_MAX_PER_CHUNK,
    DEFAULT_MAX_TOTAL,
    DEFAULT_MIN_TO_MERGE,
)

logger = get_logger("omni.langgraph.chunked")


def _default_size(item: dict[str, Any]) -> int:
    """Default: size = len(targets) or len(items) or 1."""
    targets = item.get("targets", item.get("items", []))
    if isinstance(targets, list):
        return max(1, len(targets))
    return 1


def _slice_item(item: dict[str, Any], start: int, end: int, part_label: str) -> dict[str, Any]:
    """Slice one item into a sub-item (targets or items key)."""
    key = "targets" if "targets" in item else "items"
    full = list(item.get(key, []))
    name = item.get("name", "Unknown")
    desc = item.get("description", "")
    part_name = f"{name} ({part_label})" if part_label else name
    return {"name": part_name, key: full[start:end], "description": desc}


def _merge_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple items into one (concat targets/items, join names)."""
    if not items:
        return {"name": "Merged", "targets": [], "description": ""}
    key = "targets" if "targets" in items[0] else "items"
    combined: list[Any] = []
    names: list[str] = []
    desc = ""
    for it in items:
        combined.extend(it.get(key, []))
        names.append(it.get("name", ""))
        desc = desc or it.get("description", "")
    name = " + ".join(n for n in names if n) if len(names) > 1 else (names[0] or "Merged")
    return {"name": name, key: combined, "description": desc or "Combined"}


def normalize_chunks(
    items: list[dict[str, Any]],
    config: ChunkConfig | None = None,
    *,
    get_size: Callable[[dict[str, Any]], int] = _default_size,
    slice_item: Callable[[dict[str, Any], int, int, str], dict[str, Any]] = _slice_item,
    merge_items: Callable[[list[dict[str, Any]]], dict[str, Any]] = _merge_items,
) -> list[dict[str, Any]]:
    """
    Enforce bounded chunks: split oversized, cap total, merge tiny.

    Steps:
    1. Split any item with size > max_per_chunk into multiple items.
    2. Cap total size at max_total (trim from end).
    3. Merge consecutive items with size <= min_to_merge into one, up to max_per_chunk.

    Args:
        items: List of chunk/shard dicts (e.g. {"name", "targets", "description"}).
        config: ChunkConfig; if None, uses defaults (max_per=5, max_total=30, min_merge=2).
        get_size: Function(item) -> size (default: len(targets) or len(items) or 1).
        slice_item: Function(item, start, end, part_label) -> new item for split.
        merge_items: Function(list of items) -> one merged item.

    Returns:
        Normalized list of items (same shape, bounded sizes).
    """
    if config is None:
        config = ChunkConfig(
            max_per_chunk=DEFAULT_MAX_PER_CHUNK,
            max_total=DEFAULT_MAX_TOTAL,
            min_to_merge=DEFAULT_MIN_TO_MERGE,
        )
    if not items:
        return items

    max_per = config.max_per_chunk
    max_total = config.max_total
    min_merge = config.min_to_merge

    # Step 1: Split oversized
    expanded: list[dict[str, Any]] = []
    for item in items:
        size = get_size(item)
        if size <= max_per:
            expanded.append(dict(item))
            continue
        # Slice into parts of size max_per
        key = "targets" if "targets" in item else "items"
        full = list(item.get(key, []))
        for i in range(0, len(full), max_per):
            end = min(i + max_per, len(full))
            part_label = str(i // max_per + 1) if len(full) > max_per else ""
            expanded.append(slice_item(item, i, end, part_label))

    # Step 2: Cap total
    total = 0
    capped: list[dict[str, Any]] = []
    for item in expanded:
        if total >= max_total:
            break
        size = get_size(item)
        budget = max_total - total
        if size <= budget:
            capped.append(item)
            total += size
        else:
            # Trim this item
            key = "targets" if "targets" in item else "items"
            full = list(item.get(key, []))
            take = full[:budget]
            if take or not capped:
                capped.append(
                    {
                        "name": item.get("name", "Unknown"),
                        key: take,
                        "description": item.get("description", ""),
                    }
                )
            total += len(take)

    # Step 3: Merge consecutive tiny
    merged: list[dict[str, Any]] = []
    acc: list[dict[str, Any]] = []

    for item in capped:
        size = get_size(item)
        if size <= min_merge and sum(get_size(x) for x in acc) + size <= max_per:
            acc.append(item)
        else:
            if acc:
                merged.append(merge_items(acc))
                acc = []
            if size <= min_merge:
                acc = [item]
            else:
                merged.append(item)
    if acc:
        merged.append(merge_items(acc))

    logger.debug(
        "chunked_normalize",
        original_count=len(items),
        normalized_count=len(merged),
        total_size=sum(get_size(m) for m in merged),
    )
    return merged
