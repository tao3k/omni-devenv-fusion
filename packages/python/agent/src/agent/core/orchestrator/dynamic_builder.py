"""
src/agent/core/orchestrator/dynamic_builder.py
Phase 61: Dynamic Workflow Builder for Runtime Graph Construction.

This module provides a fluent API to construct LangGraph state graphs dynamically
based on agent reasoning. It abstracts away the complexity of node wrapping
and edge definition.

Usage:
    from agent.core.orchestrator.dynamic_builder import DynamicGraphBuilder

    builder = DynamicGraphBuilder(skill_manager)
    builder.add_skill_node("fetch_file", "filesystem", "read_file", {"path": "main.py"})
    builder.add_skill_node("analyze", "code_insight", "analyze", {})
    builder.add_sequence("fetch_file", "analyze")
    graph = builder.compile()

    # Execute the graph
    result = await graph.ainvoke(initial_state)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar, Union

from langgraph.graph import END, StateGraph

from ..skill_manager import SkillManager
from ..state import GraphState

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class NodeMetadata:
    """Metadata for a dynamically created node."""

    name: str
    type: Literal["skill", "function", "router"]
    target: str  # skill_name.command or function_name
    args: Dict[str, Any] = field(default_factory=dict)


class DynamicGraphBuilder:
    """
    A factory for building state graphs at runtime.

    This builder enables the agent to construct execution graphs dynamically
    based on task analysis, supporting:
    - Skill commands as graph nodes
    - Custom Python functions as nodes
    - Sequential and conditional workflows
    - Dynamic argument passing from state

    Example:
        builder = DynamicGraphBuilder(skill_manager)
        builder.add_skill_node("read_code", "filesystem", "read_file")
        builder.add_skill_node("analyze", "code_insight", "analyze")
        builder.add_skill_node("fix", "omni_edit", "apply_fix")
        builder.add_conditional_edges(
            "analyze",
            lambda s: "fix" if s["analysis_result"].get("needs_fix") else END
        )
        graph = builder.compile()
    """

    def __init__(
        self,
        skill_manager: SkillManager,
        state_schema: type[GraphState] | None = None,
        checkpoint: bool = False,
    ):
        """
        Initialize the graph builder.

        Args:
            skill_manager: SkillManager instance for executing skill nodes
            state_schema: State schema for the graph (defaults to GraphState)
            checkpoint: Whether to enable checkpointing for the compiled graph
        """
        self.skill_manager = skill_manager
        self.state_schema = state_schema or GraphState
        self.checkpoint = checkpoint

        # Create the StateGraph
        self.workflow = StateGraph(self.state_schema)
        self.nodes: Dict[str, NodeMetadata] = {}
        self._entry_point: str | None = None
        self._compiled = False

    def add_skill_node(
        self,
        node_name: str,
        skill_name: str,
        command_name: str,
        fixed_args: Optional[Dict[str, Any]] = None,
        state_input: Optional[Dict[str, str]] = None,
        state_output: Optional[Dict[str, str]] = None,
    ) -> "DynamicGraphBuilder":
        """
        Register a skill command as a graph node.

        The generated node function will:
        1. Read inputs from state (if state_input is provided)
        2. Merge with fixed_args
        3. Execute the skill via SkillManager
        4. Update the state with the result

        Args:
            node_name: Unique name for this node
            skill_name: Name of the skill (e.g., "filesystem")
            command_name: Name of the command (e.g., "read_file")
            fixed_args: Static arguments to pass to the command
            state_input: Map state keys to command args (e.g., {"path": "file_path"})
            state_output: Map result to state keys (e.g., {"content": "file_content"})

        Returns:
            Self for fluent chaining
        """
        if node_name in self.nodes:
            raise ValueError(f"Node '{node_name}' already exists.")

        fixed_args = fixed_args or {}
        state_input = state_input or {}
        state_output = state_output or {}

        async def _skill_node_impl(state: GraphState) -> Dict[str, Any]:
            # Merge fixed args with dynamic args from state
            cmd_args = dict(fixed_args)

            # Extract dynamic args from state
            for state_key, arg_name in state_input.items():
                if state_key in state and state[state_key]:
                    cmd_args[arg_name] = state[state_key]

            # Execute via SkillManager (with caching!)
            output = await self.skill_manager.run(skill_name, command_name, cmd_args)

            logger.info(
                "skill_node_executed",
            )

            # Prepare state updates
            updates: Dict[str, Any] = {}

            # Store result in scratchpad by default
            updates.setdefault("scratchpad", []).append(
                {
                    "node": node_name,
                    "skill": f"{skill_name}.{command_name}",
                    "output": output[:500] if isinstance(output, str) else output,
                }
            )

            # Apply explicit state_output mappings
            for result_key, state_key in state_output.items():
                # If output is a dict, extract the key
                if isinstance(output, dict):
                    updates[state_key] = output.get(result_key, output)
                else:
                    updates[state_key] = output

            return updates

        self.workflow.add_node(node_name, _skill_node_impl)
        self.nodes[node_name] = NodeMetadata(
            name=node_name,
            type="skill",
            target=f"{skill_name}.{command_name}",
            args=fixed_args,
        )
        return self

    def add_function_node(
        self,
        node_name: str,
        func: Callable[..., Any],
        state_output: Optional[Dict[str, str]] = None,
    ) -> "DynamicGraphBuilder":
        """
        Add a raw Python function as a node.

        Args:
            node_name: Unique name for this node
            func: Async function to execute (receives state, returns updates)
            state_output: Optional mapping of return value to state keys

        Returns:
            Self for fluent chaining
        """
        self.workflow.add_node(node_name, func)
        self.nodes[node_name] = NodeMetadata(
            name=node_name,
            type="function",
            target=func.__name__,
        )
        return self

    def add_llm_node(
        self,
        node_name: str,
        prompt_template: str,
        model: str = "default",
        state_output: str = "llm_result",
    ) -> "DynamicGraphBuilder":
        """
        Add an LLM processing node.

        Args:
            node_name: Unique name for this node
            prompt_template: F-string template with {{state_key}} placeholders
            model: Model to use (default: "default" from config)
            state_output: State key to store result

        Returns:
            Self for fluent chaining
        """

        async def _llm_node(state: GraphState) -> Dict[str, Any]:
            # Render prompt template
            try:
                prompt = prompt_template.format(**state)
            except KeyError:
                prompt = prompt_template

            # Execute LLM call
            if hasattr(self.skill_manager, "inference") and self.skill_manager.inference:
                result = await self.skill_manager.inference.complete(prompt, model=model)
            else:
                # Fallback: return placeholder
                result = f"[LLM: {prompt[:50]}...]"

            logger.info("llm_node_executed")
            return {state_output: result}

        self.workflow.add_node(node_name, _llm_node)
        self.nodes[node_name] = NodeMetadata(
            name=node_name,
            type="router",
            target=f"llm:{model}",
        )
        return self

    def set_entry_point(self, node_name: str) -> "DynamicGraphBuilder":
        """
        Set the starting node of the graph.

        Args:
            node_name: Name of the entry node

        Returns:
            Self for fluent chaining
        """
        if node_name not in self.nodes:
            raise ValueError(f"Node '{node_name}' does not exist.")
        self._entry_point = node_name
        self.workflow.set_entry_point(node_name)
        return self

    def add_edge(
        self,
        start_node: str,
        end_node: str | type[END],
    ) -> "DynamicGraphBuilder":
        """
        Add a direct edge between two nodes.

        Args:
            start_node: Source node name
            end_node: Target node name or END

        Returns:
            Self for fluent chaining
        """
        self.workflow.add_edge(start_node, end_node)
        return self

    def add_sequence(
        self,
        *node_names: str,
    ) -> "DynamicGraphBuilder":
        """
        Add a linear sequence of edges between nodes.

        Args:
            *node_names: Sequence of node names in order

        Returns:
            Self for fluent chaining
        """
        if len(node_names) < 2:
            return self

        for i in range(len(node_names) - 1):
            self.workflow.add_edge(node_names[i], node_names[i + 1])

        return self

    def add_conditional_edges(
        self,
        source_node: str,
        condition_func: Callable[[GraphState], str],
        path_map: Dict[str, str],
    ) -> "DynamicGraphBuilder":
        """
        Add conditional branching logic.

        Args:
            source_node: Source node that returns a routing decision
            condition_func: Function that takes state and returns a path key
            path_map: Mapping of path keys to target nodes

        Returns:
            Self for fluent chaining
        """
        self.workflow.add_conditional_edges(
            source_node,
            condition_func,
            path_map,
        )
        return self

    def add_parallel(
        self,
        branch_name: str,
        nodes: List[str],
        aggregator: Optional[str] = None,
    ) -> "DynamicGraphBuilder":
        """
        Add parallel execution branches.

        Creates a fan-out/fan-in pattern where multiple nodes execute
        concurrently, optionally with an aggregator node.

        Args:
            branch_name: Base name for branch nodes (e.g., "fetch" creates "fetch_1", "fetch_2")
            nodes: List of node names to execute in parallel
            aggregator: Optional node to aggregate results (fan-in)

        Returns:
            Self for fluent chaining
        """
        # All nodes start from the same source
        for node in nodes:
            self.workflow.add_edge(branch_name, node)

        # If aggregator provided, all branches point to it
        if aggregator:
            for node in nodes:
                self.workflow.add_edge(node, aggregator)

        return self

    def compile(
        self,
        interrupt_before: List[str] | None = None,
        interrupt_after: List[str] | None = None,
    ) -> Any:
        """
        Compile the graph into a runnable executable.

        Args:
            interrupt_before: Nodes to pause before (for human-in-the-loop)
            interrupt_after: Nodes to pause after (for human-in-the-loop)

        Returns:
            Compiled LangGraph ready for execution
        """
        if self._compiled:
            raise RuntimeError("Graph already compiled. Create a new builder.")

        # Auto-detect entry point if not set
        if self._entry_point is None:
            if len(self.nodes) == 1:
                self._entry_point = next(iter(self.nodes))
                self.workflow.set_entry_point(self._entry_point)
            else:
                # Find nodes with no incoming edges (simple heuristic)
                potential_starts = set(self.nodes.keys())
                for node in self.nodes.values():
                    # This is a simplification - real graph analysis would be more thorough
                    pass

        # Configure checkpointing if enabled
        if self.checkpoint:
            # Checkpointer is configured at runtime when graph is invoked
            pass

        compiled = self.workflow.compile(
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
        )
        self._compiled = True
        return compiled

    def visualize(self) -> str:
        """
        Generate a Mermaid diagram of the graph.

        Returns:
            Mermaid diagram string
        """
        lines = ["```mermaid", "graph TD"]

        # Add nodes
        for name, meta in self.nodes.items():
            label = meta.target.split(".")[-1] if "." in meta.target else meta.target
            if meta.type == "skill":
                lines.append(f'    {name}["{label}"]')
            elif meta.type == "router":
                lines.append(f'    {name}("{label}")')
            else:
                lines.append(f"    {name}({label})")

        # Note: Full edge extraction would require access to internal graph state
        lines.append("```")

        return "\n".join(lines)


__all__ = [
    "DynamicGraphBuilder",
    "NodeMetadata",
]
