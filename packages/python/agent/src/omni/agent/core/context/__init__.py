"""
Context Optimization Module (Token Diet)

Smart context management for long-running conversations.

Submodules:
- pruner: Intelligent message trimming strategies
- manager: Context lifecycle and state management
"""

from .pruner import ContextPruner
from .manager import ContextManager

__all__ = ["ContextPruner", "ContextManager"]
