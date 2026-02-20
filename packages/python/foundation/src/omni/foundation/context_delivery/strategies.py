"""
context_delivery.strategies - Summary-only and full-content delivery strategies.

See docs/reference/skill-tool-context-practices.md for when to use each.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


def prepare_for_summary(content: str, max_chars: int = 8000) -> str:
    """Prepare content for summary-only scenario (e.g. git diff → commit message).

    Truncates to max_chars. Acceptable when the goal is to extract basic info
    and write a summary (e.g. conventional commit), not deep analysis.

    Args:
        content: Full content (e.g. git diff, log output).
        max_chars: Maximum characters to return; default 8000.

    Returns:
        Truncated content if longer than max_chars; otherwise unchanged.
    """
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n_(truncated for summary)_"


@dataclass
class ChunkedSession:
    """Session for chunked delivery of full content (no truncation).

    Use when the LLM needs to read full content across multiple calls.
    Each batch is complete; no mid-content truncation.
    """

    session_id: str
    batches: list[str]
    batch_size: int
    total_chars: int

    def get_batch(self, index: int) -> str | None:
        """Get batch at index (0-based). Returns None if out of range."""
        if 0 <= index < len(self.batches):
            return self.batches[index]
        return None

    @property
    def batch_count(self) -> int:
        """Number of batches."""
        return len(self.batches)

    def to_preview(self, max_batches: int = 5) -> dict:
        """Return preview for action=start: session_id, batch_count, first batch snippet."""
        return {
            "session_id": self.session_id,
            "batch_count": self.batch_count,
            "total_chars": self.total_chars,
            "batch_size": self.batch_size,
            "preview": self.batches[0][:500] + "..."
            if self.batches and len(self.batches[0]) > 500
            else (self.batches[0] if self.batches else ""),
        }


def create_chunked_session(
    content: str,
    batch_size: int = 28_000,
) -> ChunkedSession:
    """Create a chunked session for full-content delivery.

    Splits content into complete batches. No truncation within batches.
    Use when the LLM needs full content (e.g. researcher repomix analysis).

    Args:
        content: Full content to deliver.
        batch_size: Characters per batch; default 28000 (researcher shard limit).

    Returns:
        ChunkedSession with session_id and batches.
    """
    session_id = str(uuid.uuid4())[:8]
    batches: list[str] = []
    for i in range(0, len(content), batch_size):
        batches.append(content[i : i + batch_size])
    if not batches:
        batches = [""]
    return ChunkedSession(
        session_id=session_id,
        batches=batches,
        batch_size=batch_size,
        total_chars=len(content),
    )
