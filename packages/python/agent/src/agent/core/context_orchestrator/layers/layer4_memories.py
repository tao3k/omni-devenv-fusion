"""
layer4_memories.py - Layer 4: Associative Memories (The "Experience").
"""

from __future__ import annotations

from typing import List, Tuple

import structlog

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


class Layer4_AssociativeMemories(ContextLayer):
    """Layer 4: Associative Memories - The Experience."""

    name = "memories"
    priority = 4

    async def assemble(
        self, task: str, history: List[dict[str, str]], budget: int
    ) -> Tuple[str, int]:
        if budget < 300:
            return "", 0

        try:
            # Async Vector Search!
            from agent.core.vector_store import get_vector_memory

            vm = get_vector_memory()

            # Construct query from task + last user message
            query = task
            if history:
                query += f" {history[-1].get('content', '')}"

            # Search specifically for past lessons/reflections
            results = await vm.search(query, n_results=3)

            if not results:
                return "", 0

            memories = []
            for res in results:
                # SearchResult is a dataclass with: content, metadata, distance, id
                score = getattr(res, "distance", 0.0)
                text = getattr(res, "content", "").strip()
                if text and score > 0.7:  # Only high relevance
                    memories.append(f"<memory score='{score:.2f}'>{text}</memory>")

            if not memories:
                return "", 0

            content = "\n<associative_memory>\n" + "\n".join(memories) + "\n</associative_memory>"
            return content, _count_tokens(content)

        except Exception as e:
            logger.warning(f"Layer 4 Memory search failed: {e}")
            return "", 0


__all__ = ["Layer4_AssociativeMemories"]
