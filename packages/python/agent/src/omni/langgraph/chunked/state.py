"""
Chunked workflow state and config for LangGraph long-content flows.

Shared state shape and limits so skills can plug into the same step runner
and normalization without redefining types.
"""

from __future__ import annotations

from typing import Any, TypedDict

# Default limits (tune per skill; these match researcher-style bounds)
DEFAULT_MAX_PER_CHUNK = 5
DEFAULT_MAX_TOTAL = 30
DEFAULT_MIN_TO_MERGE = 2


class ChunkConfig:
    """Config for normalize_chunks and chunked step execution."""

    __slots__ = ("max_per_chunk", "max_total", "min_to_merge")

    def __init__(
        self,
        max_per_chunk: int = DEFAULT_MAX_PER_CHUNK,
        max_total: int = DEFAULT_MAX_TOTAL,
        min_to_merge: int = DEFAULT_MIN_TO_MERGE,
    ):
        self.max_per_chunk = max(1, max_per_chunk)
        self.max_total = max(1, max_total)
        self.min_to_merge = max(0, min_to_merge)


class ChunkedWorkflowState(TypedDict, total=False):
    """Minimal state shape for chunked workflows (queue + accumulated + session)."""

    # Queue of items to process (each item is dict with at least "name", "targets"/"items", "description")
    queue: list[dict[str, Any]]
    # Results from each processed chunk (order preserved)
    accumulated: list[Any]
    # Optional session identifier (set by runner when action=start)
    session_id: str
    # Optional workflow type for persistence
    workflow_type: str
    # Optional error message
    error: str | None
    # Extra keys are allowed (harvest_dir, system_prompt, etc.)
    # Use total=False so skills can add their own fields
