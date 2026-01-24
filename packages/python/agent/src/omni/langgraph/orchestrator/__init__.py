"""
omni/langgraph/orchestrator/__init__.py - Graph Orchestrator

Tools for building and dispatching LangGraph workflows:
- builder.py: DynamicGraphBuilder for runtime graph construction
- compiled.py: CompiledGraph wrapper with convenience methods
- dispatch.py: Graph dispatch integration

Usage:
    from omni.langgraph.orchestrator import DynamicGraphBuilder, dispatch_graph_mode

    # Build a graph
    builder = DynamicGraphBuilder(skill_runner)
    builder.add_skill_node("step1", "filesystem", "read_file")
    graph = builder.compile()

    # Dispatch using graph
    result = await dispatch_graph_mode(orchestrator, query, history, context)
"""

from omni.langgraph.orchestrator.builder import DynamicGraphBuilder, NodeMetadata
from omni.langgraph.orchestrator.compiled import CompiledGraph
from omni.langgraph.orchestrator.dispatch import dispatch_graph_mode

__all__ = [
    "CompiledGraph",
    "DynamicGraphBuilder",
    "NodeMetadata",
    "dispatch_graph_mode",
]
