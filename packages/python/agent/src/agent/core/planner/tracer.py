"""
Phase 61: Cognitive Scaffolding - Structured Tracing

Observability for Plan-and-Execute pattern.
遵循 ODF-EP 标准:
- Type hints required
- Structured logging
- Async-first ready
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Get current UTC time with timezone awareness."""
    return datetime.now(timezone.utc)


class TraceEvent:
    """A single trace event for observability."""

    def __init__(
        self,
        event_type: str,
        trace_id: str,
        span_id: str,
        parent_id: str | None,
        data: dict[str, Any],
    ) -> None:
        """Initialize a trace event.

        Args:
            event_type: Type of event (e.g., "task_start", "tool_call").
            trace_id: Unique trace identifier.
            span_id: Unique span identifier.
            parent_id: Parent span ID for nesting.
            data: Event data payload.
        """
        self.event_type = event_type
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_id = parent_id
        self.data = data
        self.timestamp = _utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict())


class Tracer:
    """Structured tracer for Plan-and-Execute observability.

    The Tracer creates a trace tree for each plan execution:
    - Plan Start → Task Start → Tool Calls → Task End → Plan End

    Attributes:
        enabled: Whether tracing is enabled.
        trace_id: Current trace identifier.
    """

    def __init__(self, enabled: bool = True) -> None:
        """Initialize the tracer.

        Args:
            enabled: Whether to enable tracing.
        """
        self.enabled = enabled
        self.trace_id: str | None = None
        self._spans: list[TraceEvent] = []
        self._current_span_id: str | None = None

    def start_trace(self, plan_id: str, goal: str) -> str:
        """Start a new trace for a plan.

        Args:
            plan_id: The plan identifier.
            goal: The user goal.

        Returns:
            Trace ID for this execution.
        """
        if not self.enabled:
            return ""

        self.trace_id = f"trace_{uuid.uuid4().hex[:8]}"
        self._spans = []
        self._current_span_id = self.trace_id

        event = TraceEvent(
            event_type="plan_start",
            trace_id=self.trace_id,
            span_id=self.trace_id,
            parent_id=None,
            data={"plan_id": plan_id, "goal": goal},
        )
        self._spans.append(event)
        logger.info(f"[TRACE] Started trace {self.trace_id} for plan {plan_id}")

        return self.trace_id

    def end_trace(self, status: str) -> None:
        """End the current trace.

        Args:
            status: Final status of the trace.
        """
        if not self.enabled or not self.trace_id:
            return

        event = TraceEvent(
            event_type="plan_end",
            trace_id=self.trace_id,
            span_id=f"end_{uuid.uuid4().hex[:8]}",
            parent_id=self._current_span_id,
            data={"status": status, "total_spans": len(self._spans)},
        )
        self._spans.append(event)
        logger.info(f"[TRACE] Ended trace {self.trace_id} with status: {status}")

    def start_task(self, task_id: str, task_description: str) -> str | None:
        """Start tracing a task.

        Args:
            task_id: The task identifier.
            task_description: Description of the task.

        Returns:
            Span ID for this task.
        """
        if not self.enabled or not self.trace_id:
            return None

        span_id = f"task_{uuid.uuid4().hex[:8]}"
        parent_id = self._current_span_id

        event = TraceEvent(
            event_type="task_start",
            trace_id=self.trace_id,
            span_id=span_id,
            parent_id=parent_id,
            data={"task_id": task_id, "description": task_description},
        )
        self._spans.append(event)
        self._current_span_id = span_id

        return span_id

    def end_task(
        self,
        task_id: str,
        status: str,
        result: str | None = None,
    ) -> None:
        """End tracing a task.

        Args:
            task_id: The task identifier.
            status: Final status (completed, failed).
            result: Optional result output.
        """
        if not self.enabled or not self.trace_id:
            return

        span_id = f"task_end_{uuid.uuid4().hex[:8]}"

        event = TraceEvent(
            event_type="task_end",
            trace_id=self.trace_id,
            span_id=span_id,
            parent_id=self._current_span_id,
            data={"task_id": task_id, "status": status, "result": result},
        )
        self._spans.append(event)

    def log_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: str,
    ) -> None:
        """Log a tool call.

        Args:
            tool_name: Name of the tool.
            arguments: Tool arguments.
            result: Tool execution result.
        """
        if not self.enabled or not self.trace_id:
            return

        span_id = f"tool_{uuid.uuid4().hex[:8]}"

        event = TraceEvent(
            event_type="tool_call",
            trace_id=self.trace_id,
            span_id=span_id,
            parent_id=self._current_span_id,
            data={
                "tool": tool_name,
                "arguments": arguments,
                "result": result,
            },
        )
        self._spans.append(event)

    def log_review(self, task_id: str, review_status: str, reflection: str) -> None:
        """Log a review event.

        Args:
            task_id: The reviewed task ID.
            review_status: Review decision.
            reflection: Review reflection text.
        """
        if not self.enabled or not self.trace_id:
            return

        span_id = f"review_{uuid.uuid4().hex[:8]}"

        event = TraceEvent(
            event_type="review",
            trace_id=self.trace_id,
            span_id=span_id,
            parent_id=self._current_span_id,
            data={
                "task_id": task_id,
                "status": review_status,
                "reflection": reflection,
            },
        )
        self._spans.append(event)

    def get_spans(self) -> list[dict[str, Any]]:
        """Get all recorded spans.

        Returns:
            List of span dictionaries.
        """
        return [span.to_dict() for span in self._spans]

    def get_span_tree(self) -> dict[str, Any]:
        """Get spans as a tree structure.

        Returns:
            Tree representation of spans.
        """
        spans_by_id = {s.span_id: s.to_dict() for s in self._spans}
        roots = []

        for span in self._spans:
            if span.parent_id is None:
                roots.append(span.span_id)
            else:
                parent = spans_by_id.get(span.parent_id)
                if parent:
                    if "children" not in parent:
                        parent["children"] = []
                    parent["children"].append(span.span_id)

        return {
            "trace_id": self.trace_id,
            "roots": roots,
            "spans": spans_by_id,
        }

    def export_json(self) -> str:
        """Export all traces as JSON.

        Returns:
            JSON string of all spans.
        """
        return json.dumps(self.get_spans(), indent=2)


# =============================================================================
# Tracer Integration Helpers
# =============================================================================

class TracedExecutor:
    """Wrapper for executor with tracing."""

    def __init__(
        self,
        executor: Any,
        tracer: Tracer | None = None,
    ) -> None:
        """Initialize traced executor.

        Args:
            executor: The executor to wrap.
            tracer: Optional tracer instance.
        """
        self.executor = executor
        self.tracer = tracer or Tracer()

    async def execute_plan(self, plan: Any) -> tuple[Any, list[Any]]:
        """Execute plan with tracing."""
        self.tracer.start_trace(plan.id, plan.goal)

        try:
            result_plan, episodes = await self.executor.execute_plan(plan)
            self.tracer.end_trace("completed")
            return result_plan, episodes
        except Exception as e:
            self.tracer.end_trace(f"error: {e}")
            raise


# =============================================================================
# Polyfactory for Testing
# =============================================================================

def create_tracer(enabled: bool = True) -> Tracer:
    """Factory function to create a Tracer.

    Args:
        enabled: Whether tracing is enabled.

    Returns:
        Configured Tracer instance.
    """
    return Tracer(enabled=enabled)
