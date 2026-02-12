"""
pipeline_builder.py - Compile declarative pipeline config into graph definition.
"""

from __future__ import annotations

from typing import Any, Callable

from .engine import ExecutionTracer
from .pipeline_schema import PipelineConfig, Segment


class LangGraphPipelineBuilder:
    """Builds graph definitions from pipeline configurations."""

    def __init__(self, config: PipelineConfig, tracer: ExecutionTracer | None = None):
        self.config = config
        self.tracer = tracer

        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[tuple[str, str]] = []
        self.conditional_edges: list[tuple[str, Any, dict[str, str]]] = []
        self.entry_node: str | None = None
        self.exit_nodes: list[str] = []
        self.step_count = 0

    def add_step(self, server: str, tool: str, node_name: str | None = None) -> str:
        self.step_count += 1
        node_name = node_name or f"{server}_{tool}"

        if node_name in self.nodes:
            base = node_name
            i = 1
            while f"{base}_{i}" in self.nodes:
                i += 1
            node_name = f"{base}_{i}"

        self.nodes[node_name] = {
            "server": server,
            "tool": tool,
            "config": self.config.servers.get(server),
        }
        return node_name

    def add_edge(self, from_node: str, to_node: str) -> None:
        self.edges.append((from_node, to_node))

    def add_conditional_edge(
        self,
        from_node: str,
        condition: Any,
        destinations: dict[str, str],
    ) -> None:
        self.conditional_edges.append((from_node, condition, destinations))

    def build_sequential(self, pipeline: list[dict[str, Any] | str]) -> dict[int, str]:
        step_to_node: dict[int, str] = {}
        previous_exits: list[str] = []
        for i, step_def in enumerate(pipeline):
            seg = self._compile_step(step_def, parent_index=i)
            step_to_node[i] = seg.entry
            if i == 0 and self.entry_node is None:
                self.entry_node = seg.entry
            for prev_exit in previous_exits:
                self.add_edge(prev_exit, seg.entry)
            previous_exits = seg.exits
        if previous_exits:
            self.exit_nodes = previous_exits
        return step_to_node

    def _compile_step(self, step_def: dict[str, Any] | str, parent_index: int) -> Segment:
        if isinstance(step_def, str):
            server, tool = step_def.split(".", 1)
            node_name = self.add_step(server, tool)
            return Segment(entry=node_name, exits=[node_name])

        key, value = next(iter(step_def.items()))
        if key == "loop":
            return self._compile_loop_segment(value, parent_index)
        if key == "branch":
            return self._compile_branch_segment(value)
        if "." in key:
            server, tool = key.split(".", 1)
            node_name = self._build_step(server, tool, value or {})
            return Segment(entry=node_name, exits=[node_name])
        raise ValueError(f"Unknown step type: {key}")

    def _build_step(self, server: str, tool: str, config: dict[str, Any]) -> str:
        node_name = self.add_step(server, tool)
        self.nodes[node_name]["input_mapping"] = config.get("input", {})
        self.nodes[node_name]["output_mapping"] = config.get("output", [])
        return node_name

    def _build_loop(self, config: dict[str, Any], parent_index: int) -> str:
        seg = self._compile_loop_segment(config, parent_index)
        return seg.entry

    def _compile_loop_segment(self, config: dict[str, Any], parent_index: int) -> Segment:
        max_iterations = int(config.get("max_iterations", 3))
        steps = config.get("steps", [])
        loop_node = f"loop_{parent_index}"
        after_node = f"{loop_node}_after"
        self.nodes[loop_node] = {
            "type": "loop",
            "max_iterations": max_iterations,
        }
        self.nodes[after_node] = {"type": "noop"}

        child_builder = LangGraphPipelineBuilder(self.config, self.tracer)
        child_builder.nodes = self.nodes
        child_builder.edges = self.edges
        child_builder.conditional_edges = self.conditional_edges
        child_builder.step_count = self.step_count
        child_builder.build_sequential(steps)
        self.step_count = child_builder.step_count
        body_entry = child_builder.entry_node or after_node
        body_exits = child_builder.exit_nodes or [after_node]

        self.add_conditional_edge(
            loop_node,
            _create_loop_condition(loop_node, max_iterations),
            {"continue": body_entry, "exit": after_node},
        )
        for exit_node in body_exits:
            self.add_edge(exit_node, loop_node)
        return Segment(entry=loop_node, exits=[after_node])

    def _build_branch(self, config: dict[str, Any]) -> str:
        seg = self._compile_branch_segment(config)
        return seg.entry

    def _compile_branch_segment(self, config: dict[str, Any]) -> Segment:
        router = str(config.get("router", "default_router"))
        field = str(config.get("field", "route"))
        value_map = config.get("value_map", {})
        branches = config.get("branches", {})
        branch_node = f"branch_{router}"
        after_node = f"{branch_node}_after"
        self.nodes[branch_node] = {
            "type": "branch",
            "router": router,
            "field": field,
            "value_map": value_map,
        }
        self.nodes[after_node] = {"type": "noop"}

        destinations: dict[str, str] = {}
        branch_end_nodes: list[str] = []
        for branch_name, branch_steps in branches.items():
            child_builder = LangGraphPipelineBuilder(self.config, self.tracer)
            child_builder.nodes = self.nodes
            child_builder.edges = self.edges
            child_builder.conditional_edges = self.conditional_edges
            child_builder.step_count = self.step_count
            child_builder.build_sequential(branch_steps)
            self.step_count = child_builder.step_count
            entry = child_builder.entry_node or after_node
            exits = child_builder.exit_nodes or [after_node]
            destinations[branch_name] = entry
            branch_end_nodes.extend(exits)

        if not destinations:
            destinations["default"] = after_node
        default_branch = next(iter(destinations.keys()))
        self.add_conditional_edge(
            branch_node,
            _create_branch_condition(
                branch_node,
                field,
                value_map,
                destinations,
                default_branch,
            ),
            destinations,
        )
        for exit_node in branch_end_nodes:
            self.add_edge(exit_node, after_node)
        return Segment(entry=branch_node, exits=[after_node])

    def build(self) -> dict[str, Any]:
        self.nodes = {}
        self.edges = []
        self.conditional_edges = []
        self.entry_node = None
        self.exit_nodes = []

        self.build_sequential(self.config.pipeline)
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "conditional_edges": self.conditional_edges,
            "servers": self.config.servers,
            "parameters": self.config.parameters,
            "entry_node": self.entry_node,
            "exit_nodes": self.exit_nodes,
        }


def _create_loop_condition(
    node_name: str,
    max_iterations: int,
) -> Callable[[dict[str, Any]], str]:
    """Create a loop routing function based on per-node iteration count."""

    def condition(state: dict[str, Any]) -> str:
        loop_iters = state.get("__loop_iters__", {})
        current = int(loop_iters.get(node_name, 0))
        return "continue" if current <= max_iterations else "exit"

    return condition


def _create_branch_condition(
    node_name: str,
    field: str,
    value_map: dict[str, list[str]] | dict[str, Any],
    destinations: dict[str, str],
    default_branch: str,
) -> Callable[[dict[str, Any]], str]:
    """Create a branch routing function from state field and optional value maps."""
    valid_branches = set(destinations.keys())

    def condition(state: dict[str, Any]) -> str:
        candidate = state.get(field)
        if candidate is None:
            candidate = state.get(node_name)
        if candidate is None:
            candidate = state.get("routing_reason")
        if isinstance(candidate, str) and candidate in valid_branches:
            return candidate
        if isinstance(candidate, str) and isinstance(value_map, dict):
            for branch_name, values in value_map.items():
                if (
                    branch_name in valid_branches
                    and isinstance(values, list)
                    and candidate in values
                ):
                    return branch_name
        return default_branch

    return condition


__all__ = [
    "LangGraphPipelineBuilder",
    "_create_loop_condition",
    "_create_branch_condition",
]
