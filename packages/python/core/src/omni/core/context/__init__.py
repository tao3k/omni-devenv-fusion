"""
omni.core.context - Cognitive Pipeline

Modular context providers for assembling LLM prompts.

Modules:
- base: Abstract base classes
- providers: Concrete context providers
- orchestrator: Context assembly engine
- prompts: Prompt injection utilities

Usage:
    from omni.core.context import ContextOrchestrator, SystemPersonaProvider
    from omni.core.prompts import inject_prompt, load_prompt

    orchestrator = ContextOrchestrator([
        SystemPersonaProvider(role="Architect"),
    ])

    # Inject prompt
    content = load_prompt("assets/prompts/custom.md", category="knowledge")
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

# Prompt injection utilities
from ..prompts import inject_prompt, load_prompt, merge_prompts, PROMPT_TAGS

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
    # Prompts
    "inject_prompt",
    "load_prompt",
    "merge_prompts",
    "PROMPT_TAGS",
]
