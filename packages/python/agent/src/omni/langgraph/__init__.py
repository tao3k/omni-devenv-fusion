"""
omni/langgraph/__init__.py - LangGraph Cognitive Graph System

LangGraph-based cognitive state machine for Omni Agent.
Provides plan -> execute -> reflect workflow with checkpoint persistence.

Modules:
    - graph.py: OmniGraph cognitive state machine
    - state.py: GraphState TypedDict and StateCheckpointer
    - orchestrator/: Dynamic graph building and dispatch
    - skills/: Graph-based skill implementations

Usage:
    from omni.langgraph.graph import OmniGraph, get_graph
    from omni.langgraph.orchestrator import DynamicGraphBuilder

    # Create a simple graph
    graph = get_graph()
    result = await graph.run(user_query="Fix bug", thread_id="session-123")
"""

from omni.langgraph.graph import (
    GraphInput,
    GraphOutput,
    OmniGraph,
    execute_node,
    get_graph,
    plan_node,
    reflect_node,
    reset_graph,
)
from omni.langgraph.orchestrator import (
    CompiledGraph,
    DynamicGraphBuilder,
    NodeMetadata,
    dispatch_graph_mode,
)
from omni.langgraph.state import (
    GraphState,
    StateCheckpointer,
    create_initial_state,
    get_checkpointer,
    merge_state,
)

__all__ = [
    # Graph
    "OmniGraph",
    "get_graph",
    "reset_graph",
    "plan_node",
    "execute_node",
    "reflect_node",
    "GraphInput",
    "GraphOutput",
    # State
    "GraphState",
    "StateCheckpointer",
    "get_checkpointer",
    "create_initial_state",
    "merge_state",
    # Orchestrator
    "DynamicGraphBuilder",
    "NodeMetadata",
    "CompiledGraph",
    "dispatch_graph_mode",
]
