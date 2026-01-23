"""
omni/core/orchestrator/compiled.py - CompiledGraph Wrapper

Wrapper around compiled LangGraph with convenient methods for:
- Simplified state retrieval
- Interrupt checking and resumption
- Stream mode support
- Configuration management

Usage:
    from omni.core.orchestrator.compiled import CompiledGraph

    graph = builder.compile()
    config = graph.get_config()

    # Check for interrupts
    if graph.has_interrupt():
        value = graph.get_interrupt_value()

    # Resume from interrupt
    command = graph.resume("approved")
    async for chunk in graph.stream(command):
        print(chunk)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from langgraph.types import Command, StreamMode, StateSnapshot

logger = logging.getLogger(__name__)


class CompiledGraph:
    """
    Wrapper around compiled LangGraph with convenient methods.

    This wrapper provides:
    - Simplified configuration and state management
    - Interrupt detection and resumption
    - Stream mode support
    - Helper methods for graph navigation

    Attributes:
        graph: The underlying compiled LangGraph
        thread_id: Default thread ID for this graph instance
        stream_modes: Default stream modes for streaming operations
    """

    def __init__(
        self,
        graph: Any,
        thread_id: str | None = None,
        stream_modes: List[StreamMode] | None = None,
    ):
        """
        Initialize the CompiledGraph wrapper.

        Args:
            graph: Compiled LangGraph instance
            thread_id: Default thread ID for state persistence
            stream_modes: Default stream modes (defaults to ["values"])
        """
        self.graph = graph
        self.thread_id = thread_id
        self.stream_modes = stream_modes or ["values"]

    # =========================================================================
    # Configuration
    # =========================================================================

    def get_config(self, thread_id: str | None = None) -> Dict[str, Any]:
        """
        Get the configuration for a thread.

        Args:
            thread_id: Thread ID to use (defaults to instance thread_id)

        Returns:
            Config dict for LangGraph operations

        Example:
            config = graph.get_config("my-workflow-123")
            state = graph.get_state(thread_id="my-workflow-123")
        """
        tid = thread_id or self.thread_id
        if tid:
            return {"configurable": {"thread_id": tid}}
        return {}

    # =========================================================================
    # State Management
    # =========================================================================

    def get_state(
        self,
        thread_id: str | None = None,
    ) -> StateSnapshot | None:
        """
        Get the current state of the graph.

        Args:
            thread_id: Thread ID (uses default if not provided)

        Returns:
            StateSnapshot if state exists, None otherwise

        Example:
            snapshot = graph.get_state()
            if snapshot:
                print(f"Current node: {snapshot.tasks[0].name if snapshot.tasks else 'None'}")
        """
        config = self.get_config(thread_id)
        if not config:
            return None
        try:
            return self.graph.get_state(config)
        except Exception as e:
            logger.warning(f"Failed to get state: {e}")
            return None

    def update_state(
        self,
        values: Dict[str, Any],
        thread_id: str | None = None,
        as_node: str | None = None,
    ) -> None:
        """
        Update the state of the graph (for interrupt-resume pattern).

        Args:
            values: State values to update
            thread_id: Thread ID (uses default if not provided)
            as_node: The node that produced the update

        Example:
            # After getting interrupt, update state before resuming
            graph.update_state({"status": "approved", "message": "my commit msg"})
            await graph.ainvoke(None, thread_id)
        """
        config = self.get_config(thread_id)
        if not config:
            return
        self.graph.update_state(config, values, as_node=as_node)

    def aget_state(
        self,
        thread_id: str | None = None,
    ) -> StateSnapshot | None:
        """
        Get the current state of the graph (async version).

        Args:
            thread_id: Thread ID (uses default if not provided)

        Returns:
            StateSnapshot if state exists, None otherwise
        """
        return self.get_state(thread_id)

    def aupdate_state(
        self,
        values: Dict[str, Any],
        thread_id: str | None = None,
        as_node: str | None = None,
    ) -> None:
        """
        Update the state of the graph (async version).

        Args:
            values: State values to update
            thread_id: Thread ID (uses default if not provided)
            as_node: The node that produced the update
        """
        self.update_state(values, thread_id, as_node)

    def get_next_node(self, thread_id: str | None = None) -> str | None:
        """
        Get the next node to be executed.

        Args:
            thread_id: Thread ID (uses default if not provided)

        Returns:
            Name of the next node, or None if graph is complete
        """
        snapshot = self.get_state(thread_id)
        if snapshot and snapshot.tasks:
            return snapshot.tasks[0].name if snapshot.tasks else None
        return None

    # =========================================================================
    # Interrupt Handling
    # =========================================================================

    def has_interrupt(self, thread_id: str | None = None) -> bool:
        """
        Check if the graph is waiting for human input.

        Args:
            thread_id: Thread ID (uses default if not provided)

        Returns:
            True if graph is paused at an interrupt node

        Example:
            if graph.has_interrupt():
                print("Waiting for human approval...")
        """
        snapshot = self.get_state(thread_id)
        return snapshot is not None and len(snapshot.tasks) > 0

    def get_interrupt_value(self, thread_id: str | None = None) -> Any:
        """
        Get the value passed to the last interrupt().

        Args:
            thread_id: Thread ID (uses default if not provided)

        Returns:
            The value passed to interrupt(), or None if no interrupt

        Example:
            if graph.has_interrupt():
                prompt = graph.get_interrupt_value()
                print(f"Interrupt prompt: {prompt}")
        """
        snapshot = self.get_state(thread_id)
        if snapshot and snapshot.interrupts:
            # The latest interrupt's value
            return snapshot.interrupts[-1].value
        return None

    # =========================================================================
    # Graph Invocation
    # =========================================================================

    async def invoke(
        self,
        input_state: Dict[str, Any],
        thread_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        Invoke the graph synchronously.

        Args:
            input_state: Initial state for the graph
            thread_id: Thread ID (uses default if not provided)

        Returns:
            Final state after graph execution
        """
        config = self.get_config(thread_id)
        return await self.graph.ainvoke(input_state, config=config)

    async def ainvoke(
        self,
        input_state: Dict[str, Any],
        thread_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        Invoke the graph asynchronously.

        This is an alias for invoke() for clarity in async contexts.

        Args:
            input_state: Initial state for the graph
            thread_id: Thread ID (uses default if not provided)

        Returns:
            Final state after graph execution
        """
        return await self.invoke(input_state, thread_id)

    # =========================================================================
    # Streaming
    # =========================================================================

    async def stream(
        self,
        input_state: Dict[str, Any] | Command,
        thread_id: str | None = None,
        stream_mode: StreamMode | None = None,
    ):
        """
        Stream output from the graph.

        Args:
            input_state: Initial state or Command for resuming
            thread_id: Thread ID (uses default if not provided)
            stream_mode: Override stream mode

        Yields:
            Chunks of graph output

        Example:
            async for chunk in graph.stream(initial_state):
                print(chunk)
        """
        config = self.get_config(thread_id)
        mode = stream_mode or self.stream_modes[0] if self.stream_modes else "values"
        async for chunk in self.graph.astream(input_state, config=config, stream_mode=mode):
            yield chunk

    async def astream(
        self,
        input_state: Dict[str, Any] | Command,
        thread_id: str | None = None,
    ):
        """
        Async iterator for streaming output.

        This is an alias for stream() for consistency.

        Args:
            input_state: Initial state or Command for resuming
            thread_id: Thread ID (uses default if not provided)

        Yields:
            Chunks of graph output
        """
        async for chunk in self.stream(input_state, thread_id):
            yield chunk

    # =========================================================================
    # Command Factory Methods
    # =========================================================================

    def resume(
        self,
        value: Any,
        thread_id: str | None = None,
        update: Dict[str, Any] | None = None,
    ) -> Command:
        """
        Create a Command to resume from an interrupt.

        Args:
            value: The value to pass to the interrupt() call
            thread_id: Thread ID (uses default if not provided)
            update: Optional state updates to apply

        Returns:
            Command object to pass to stream()

        Example:
            # Graph is waiting at interrupt node
            command = graph.resume("approved", update={"note": "LGTM"})
            async for chunk in graph.stream(command, thread_id="workflow-123"):
                print(chunk)
        """
        return Command(resume=value, update=update)

    def goto(
        self,
        node: str,
        thread_id: str | None = None,
        update: Dict[str, Any] | None = None,
    ) -> Command:
        """
        Create a Command to go to a specific node.

        Args:
            node: Target node name
            thread_id: Thread ID (uses default if not provided)
            update: Optional state updates to apply

        Returns:
            Command object to pass to stream()

        Example:
            command = graph.goto("review_node", update={"status": "approved"})
            async for chunk in graph.stream(command):
                print(chunk)
        """
        return Command(goto=node, update=update)


__all__ = ["CompiledGraph"]
