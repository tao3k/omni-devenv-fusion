"""
layer7_code.py - Layer 7: Raw Code (The "Ground Truth").
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

import structlog

from common.gitops import get_project_root

from .layer_base import ContextLayer

logger = structlog.get_logger(__name__)

_ENCODER = None


def _get_encoder():
    """Lazy import tiktoken encoder."""
    global _ENCODER
    if _ENCODER is None:
        import tiktoken

        _ENCODER = tiktoken.get_encoding("cl100k_base")
    return _ENCODER


def _count_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _get_encoder()
    return len(encoder.encode(text))


def _truncate_tokens(text: str, max_tokens: int) -> str:
    if not text:
        return ""
    encoder = _get_encoder()
    tokens = encoder.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoder.decode(tokens[:max_tokens])


class Layer7_RawCode(ContextLayer):
    """Layer 7: Raw Code - The Ground Truth."""

    name = "raw_code"
    priority = 7

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        if budget < 100:
            return "", 0

        try:
            # Read the most recently mentioned file in history
            if history:
                last_msg = history[-1].get("content", "")
                paths = re.findall(r"([a-zA-Z0-9_/.-]+\.py)", last_msg)

                if paths:
                    file_path = Path(paths[0])
                    if not file_path.is_absolute():
                        file_path = get_project_root() / file_path

                    if file_path.exists():
                        content = file_path.read_text(encoding="utf-8")
                        # Truncate to remaining budget
                        truncated = _truncate_tokens(content, budget)
                        rel_path = file_path.relative_to(get_project_root())

                        added_note = ""
                        if len(truncated) < len(content):
                            added_note = f"\n\n[... Content truncated, {len(content) - len(truncated)} chars hidden ...]"

                        return (
                            f"\n\n## Active File: {rel_path}\n```{truncated}```{added_note}",
                            _count_tokens(truncated),
                        )

            return "", 0

        except Exception as e:
            logger.warning(f"Raw code read failed: {e}")
            return "", 0


__all__ = ["Layer7_RawCode"]
