"""
node_factory.py - Pluggable node factory for pipeline-generated LangGraph nodes.

Provides a ToolInvoker protocol so pipeline nodes can execute tools via:
- built-in no-op execution (default)
- mapped Python callables (tests/local adapters)
- future MCP adapters
"""

from __future__ import annotations

import inspect
from typing import Any, Protocol

from .engine import ExecutionTracer
from .interfaces import StepType


class ToolInvoker(Protocol):
    """Protocol for executing a tool call from a compiled pipeline node."""

    async def invoke(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any] | Any:
        """Execute a tool and return a serializable result."""


class NoOpToolInvoker:
    """Default invoker used when no backend is configured."""

    async def invoke(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "status": "completed",
            "server": server,
            "tool": tool,
            "input": payload,
        }


class MappingToolInvoker:
    """Invoker backed by a mapping of `server.tool` -> callable."""

    def __init__(self, mapping: dict[str, Any]):
        self._mapping = mapping

    async def invoke(
        self,
        server: str,
        tool: str,
        payload: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any] | Any:
        key = f"{server}.{tool}"
        fn = self._mapping.get(key)
        if fn is None:
            return {
                "status": "not_implemented",
                "server": server,
                "tool": tool,
                "input": payload,
            }
        if inspect.iscoroutinefunction(fn):
            return await fn(payload, state)
        return fn(payload, state)


def create_pipeline_node(
    node_name: str,
    node_config: dict[str, Any],
    tool_invoker: ToolInvoker | None = None,
    tracer: ExecutionTracer | None = None,
) -> Any:
    """Create a LangGraph node function with pluggable tool invocation."""
    invoker = tool_invoker or NoOpToolInvoker()

    async def node_function(state: dict[str, Any]) -> dict[str, Any]:
        node_type = node_config.get("type")
        if node_type == "noop":
            return dict(state)
        if node_type in {"loop_control", "loop"}:
            new_state = dict(state)
            loop_iters = dict(new_state.get("__loop_iters__", {}))
            loop_iters[node_name] = int(loop_iters.get(node_name, 0)) + 1
            new_state["__loop_iters__"] = loop_iters
            return new_state
        if node_type in {"router", "branch"}:
            return dict(state)

        server = node_config["server"]
        tool = node_config["tool"]
        input_mapping = node_config.get("input_mapping", {})
        output_mapping = node_config.get("output_mapping", [])

        payload: dict[str, Any] = {}
        for param_key, mapping_key in input_mapping.items():
            if isinstance(mapping_key, str) and mapping_key.startswith("$"):
                payload[param_key] = state.get(mapping_key[1:])
            else:
                payload[param_key] = state.get(mapping_key)

        step_id = None
        if tracer:
            step_id = tracer.start_step(
                name=f"{server}.{tool}",
                step_type=StepType.TOOL_START,
                input_data={"server": server, "tool": tool, "payload": payload},
            )

        result = await invoker.invoke(server=server, tool=tool, payload=payload, state=state)
        new_state = dict(state)

        if isinstance(output_mapping, dict):
            for output_key, result_key in output_mapping.items():
                if isinstance(result, dict):
                    new_state[output_key] = result.get(result_key)
        elif isinstance(output_mapping, list):
            for output_key in output_mapping:
                if isinstance(result, dict):
                    new_state[output_key] = result.get(output_key)

        if tracer and step_id:
            tracer.end_step(step_id, output_data={"result": result})

        return new_state

    return node_function


__all__ = [
    "ToolInvoker",
    "NoOpToolInvoker",
    "MappingToolInvoker",
    "create_pipeline_node",
]
