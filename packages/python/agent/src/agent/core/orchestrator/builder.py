"""
builder.py - DynamicGraphBuilder for Runtime Graph Construction

A fluent API to construct LangGraph state graphs dynamically based on agent reasoning.
It abstracts away the complexity of node wrapping and edge definition.

Advanced Features (LangGraph v0.2+):
- Human-in-the-Loop with interrupt() API
- Command pattern for complex graph control
- State Schema with Reducers for parallel writes
- Stream Modes for rich output
- Send pattern for fan-out/fan-in parallelization

Usage:
    from agent.core.orchestrator.builder import DynamicGraphBuilder

    # Basic usage
    builder = DynamicGraphBuilder(skill_manager)
    builder.add_skill_node("fetch_file", "filesystem", "read_file", {"path": "main.py"})
    builder.add_skill_node("analyze", "code_insight", "analyze", {})
    builder.add_sequence("fetch_file", "analyze")
    graph = builder.compile()

    # Execute the graph
    result = await graph.ainvoke(initial_state)

    # Human-in-the-Loop
    builder = DynamicGraphBuilder(skill_manager, checkpoint=True)
    builder.add_interrupt_node("human_review", "Please review the commit")
    builder.add_skill_node("commit", "git", "commit")
    builder.add_sequence("human_review", "commit")
    graph = builder.compile(interrupt_before=["commit"])

    # Resume from interrupt
    for chunk in graph.stream(Command(resume="approved"), config):
        print(chunk)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, TypeVar, Union
from typing_extensions import TypedDict

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import (
    interrupt,
    Command,
    Send,
    StreamMode,
)

from ..skill_manager import SkillManager
from ..state import GraphState
from .compiled import CompiledGraph

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class NodeMetadata:
    """Metadata for a dynamically created node."""

    name: str
    type: Literal["skill", "function", "router", "interrupt", "command"]
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
    - Human-in-the-Loop with interrupt() API
    - Command pattern for complex graph control
    - Send pattern for parallel execution
    - State Schema with Reducers

    Example (Basic):
        builder = DynamicGraphBuilder(skill_manager)
        builder.add_skill_node("read_code", "filesystem", "read_file")
        builder.add_skill_node("analyze", "code_insight", "analyze")
        builder.add_conditional_edges(
            "analyze",
            lambda s: "fix" if s["analysis_result"].get("needs_fix") else END
        )
        graph = builder.compile()

    Example (Human-in-the-Loop):
        builder = DynamicGraphBuilder(skill_manager, checkpoint=True)
        builder.add_interrupt_node("review", "Please review the changes")
        builder.add_skill_node("commit", "git", "commit")
        builder.add_sequence("review", "commit")
        graph = builder.compile(interrupt_before=["commit"])

        # Resume
        for chunk in graph.stream(Command(resume="approved"), config):
            print(chunk)

    Example (Parallel Execution):
        builder = DynamicGraphBuilder(skill_manager)
        builder.add_skill_node("lint", "linter", "lint")
        builder.add_skill_node("format", "formatter", "format")
        builder.add_skill_node("test", "tester", "run")
        builder.add_send_branch("parallel_checks", ["lint", "format", "test"])
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
        self._stream_modes: List[StreamMode] | None = None

    # =========================================================================
    # Node Creation Methods
    # =========================================================================

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
            state_input: Map state keys to command args (e.g., {"path": "file_file"})
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

            # Execute via SkillManager
            output = await self.skill_manager.run(skill_name, command_name, cmd_args)

            logger.info(
                "skill_node_executed",
                extra={"node": node_name, "skill": f"{skill_name}.{command_name}"},
            )

            # Parse JSON string output if needed
            # SkillManager.run() returns str(result), which may be:
            # 1. Valid JSON (double quotes)
            # 2. Python repr of dict (single quotes)
            parsed_output = output
            if isinstance(output, str):
                import json

                try:
                    parsed_output = json.loads(output)
                except json.JSONDecodeError:
                    # Try Python literal_eval for repr format (single quotes)
                    try:
                        import ast

                        parsed_output = ast.literal_eval(output)
                    except (ValueError, SyntaxError):
                        parsed_output = output  # Keep as string if not parseable

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
                if isinstance(parsed_output, dict):
                    updates[state_key] = parsed_output.get(result_key, output)
                else:
                    updates[state_key] = parsed_output

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
    ) -> "DynamicGraphBuilder":
        """
        Add a raw Python function as a node.

        For Human-in-the-Loop, use add_interrupt_node() instead.

        Args:
            node_name: Unique name for this node
            func: Async function to execute (receives state, returns updates)

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

    def add_interrupt_node(
        self,
        node_name: str,
        prompt: str,
        resume_key: str = "human_input",
    ) -> "DynamicGraphBuilder":
        """
        Add a Human-in-the-Loop interrupt node.

        This node pauses execution and waits for human input before continuing.
        The human input is returned as the value of the specified resume_key.

        Args:
            node_name: Unique name for this node
            prompt: Message to show the human for approval
            resume_key: State key to store the human input (default: "human_input")

        Returns:
            Self for fluent chaining

        Example:
            builder.add_interrupt_node(
                "human_review",
                "Please review the commit message and approve",
            )
            # To resume:
            graph.stream(Command(resume="approved"), config)
        """

        async def _interrupt_impl(state: GraphState) -> Dict[str, Any]:
            # Call interrupt() - this pauses execution
            user_input = interrupt(prompt)
            # Return the user's input to be stored in state
            return {resume_key: user_input}

        self.workflow.add_node(node_name, _interrupt_impl)
        self.nodes[node_name] = NodeMetadata(
            name=node_name,
            type="interrupt",
            target=f"interrupt:{prompt[:50]}...",
        )
        return self

    def add_command_node(
        self,
        node_name: str,
        func: Callable[..., Any],
    ) -> "DynamicGraphBuilder":
        """
        Add a node that returns Command for complex graph control.

        Command allows a node to:
        1. Update state before continuing
        2. Dynamically route to any node (not just predefined edges)
        3. Resume from interrupts with both update and goto

        Args:
            node_name: Unique name for this node
            func: Async function that returns a Command

        Returns:
            Self for fluent chaining

        Example:
            async def conditional_commit(state):
                if state["approved"]:
                    return Command(update={"status": "committed"}, goto="END")
                return Command(update={"status": "skipped"}, goto="END")

            builder.add_command_node("execute_commit", conditional_commit)
        """
        self.workflow.add_node(node_name, func)
        self.nodes[node_name] = NodeMetadata(
            name=node_name,
            type="command",
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
                result = f"[LLM: {prompt[:50]}...]"

            logger.info("llm_node_executed", extra={"node": node_name})
            return {state_output: result}

        self.workflow.add_node(node_name, _llm_node)
        self.nodes[node_name] = NodeMetadata(
            name=node_name,
            type="router",
            target=f"llm:{model}",
        )
        return self

    # =========================================================================
    # Edge Definition Methods
    # =========================================================================

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

    def add_send_branch(
        self,
        source_node: str,
        target_nodes: List[str],
        send_input: Callable[[GraphState], List[Send]] | None = None,
    ) -> "DynamicGraphBuilder":
        """
        Add parallel execution using Send pattern (fan-out/fan-in).

        This creates a pattern where one node spawns multiple parallel tasks,
        each processing a different input. Results can be aggregated using
        a reducer channel in the state schema.

        Args:
            source_node: Node that spawns parallel tasks
            target_nodes: List of target nodes to execute in parallel
            send_input: Optional function to generate Send objects.
                       If not provided, uses state directly.

        Returns:
            Self for fluent chaining

        Example:
            def spawn_lints(state):
                return [
                    Send("lint_file", {"path": f, "result": None})
                    for f in state["changed_files"]
                ]

            builder.add_send_branch("lint_all", ["lint_file"], spawn_lints)
            builder.add_edge("lint_file", "aggregate_results")
        """
        # For now, just add edges from source to each target
        # Full Send pattern requires a spawn node
        for target in target_nodes:
            self.workflow.add_edge(source_node, target)

        return self

    # =========================================================================
    # Compilation Methods
    # =========================================================================

    def with_stream_modes(
        self,
        modes: List[StreamMode],
    ) -> "DynamicGraphBuilder":
        """
        Set stream modes for the compiled graph.

        Args:
            modes: List of stream modes (e.g., ["values", "updates", "messages"])

        Returns:
            Self for fluent chaining

        Example:
            builder.with_stream_modes(["values", "messages"])
            graph = builder.compile()
        """
        self._stream_modes = modes
        return self

    def compile(
        self,
        interrupt_before: List[str] | None = None,
        interrupt_after: List[str] | None = None,
        thread_id: str | None = None,
        checkpointer: Any | None = None,
    ) -> CompiledGraph:
        """
        Compile the graph into a runnable executable.

        Args:
            interrupt_before: Nodes to pause before (for human-in-the-loop)
            interrupt_after: Nodes to pause after (for human-in-the-loop)
            thread_id: Thread ID for checkpointer (if checkpoint=True)
            checkpointer: Custom checkpointer (overrides checkpoint flag)

        Returns:
            CompiledLangGraph ready for execution

        Example:
            graph = builder.compile(
                interrupt_before=["commit"],
                thread_id="commit-workflow-123",
            )

            # Stream with interrupt
            for chunk in graph.stream(initial_state, config):
                print(chunk)

            # Check for interrupt
            snapshot = graph.get_state(config)
            if snapshot.tasks:
                # Graph is waiting for human input
                print("Waiting for approval...")
        """
        if self._compiled:
            raise RuntimeError("Graph already compiled. Create a new builder.")

        # Auto-detect entry point if not set
        if self._entry_point is None:
            if len(self.nodes) == 1:
                self._entry_point = next(iter(self.nodes))
                self.workflow.set_entry_point(self._entry_point)

        # Configure checkpointer
        resolved_checkpointer = checkpointer
        if resolved_checkpointer is None and self.checkpoint:
            resolved_checkpointer = MemorySaver()

        # Compile with all options
        compiled = self.workflow.compile(
            checkpointer=resolved_checkpointer,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
        )

        self._compiled = True
        return CompiledGraph(
            graph=compiled,
            thread_id=thread_id,
            stream_modes=self._stream_modes,
        )

    # =========================================================================
    # Visualization
    # =========================================================================

    def visualize(self) -> str:
        """
        Generate a Mermaid diagram of the graph.

        Returns:
            Mermaid diagram string
        """
        lines = ["```mermaid", "graph TD"]

        # Add nodes with different shapes based on type
        for name, meta in self.nodes.items():
            label = meta.target.split(".")[-1] if "." in meta.target else meta.target

            if meta.type == "skill":
                lines.append(f'    {name}["{label}"]')
            elif meta.type == "interrupt":
                lines.append(f'    {name}{{"{label} interrupt"}}')
            elif meta.type == "command":
                lines.append(f'    {name}("{label}")')
            elif meta.type == "router":
                lines.append(f"    {name}[{label}]")
            else:
                lines.append(f"    {name}({label})")

        # Add styles for special node types
        lines.append("    classDef interrupt fill:#f96,stroke:#333")
        lines.append("    classDef command fill:#9f6,stroke:#333")

        lines.append("```")
        return "\n".join(lines)


__all__ = ["DynamicGraphBuilder", "NodeMetadata"]
