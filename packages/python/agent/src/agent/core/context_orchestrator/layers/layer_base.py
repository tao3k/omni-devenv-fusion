"""
layer_base.py - Base class for Context Layers.
"""

from __future__ import annotations

from typing import List, Tuple


class ContextLayer:
    """Base class for async context layers."""

    name: str = "base"
    priority: int = 100

    async def assemble(
        self,
        task: str,
        history: List[dict[str, str]],
        budget: int,
    ) -> Tuple[str, int]:
        """
        Asynchronously assemble this layer's context.

        Args:
            task: The current task description
            history: Conversation history
            budget: Remaining token budget

        Returns:
            Tuple of (content_string, tokens_used)
        """
        raise NotImplementedError


__all__ = ["ContextLayer"]
