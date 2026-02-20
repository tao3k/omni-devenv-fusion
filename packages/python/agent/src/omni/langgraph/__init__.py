"""Public LangGraph namespace with lazy exports for low startup overhead."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "CompiledGraph": (".orchestrator", "CompiledGraph"),
    "DynamicGraphBuilder": (".orchestrator", "DynamicGraphBuilder"),
    "GraphInput": (".graph", "GraphInput"),
    "GraphOutput": (".graph", "GraphOutput"),
    "GraphState": (".state", "GraphState"),
    "NodeMetadata": (".orchestrator", "NodeMetadata"),
    "OmniGraph": (".graph", "OmniGraph"),
    "StateCheckpointer": (".state", "StateCheckpointer"),
    "VisualFormat": (".visualize", "VisualFormat"),
    "build_execution_levels": (".parallel", "build_execution_levels"),
    "create_initial_state": (".state", "create_initial_state"),
    "dispatch_graph_mode": (".orchestrator", "dispatch_graph_mode"),
    "execute_node": (".graph", "execute_node"),
    "get_checkpointer": (".state", "get_checkpointer"),
    "get_graph": (".graph", "get_graph"),
    "list_workflows": (".visualize", "list_workflows"),
    "merge_state": (".state", "merge_state"),
    "plan_node": (".graph", "plan_node"),
    "reflect_node": (".graph", "reflect_node"),
    "register_workflow": (".visualize", "register_workflow"),
    "reset_graph": (".graph", "reset_graph"),
    "run_parallel_levels": (".parallel", "run_parallel_levels"),
    "visualize_workflow": (".visualize", "visualize_workflow"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name, package=__name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
