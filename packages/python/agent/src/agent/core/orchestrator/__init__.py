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

Dynamic Workflow Builder:
- builder.py: DynamicGraphBuilder core class
- compiled.py: CompiledGraph wrapper
- state_utils.py: State schema utilities with reducers

Usage:
    from agent.core.orchestrator import Orchestrator

    orchestrator = Orchestrator()
    response = await orchestrator.dispatch(user_query, history)

    # Dynamic Workflow Builder
    from agent.core.orchestrator import DynamicGraphBuilder
    from agent.core.orchestrator.state_utils import create_reducer_state_schema
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

# Dynamic Workflow Builder - imports from new modular structure
from agent.core.orchestrator.builder import (
    DynamicGraphBuilder,
    NodeMetadata,
)
from agent.core.orchestrator.compiled import CompiledGraph
from agent.core.orchestrator.state_utils import (
    create_reducer_state_schema,
    create_accumulating_list_schema,
    create_merge_dict_schema,
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
    # Dynamic Workflow Builder
    "DynamicGraphBuilder",
    "NodeMetadata",
    "CompiledGraph",
    "create_reducer_state_schema",
    "create_accumulating_list_schema",
    "create_merge_dict_schema",
]
