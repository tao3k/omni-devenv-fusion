"""
layer3_knowledge.py - Layer 3: Knowledge & Docs (The "Textbook").
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import structlog

from common.gitops import get_project_root
from common.mcp_core.reference_library import get_reference_path

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


class Layer3_Knowledge(ContextLayer):
    """Layer 3: Project Knowledge - The Textbook."""

    name = "knowledge"
    priority = 3

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        if budget < 500:
            return "", 0

        project_root = get_project_root()
        # SSOT: references.yaml for architecture docs directory
        docs_dir = project_root / get_reference_path("context.architecture_docs_dir")

        relevant_docs = []
        keywords = task.lower().split()

        if docs_dir.exists():
            for doc in docs_dir.glob("*.md"):
                # Very naive relevance check
                if any(k in doc.name.lower() for k in keywords if len(k) > 4):
                    try:
                        content = doc.read_text(encoding="utf-8")
                        truncated = _truncate_tokens(content, 500)  # Cap each doc
                        relevant_docs.append(f"<doc name='{doc.name}'>\n{truncated}\n</doc>")
                    except Exception as e:
                        logger.warning(f"Failed to read doc {doc.name}: {e}")

        if not relevant_docs:
            return "", 0

        content = (
            "\n<relevant_documentation>\n"
            + "\n".join(relevant_docs)
            + "\n</relevant_documentation>"
        )
        return content, _count_tokens(content)


__all__ = ["Layer3_Knowledge"]
