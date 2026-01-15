"""
agent/core/orchestrator/
Orchestrator - The Central Switchboard.

Atomic module structure for easier maintenance:
- core.py: Main Orchestrator class
- types.py: Pydantic DTOs
- protocol.py: IOrchestrator protocol
- config.py: Configuration constants
- dispatch.py: Dispatch logic
- feedback.py: Feedback loop
- tools.py: Tool registry
- state.py: State persistence
- graph.py: LangGraph integration
- dynamic_builder.py:  Dynamic Workflow Builder

Usage:
    from agent.core.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    response = await orchestrator.dispatch(user_query, history)
"""

from agent.core.orchestrator.core import (
    Orchestrator,
    orchestrator_main,
)

from agent.core.orchestrator.protocol import IOrchestrator
from agent.core.orchestrator.types import (
    DispatchParams,
    DispatchResult,
    HiveContext,
)
from agent.core.orchestrator.config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_FEEDBACK_ENABLED,
)

from agent.core.orchestrator.dynamic_builder import (
    DynamicGraphBuilder,
    NodeMetadata,
)

__all__ = [
    # Core
    "Orchestrator",
    "orchestrator_main",
    # Protocol
    "IOrchestrator",
    # Types
    "DispatchParams",
    "DispatchResult",
    "HiveContext",
    # Config
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_FEEDBACK_ENABLED",
    #  Dynamic Workflow Builder
    "DynamicGraphBuilder",
    "NodeMetadata",
]
