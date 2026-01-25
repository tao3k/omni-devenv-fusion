"""
omni.core.context - Cognitive Pipeline

Modular context providers for assembling LLM prompts.

Modules:
- base: Abstract base classes
- providers: Concrete context providers
- orchestrator: Context assembly engine

Usage:
    from omni.core.context import ContextOrchestrator, SystemPersonaProvider

    orchestrator = ContextOrchestrator([
        SystemPersonaProvider(role="Architect"),
    ])
"""

from .base import ContextProvider, ContextResult
from .orchestrator import (
    ContextOrchestrator,
    create_executor_orchestrator,
    create_planner_orchestrator,
)
from .providers import (
    ActiveSkillProvider,
    AvailableToolsProvider,
    EpisodicMemoryProvider,
    SystemPersonaProvider,
)

__all__ = [
    "ActiveSkillProvider",
    "AvailableToolsProvider",
    "ContextOrchestrator",
    "ContextProvider",
    "ContextResult",
    "EpisodicMemoryProvider",
    "SystemPersonaProvider",
    "create_executor_orchestrator",
    "create_planner_orchestrator",
]
