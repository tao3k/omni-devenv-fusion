"""
Context Optimization Module (Token Diet)

Smart context management for long-running conversations.

Submodules:
- pruner: Intelligent message trimming strategies
- manager: Context lifecycle and state management
"""

from .manager import ContextManager
from .pruner import ContextPruner

__all__ = ["ContextManager", "ContextPruner"]
