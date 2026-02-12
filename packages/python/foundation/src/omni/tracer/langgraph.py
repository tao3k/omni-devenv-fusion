"""
langgraph.py - LangGraph integration for the execution tracing system

Provides tracing callbacks for LangGraph execution.
Integrates ExecutionTracer with LangGraph's callback system.

Key classes:
- TracingCallbackHandler: Custom callback handler for LangGraph events
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

from omni.foundation.config.logging import get_logger

from .engine import ExecutionTracer
from .interfaces import StepType

logger = get_logger("omni.tracer.langgraph")


class TracingCallbackHandler:
    """Custom callback handler for LangGraph event streaming.

    Captures:
    - LLM calls (prompts, responses, streaming tokens)
    - Tool calls and results
    - Node execution
    - Retriever queries and results

    Usage:
        tracer = ExecutionTracer(trace_id="session-123")
        handler = TracingCallbackHandler(tracer)

        # Use with LangGraph config
        config = {"callbacks": [handler]}
        async for event in app.astream_events(initial_state, config=config):
            handler.handle_event(event)
    """

    def __init__(self, tracer: ExecutionTracer):
        """Initialize the handler.

        Args:
            tracer: The execution tracer to use
        """
        self.tracer = tracer
        self._step_mapping: dict[str, str] = {}

        logger.debug("tracing_callback_handler_initialized")

    def handle_event(self, event: dict[str, Any]) -> None:
        """Handle a LangGraph event.

        Args:
            event: LangGraph event dictionary
        """
        event_type = event.get("event")
        data = event.get("data", {})

        if event_type == "on_llm_start":
            self._on_llm_start(data)
        elif event_type == "on_llm_end":
            self._on_llm_end(data)
        elif event_type == "on_llm_stream":
            self._on_llm_stream(data)
        elif event_type == "on_tool_start":
            self._on_tool_start(data)
        elif event_type == "on_tool_end":
            self._on_tool_end(data)
        elif event_type == "on_retriever_start":
            self._on_retriever_start(data)
        elif event_type == "on_retriever_end":
            self._on_retriever_end(data)
        elif event_type == "on_chain_start":
            self._on_chain_start(data)
        elif event_type == "on_chain_end":
            self._on_chain_end(data)

    def _on_llm_start(self, data: dict[str, Any]) -> None:
        """Handle LLM start event."""
        serialized = data.get("serialized", {})
        prompts = data.get("prompts", [])

        step_id = self.tracer.start_step(
            name=serialized.get("name", "llm"),
            step_type=StepType.LLM_START,
            input_data={"prompts": prompts},
        )

        run_id = data.get("run_id", "")
        if run_id:
            self._step_mapping[run_id] = step_id

    def _on_llm_end(self, data: dict[str, Any]) -> None:
        """Handle LLM end event."""
        run_id = data.get("run_id", "")
        step_id = self._step_mapping.pop(run_id, None)

        if step_id:
            response = data.get("response", {})
            if isinstance(response, dict):
                response_content = response.get("content", "")
            else:
                response_content = str(response)

            self.tracer.end_step(
                step_id,
                output_data={"response": response_content},
                reasoning_content=response_content,
            )

    def _on_llm_stream(self, data: dict[str, Any]) -> None:
        """Handle LLM stream token event."""
        token = data.get("token", "")
        run_id = data.get("run_id", "")
        step_id = self._step_mapping.get(run_id)

        if step_id and token:
            self.tracer.record_thinking(step_id, token)

    def _on_tool_start(self, data: dict[str, Any]) -> None:
        """Handle tool start event."""
        serialized = data.get("serialized", {})
        input_str = data.get("input", "")

        step_id = self.tracer.start_step(
            name=serialized.get("name", "tool"),
            step_type=StepType.TOOL_START,
            input_data={"input": input_str},
        )

        run_id = data.get("run_id", "")
        if run_id:
            self._step_mapping[run_id] = step_id

    def _on_tool_end(self, data: dict[str, Any]) -> None:
        """Handle tool end event."""
        run_id = data.get("run_id", "")
        step_id = self._step_mapping.pop(run_id, None)

        if step_id:
            output = data.get("output", "")
            output_data = {"output": str(output)}
            self.tracer.end_step(step_id, output_data=output_data)

    def _on_retriever_start(self, data: dict[str, Any]) -> None:
        """Handle retriever start event."""
        query = data.get("query", "")

        step_id = self.tracer.start_step(
            name="retriever",
            step_type=StepType.RETRIEVAL,
            input_data={"query": query},
        )

    def _on_retriever_end(self, data: dict[str, Any]) -> None:
        """Handle retriever end event."""
        documents = data.get("documents", [])
        query = data.get("query", "")

        # Find the active retrieval step
        retrieval_steps = [
            sid
            for sid, step in self.tracer.trace.steps.items()
            if step.step_type == StepType.RETRIEVAL and step.output_data is None
        ]

        if retrieval_steps:
            last_retrieval = retrieval_steps[-1]
            docs_data = [
                {"content": doc.get("page_content", str(doc))[:200]} for doc in documents[:10]
            ]
            self.tracer.end_step(
                last_retrieval,
                output_data={"query": query, "documents": docs_data, "count": len(documents)},
            )

    def _on_chain_start(self, data: dict[str, Any]) -> None:
        """Handle start event."""
        serialized = data.get("serialized", {})
        name = serialized.get("name", "chain")

        # Determine step type
        step_type = StepType.NODE_START if "node" in name.lower() else StepType.CHAIN_START

        self.tracer.start_step(
            name=name,
            step_type=step_type,
            input_data=data.get("inputs"),
        )

    def _on_chain_end(self, data: dict[str, Any]) -> None:
        """Handle chain/node end event."""
        outputs = data.get("outputs", {})
        current_step = self.tracer.current_step_id

        if current_step:
            self.tracer.end_step(current_step, output_data=outputs)


# =============================================================================
# Helper Functions
# =============================================================================


def create_traced_app(
    graph: Any,
    tracer: ExecutionTracer,
) -> tuple[Any, TracingCallbackHandler]:
    """Create a traced version of a compiled LangGraph app.

    Args:
        graph: Compiled LangGraph application
        tracer: Execution tracer to use

    Returns:
        Tuple of (graph, handler) where handler should be used with config
    """
    handler = TracingCallbackHandler(tracer)
    return graph, handler


async def stream_with_trace(
    app: Any,
    initial_state: dict[str, Any],
    tracer: ExecutionTracer,
    thread_id: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream events from LangGraph while capturing trace.

    Args:
        app: Compiled LangGraph application
        initial_state: Initial state for the graph
        tracer: Execution tracer
        thread_id: Thread ID for checkpointer

    Yields:
        Events from the graph
    """
    # Start trace
    tracer.start_trace()

    # Create handler
    handler = TracingCallbackHandler(tracer)

    # Stream with callbacks
    config = {"callbacks": [handler]}

    try:
        async for event in app.astream_events(initial_state, config=config, thread_id=thread_id):
            # Process event through handler
            handler.handle_event(event)
            yield event
    finally:
        # End trace
        tracer.end_trace()


__all__ = [
    "TracingCallbackHandler",
    "create_traced_app",
    "stream_with_trace",
]
