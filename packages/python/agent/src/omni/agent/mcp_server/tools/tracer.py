"""
tracer.py - Execution Tracing MCP Tools

Exposes UltraRAG-style execution tracing via MCP protocol.

Tools:
- run_agent_with_trace: Run agent with full execution tracing
- get_execution_trace: Retrieve historical trace details
- list_traces: List available traces
- search_traces: Search traces by criteria
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent

logger = logging.getLogger("omni.agent.mcp_server.tools.tracer")


def register_tracer_tools(app: Server) -> None:
    """Register tracing-related MCP tools.

    Args:
        app: MCP Server instance
    """

    @app.call_tool()
    async def run_agent_with_trace(arguments: dict) -> list[Any]:
        """Run the agent with full execution tracing (UltraRAG-style).

        Returns complete execution trajectory including thinking process,
        tool calls, and variable history.

        Args:
            query: User query to process
            thread_id: Optional thread/session ID
            enable_thinking: Capture LLM thinking process (default: True)

        Returns:
            JSON with result, thinking steps, and execution trace
        """
        try:
            query = arguments.get("query", "")
            thread_id = arguments.get("thread_id", f"trace_{id(arguments)}")
            enable_thinking = arguments.get("enable_thinking", True)

            if not query:
                return [TextContent(type="text", text="Error: 'query' parameter required")]

            from omni.langgraph.graph import OmniGraph
            from omni.tracer import ExecutionTracer, TracingCallbackHandler

            # Initialize graph with tracing
            graph = OmniGraph(enable_tracing=True)

            # Initialize tracer
            tracer = ExecutionTracer(
                trace_id=f"trace_{thread_id}",
                user_query=query,
                thread_id=thread_id,
            )
            tracer.start_trace()

            # Create callback handler
            handler = TracingCallbackHandler(tracer)

            # Build initial state
            from omni.langgraph.state import GraphState

            initial_state = GraphState(
                messages=[{"role": "user", "content": query}],
                context_ids=[],
                current_plan="",
                error_count=0,
                workflow_state={},
            )

            # Execute with callbacks
            result_content = ""
            success = False
            iterations = 0

            try:
                app_graph = graph.get_app()
                config = {"callbacks": [handler]}

                async for event in app_graph.graph.astream(
                    initial_state, config=config, thread_id=thread_id
                ):
                    for node_name, state_update in event.items():
                        iterations += 1
                        if node_name == "execute":
                            messages = state_update.get("messages", [])
                            if messages:
                                result_content = messages[-1].get("content", "")
                        if node_name == "reflect":
                            workflow = state_update.get("workflow_state", {})
                            if workflow.get("approved"):
                                success = True

            except Exception as e:
                logger.error(f"Graph execution failed: {e}")
                result_content = f"Error: {str(e)}"

            # Get the trace
            trace = tracer.end_trace(
                success=success, error_message=None if success else result_content
            )

            # Extract thinking steps
            thinking = []
            if enable_thinking:
                for step in trace.steps.values():
                    if step.reasoning_content:
                        thinking.append(
                            {
                                "step": step.name,
                                "type": step.step_type.value,
                                "reasoning": step.reasoning_content,
                            }
                        )

            # Extract execution steps
            steps = []
            for step in trace.steps.values():
                steps.append(
                    {
                        "name": step.name,
                        "type": step.step_type.value,
                        "status": step.status,
                        "duration_ms": step.duration_ms,
                    }
                )

            # Memory pool summary
            memory_summary = trace.memory_pool.summary()

            result = {
                "result": result_content,
                "success": success,
                "thinking": thinking,
                "steps": steps,
                "trace_summary": {
                    "trace_id": trace.trace_id,
                    "step_count": trace.step_count(),
                    "thinking_step_count": trace.thinking_step_count(),
                    "duration_ms": trace.duration_ms,
                },
                "memory_pool": memory_summary,
            }

            logger.info(
                f"[MCP] Traced execution completed",
                trace_id=trace.trace_id,
                steps=trace.step_count(),
            )

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            logger.error(f"run_agent_with_trace failed: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    @app.call_tool()
    async def get_execution_trace(arguments: dict) -> list[Any]:
        """Get details of a historical execution trace.

        Args:
            trace_id: The trace ID to retrieve
            include_memory: Include memory pool contents (default: False)
            include_steps: Include step details (default: True)

        Returns:
            Trace details as JSON
        """
        try:
            trace_id = arguments.get("trace_id", "")
            include_memory = arguments.get("include_memory", False)
            include_steps = arguments.get("include_steps", True)

            if not trace_id:
                return [TextContent(type="text", text="Error: 'trace_id' parameter required")]

            from omni.tracer import TraceStorage

            storage = TraceStorage()
            trace = storage.load(trace_id)

            if not trace:
                return [TextContent(type="text", text=f"Error: Trace '{trace_id}' not found")]

            result = {
                "trace_id": trace.trace_id,
                "user_query": trace.user_query,
                "thread_id": trace.thread_id,
                "start_time": trace.start_time.isoformat(),
                "end_time": trace.end_time.isoformat() if trace.end_time else None,
                "success": trace.success,
                "duration_ms": trace.duration_ms,
            }

            if include_steps:
                result["steps"] = [
                    {
                        "name": step.name,
                        "type": step.step_type.value,
                        "reasoning": step.reasoning_content,
                        "input": step.input_data,
                        "output": step.output_data,
                        "duration_ms": step.duration_ms,
                        "status": step.status,
                    }
                    for step in trace.steps.values()
                ]

            if include_memory:
                result["memory_pool"] = trace.memory_pool.to_dict()

            result["memory_summary"] = trace.memory_pool.summary()

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            logger.error(f"get_execution_trace failed: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    @app.call_tool()
    async def list_traces(arguments: dict) -> list[Any]:
        """List available execution traces.

        Args:
            limit: Maximum number of traces to return (default: 20)
            offset: Skip this many traces (default: 0)

        Returns:
            List of trace metadata
        """
        try:
            limit = arguments.get("limit", 20)
            offset = arguments.get("offset", 0)

            from omni.tracer import TraceStorage

            storage = TraceStorage()
            traces = storage.list_traces(limit=limit, offset=offset)

            result = {
                "count": len(traces),
                "traces": traces,
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            logger.error(f"list_traces failed: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    @app.call_tool()
    async def search_traces(arguments: dict) -> list[Any]:
        """Search execution traces by criteria.

        Args:
            query: Search in user_query and step names
            step_type: Filter by step type (e.g., "llm_start", "tool_end")
            min_duration_ms: Minimum duration in milliseconds
            max_duration_ms: Maximum duration in milliseconds
            success: Filter by success status
            limit: Maximum results (default: 20)

        Returns:
            Matching traces
        """
        try:
            query = arguments.get("query")
            step_type = arguments.get("step_type")
            min_duration_ms = arguments.get("min_duration_ms")
            max_duration_ms = arguments.get("max_duration_ms")
            success = arguments.get("success")
            limit = arguments.get("limit", 20)

            from omni.tracer import TraceStorage, StepType

            storage = TraceStorage()

            # Convert step_type string to enum
            step_type_enum = StepType(step_type) if step_type else None

            traces = storage.search(
                query=query,
                step_type=step_type_enum,
                min_duration_ms=min_duration_ms,
                max_duration_ms=max_duration_ms,
                success=success,
                limit=limit,
            )

            result = {
                "count": len(traces),
                "traces": [
                    {
                        "trace_id": t.trace_id,
                        "user_query": t.user_query,
                        "start_time": t.start_time.isoformat(),
                        "success": t.success,
                        "duration_ms": t.duration_ms,
                        "step_count": t.step_count(),
                        "thinking_steps": t.thinking_step_count(),
                    }
                    for t in traces
                ],
            }

            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        except Exception as e:
            logger.error(f"search_traces failed: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    @app.call_tool()
    async def delete_trace(arguments: dict) -> list[Any]:
        """Delete an execution trace.

        Args:
            trace_id: The trace ID to delete

        Returns:
            Success message
        """
        try:
            trace_id = arguments.get("trace_id", "")

            if not trace_id:
                return [TextContent(type="text", text="Error: 'trace_id' parameter required")]

            from omni.tracer import TraceStorage

            storage = TraceStorage()
            deleted = storage.delete(trace_id)

            if deleted:
                return [TextContent(type="text", text=f"Trace '{trace_id}' deleted successfully")]
            else:
                return [TextContent(type="text", text=f"Trace '{trace_id}' not found")]

        except Exception as e:
            logger.error(f"delete_trace failed: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    logger.info(
        "Tracer tools registered (run_agent_with_trace, get_execution_trace, list_traces, search_traces, delete_trace)"
    )


__all__ = ["register_tracer_tools"]
