"""
base.py - Context Provider Abstract Layer

Defines the contract for all context providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ContextResult:
    """Result from a context provider."""

    content: str
    token_count: int
    name: str
    priority: int  # 0=highest (System), 100=lowest (Raw Data)


class ContextProvider(ABC):
    """Abstract base class for context providers."""

    @abstractmethod
    async def provide(self, state: dict[str, Any], budget: int) -> Optional[ContextResult]:
        """Generate context based on current state.

        Args:
            state: LangGraph state (contains history, active_skill, etc.)
            budget: Remaining tokens available for this layer.

        Returns:
            ContextResult with content and token count, or None if skipped.
        """
        ...


__all__ = ["ContextProvider", "ContextResult"]
