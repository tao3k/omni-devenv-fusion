"""
engine.py - Core execution tracing engine

UltraRAG-style execution tracing engine that tracks step-by-step execution,
captures thinking content, and manages the memory pool.

Key classes:
- ExecutionTracer: Main tracer for tracking execution
- TracingSession: Context manager for tracing sessions

UltraRAG Memory Conventions:
- $variable: Read-only parameters (from parameter.yaml)
- variable: Global variables (from global_vars)
- memory_variable: History-tracked variables
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

from .async_utils import DispatchMode, dispatch_coroutine
from .callbacks import CallbackManager, TracingCallback
from .interfaces import ExecutionStep, ExecutionTrace, MemoryPool, StepType

logger = get_logger("omni.tracer.engine")


class ExecutionTracer:
    """Core execution tracer - UltraRAG memory_pool + stream_callback implementation.

    Provides fine-grained tracking of execution steps, thinking content,
    and variable history.

    UltraRAG Memory Conventions:
    - $variable: Read-only parameters (from parameter.yaml)
    - variable: Global variables (from global_vars)
    - memory_variable: History-tracked variables (accessible via get_memory)

    Usage:
        tracer = ExecutionTracer(trace_id="session-123")

        # Start a step
        step_id = tracer.start_step(
            name="plan",
            step_type=StepType.NODE_START,
            input_data={"query": "..."},
        )

        # Record thinking
        tracer.record_thinking(step_id, "Analyzing the query...")

        # Save with UltraRAG convention
        tracer.save_to_memory("memory_result", {...}, step_id)  # History tracked
        tracer.set_global("result", {...})                      # Global
        tracer.set_param("$query", "...")                      # Parameter

        # End the step
        tracer.end_step(step_id, output_data={...})
    """

    # Thread-safe context variables
    _current_step_id: ContextVar[str | None] = ContextVar("_current_step_id", default=None)
    _current_trace_id: ContextVar[str | None] = ContextVar("_current_trace_id", default=None)

    def __init__(
        self,
        trace_id: str | None = None,
        user_query: str | None = None,
        thread_id: str | None = None,
        enable_stream_callback: bool = False,
        callback_dispatch_mode: DispatchMode | str = DispatchMode.INLINE,
    ):
        """Initialize the tracer.

        Args:
            trace_id: Optional trace ID. Auto-generated if not provided.
            user_query: The original user query for context.
            thread_id: Session thread ID.
            enable_stream_callback: Enable real-time stream callbacks.
            callback_dispatch_mode:
                - inline: execute immediately when no loop is active.
                - background: fire-and-forget thread when no loop is active.
        """
        self.trace_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        self.user_query = user_query
        self.thread_id = thread_id
        self.enable_stream_callback = enable_stream_callback
        self.callback_dispatch_mode = DispatchMode(callback_dispatch_mode)

        # Execution trace
        self.trace = ExecutionTrace(
            trace_id=self.trace_id,
            user_query=user_query,
            thread_id=thread_id,
        )

        # Memory storage (UltraRAG convention)
        self._params: dict[str, Any] = {}  # $variable - read-only params
        self._globals: dict[str, Any] = {}  # variable - global vars
        self._memory: MemoryPool = MemoryPool()  # memory_* - history tracked

        # Current step tracking
        self._step_stack: list[str] = []  # For hierarchical tracking

        # Callbacks
        self.callbacks = CallbackManager()

        # Stream callbacks (real-time listeners)
        self._stream_listeners: list[Any] = []
        self._pending_tasks: set[asyncio.Task[Any]] = set()

        logger.debug(
            "tracer_initialized",
            trace_id=self.trace_id,
        )

    # =========================================================================
    # Context Variable Accessors (Thread-Safe)
    # =========================================================================

    @property
    def current_step_id(self) -> str | None:
        """Get the current active step ID (thread-safe)."""
        return ExecutionTracer._current_step_id.get()

    @property
    def current_trace_id(self) -> str | None:
        """Get the current trace ID (thread-safe)."""
        return ExecutionTracer._current_trace_id.get()

    # =========================================================================
    # Step Management
    # =========================================================================

    def start_step(
        self,
        name: str,
        step_type: StepType,
        input_data: dict[str, Any] | None = None,
        parent_step_id: str | None = None,
    ) -> str:
        """Start a new execution step.

        Args:
            name: Name of the step (node/tool name)
            step_type: Type of the step
            input_data: Input data for this step
            parent_step_id: Parent step ID for hierarchical tracing

        Returns:
            Step ID for this new step
        """
        step_id = f"step_{uuid.uuid4().hex[:12]}"

        # Determine parent ID
        parent_id = parent_step_id or self._step_stack[-1] if self._step_stack else None

        step = ExecutionStep(
            step_id=step_id,
            step_type=step_type,
            name=name,
            parent_id=parent_id,
            input_data=input_data,
            status="running",
        )

        # Store step
        self.trace.steps[step_id] = step

        # Track current step (thread-safe)
        self._current_step_id.set(step_id)
        self._step_stack.append(step_id)

        # Set root step if this is the first step
        if self.trace.root_step_id is None:
            self.trace.root_step_id = step_id

        # Emit callback
        dispatch_coroutine(
            self.callbacks.emit_step_start(self.trace, step),
            mode=self.callback_dispatch_mode,
            pending_tasks=self._pending_tasks,
        )

        # Stream callback (fire-and-forget)
        if self.enable_stream_callback and self._stream_listeners:
            dispatch_coroutine(
                self._emit_stream(
                    "step_start", {"step_id": step_id, "name": name, "step_type": step_type.value}
                ),
                mode=self.callback_dispatch_mode,
                pending_tasks=self._pending_tasks,
            )

        logger.debug(
            "step_started",
            step_id=step_id,
            step_type=step_type.value,
            name=name,
            parent_id=parent_id,
        )

        return step_id

    def end_step(
        self,
        step_id: str,
        output_data: dict[str, Any] | None = None,
        reasoning_content: str | None = None,
        status: str = "completed",
    ) -> None:
        """End an execution step.

        Args:
            step_id: Step ID to end
            output_data: Output data from this step
            reasoning_content: Final reasoning/thinking content
            status: Step status (completed, error)
        """
        step = self.trace.steps.get(step_id)
        if step is None:
            logger.warning("step_not_found", step_id=step_id)
            return

        # Update step
        step.output_data = output_data
        step.reasoning_content = reasoning_content or step.reasoning_content
        step.status = status

        # Calculate duration
        step.duration_ms = (datetime.now() - step.timestamp).total_seconds() * 1000

        # Pop from stack if this is the current step
        if self._step_stack and self._step_stack[-1] == step_id:
            self._step_stack.pop()

        # Update current step to parent (thread-safe)
        if self._step_stack:
            self._current_step_id.set(self._step_stack[-1])
        else:
            self._current_step_id.set(None)

        # Emit callback
        dispatch_coroutine(
            self.callbacks.emit_step_end(self.trace, step),
            mode=self.callback_dispatch_mode,
            pending_tasks=self._pending_tasks,
        )

        # Stream callback (fire-and-forget)
        if self.enable_stream_callback and self._stream_listeners:
            dispatch_coroutine(
                self._emit_stream(
                    "step_end",
                    {
                        "step_id": step_id,
                        "name": step.name,
                        "status": status,
                        "duration_ms": step.duration_ms,
                    },
                ),
                mode=self.callback_dispatch_mode,
                pending_tasks=self._pending_tasks,
            )

        logger.debug(
            "step_ended",
            step_id=step_id,
            step_type=step.step_type.value,
            duration_ms=step.duration_ms,
            status=status,
        )

    def record_thinking(self, step_id: str | None, content: str) -> None:
        """Record thinking content for a step.

        Accumulates thinking content as it's generated (real-time streaming).

        Args:
            step_id: Step ID to record thinking for
            content: Thinking content to append
        """
        if step_id is None:
            step_id = self.current_step_id

        if step_id is None:
            logger.warning("no_active_step_for_thinking")
            return

        step = self.trace.steps.get(step_id)
        if step is None:
            logger.warning("step_not_found_for_thinking", step_id=step_id)
            return

        # Accumulate thinking content
        if step.reasoning_content is None:
            step.reasoning_content = content
        else:
            step.reasoning_content += content

        # Emit callback
        dispatch_coroutine(
            self.callbacks.emit_thinking(self.trace, step, content),
            mode=self.callback_dispatch_mode,
            pending_tasks=self._pending_tasks,
        )

        # Stream callback (fire-and-forget)
        if self.enable_stream_callback and self._stream_listeners:
            dispatch_coroutine(
                self._emit_stream(
                    "thinking",
                    {
                        "step_id": step_id,
                        "content": content,
                    },
                ),
                mode=self.callback_dispatch_mode,
                pending_tasks=self._pending_tasks,
            )

        logger.debug(
            "thinking_recorded",
            step_id=step_id,
            content_length=len(content),
        )

    # =========================================================================
    # Memory Pool (UltraRAG Convention)
    # =========================================================================

    def save_to_memory(
        self,
        var_name: str,
        value: Any,
        source_step: str | None = None,
    ) -> None:
        """Save a variable to the memory pool with UltraRAG convention.

        Variables are classified by prefix:
        - memory_*: History-tracked (via MemoryPool)
        - $*: Parameters (read-only)
        - others: Global variables

        Args:
            var_name: Name of the variable (with or without prefix)
            value: Value to store
            source_step: Step ID that produced this value
        """
        if source_step is None:
            source_step = self.current_step_id or "unknown"

        # Classify by prefix
        if var_name.startswith("memory_"):
            # History-tracked variable
            self._memory.save(var_name, value, source_step)
        elif var_name.startswith("$"):
            # Parameter (read-only)
            self._params[var_name] = value
        else:
            # Global variable
            self._globals[var_name] = value

        # Also save to trace for serialization
        self.trace.memory_pool.save(var_name, value, source_step)

        # Stream callback (fire-and-forget)
        if self.enable_stream_callback and self._stream_listeners:
            dispatch_coroutine(
                self._emit_stream(
                    "memory_save",
                    {
                        "var_name": var_name,
                        "source_step": source_step,
                    },
                ),
                mode=self.callback_dispatch_mode,
                pending_tasks=self._pending_tasks,
            )
        dispatch_coroutine(
            self.callbacks.emit_memory_save(
                self.trace,
                var_name,
                value,
                source_step,
            ),
            mode=self.callback_dispatch_mode,
            pending_tasks=self._pending_tasks,
        )

        logger.debug(
            "memory_saved",
            var_name=var_name,
            var_type=self._get_var_type(var_name),
            source_step=source_step,
        )

    def record_memory(
        self,
        var_name: str,
        value: Any,
        *,
        step: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record memory value with optional metadata.

        This is a convenience wrapper for pipelines that track additional
        context about memory updates.
        """
        payload = value
        if metadata is not None:
            payload = {
                "content": value,
                "metadata": metadata,
            }
        self.save_to_memory(var_name=var_name, value=payload, source_step=step)

    def get_memory(self, var_name: str) -> Any | None:
        """Get the latest value of a variable.

        Supports all variable types:
        - memory_*: Returns latest from history
        - $*: Returns parameter value
        - others: Returns global value

        Args:
            var_name: Name of the variable

        Returns:
            Value or None
        """
        if var_name.startswith("memory_"):
            entry = self._memory.get_latest(var_name)
            return entry.value if entry else None
        elif var_name.startswith("$"):
            return self._params.get(var_name)
        else:
            return self._globals.get(var_name)

    def get_memory_history(self, var_name: str) -> list[tuple[datetime, Any, str]]:
        """Get the history of a memory variable.

        Args:
            var_name: Name of the variable (must start with memory_)

        Returns:
            List of (timestamp, value, source_step) tuples
        """
        return self._memory.get_history(var_name)

    def _get_var_type(self, var_name: str) -> str:
        """Get the type of a variable by its name."""
        if var_name.startswith("memory_"):
            return "memory"
        elif var_name.startswith("$"):
            return "parameter"
        else:
            return "global"

    # =========================================================================
    # Parameters (UltraRAG $variable convention)
    # =========================================================================

    def set_param(self, key: str, value: Any) -> None:
        """Set a read-only parameter ($variable).

        Args:
            key: Parameter name (with or without $ prefix)
            value: Parameter value
        """
        if not key.startswith("$"):
            key = f"${key}"
        self._params[key] = value

    def get_param(self, key: str) -> Any | None:
        """Get a parameter value.

        Args:
            key: Parameter name (with or without $ prefix)

        Returns:
            Parameter value or None
        """
        if not key.startswith("$"):
            key = f"${key}"
        return self._params.get(key)

    # =========================================================================
    # Global Variables
    # =========================================================================

    def set_global(self, key: str, value: Any) -> None:
        """Set a global variable.

        Args:
            key: Variable name
            value: Value to store
        """
        self._globals[key] = value

    def get_global(self, key: str) -> Any | None:
        """Get a global variable.

        Args:
            key: Variable name

        Returns:
            Value or None
        """
        return self._globals.get(key)

    # =========================================================================
    # Stream Callbacks (Real-time)
    # =========================================================================

    def add_stream_listener(self, listener: Any) -> None:
        """Add a real-time stream listener.

        Args:
            listener: Async callable (event: str, data: dict) -> None
        """
        self._stream_listeners.append(listener)

    def remove_stream_listener(self, listener: Any) -> None:
        """Remove a stream listener.

        Args:
            listener: Listener to remove
        """
        if listener in self._stream_listeners:
            self._stream_listeners.remove(listener)

    async def _emit_stream(self, event: str, data: dict) -> None:
        """Emit event to all stream listeners.

        Args:
            event: Event type
            data: Event data
        """
        for listener in self._stream_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, data)
                else:
                    listener(event, data)
            except Exception as e:
                logger.warning(
                    "stream_listener_error",
                    event=event,
                    error=str(e),
                )

    async def drain_pending_callbacks(self) -> None:
        """Wait for all in-loop scheduled callback tasks to complete."""
        while self._pending_tasks:
            tasks = tuple(self._pending_tasks)
            await asyncio.gather(*tasks, return_exceptions=True)

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_execution_path(self) -> list[ExecutionStep]:
        """Get the execution path as an ordered list of steps."""
        return self.trace.get_execution_path()

    def get_thinking_steps(self) -> list[ExecutionStep]:
        """Get all steps with reasoning content."""
        return self.trace.get_thinking_steps()

    def get_memory_summary(self) -> dict[str, Any]:
        """Get summary of all memory types."""
        return {
            "params": len(self._params),
            "globals": len(self._globals),
            "memory": self._memory.summary(),
        }

    def serialize_memory_pool(self) -> dict[str, Any]:
        """Serialize memory pool and related tracing context."""
        return {
            "trace_id": self.trace_id,
            "thread_id": self.thread_id,
            "timestamp": datetime.now().isoformat(),
            "memory_pool": self.trace.memory_pool.to_dict(),
            "summary": self.get_memory_summary(),
            "params": self._params,
            "globals": self._globals,
        }

    def write_memory_output(
        self,
        output_dir: str | Path | None = None,
        *,
        file_name: str | None = None,
    ) -> str:
        """Write serialized memory pool to disk as JSON."""
        base_dir = Path(output_dir) if output_dir is not None else Path.cwd() / ".traces"
        base_dir.mkdir(parents=True, exist_ok=True)
        out_name = file_name or f"{self.trace_id}_memory.json"
        out_path = base_dir / out_name
        payload = self.serialize_memory_pool()
        out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        logger.info("memory_output_written", path=str(out_path), trace_id=self.trace_id)
        return str(out_path)

    # =========================================================================
    # Trace Lifecycle
    # =========================================================================

    def start_trace(self) -> None:
        """Mark the trace as started."""
        self.trace.start_time = datetime.now()
        # Set thread-safe trace ID
        ExecutionTracer._current_trace_id.set(self.trace_id)
        logger.info("trace_started", trace_id=self.trace_id)

    def end_trace(self, success: bool = True, error_message: str | None = None) -> ExecutionTrace:
        """Mark the trace as completed.

        Args:
            success: Whether the execution was successful
            error_message: Error message if failed

        Returns:
            The completed execution trace
        """
        self.trace.end_time = datetime.now()
        self.trace.success = success
        self.trace.error_message = error_message

        # Clear thread-safe context
        ExecutionTracer._current_step_id.set(None)
        ExecutionTracer._current_trace_id.set(None)

        # Emit final callback
        dispatch_coroutine(
            self.callbacks.emit_trace_end(self.trace),
            mode=self.callback_dispatch_mode,
            pending_tasks=self._pending_tasks,
        )

        # Stream callback (fire-and-forget)
        if self.enable_stream_callback and self._stream_listeners:
            dispatch_coroutine(
                self._emit_stream(
                    "trace_end",
                    {
                        "trace_id": self.trace_id,
                        "success": success,
                        "step_count": self.trace.step_count(),
                    },
                ),
                mode=self.callback_dispatch_mode,
                pending_tasks=self._pending_tasks,
            )

        logger.info(
            "trace_completed",
            trace_id=self.trace_id,
            success=success,
            step_count=self.trace.step_count(),
            thinking_steps=self.trace.thinking_step_count(),
            duration_ms=self.trace.duration_ms,
        )

        return self.trace

    def add_callback(self, callback: TracingCallback) -> None:
        """Add a callback to the tracer.

        Args:
            callback: Callback instance implementing TracingCallback
        """
        self.callbacks.add_callback(callback)


# =========================================================================
# Context Manager
# =========================================================================


@asynccontextmanager
async def traced_session(
    trace_id: str | None = None,
    user_query: str | None = None,
    thread_id: str | None = None,
    enable_stream_callback: bool = False,
):
    """Context manager for tracing a complete session.

    Usage:
        async with traced_session("session-123", "Analyze this code") as tracer:
            # Your code here
            step_id = tracer.start_step("analyze", StepType.NODE_START, {...})
            ...
            tracer.end_step(step_id, {...})

        # Get the trace
        trace = tracer.end_trace()

    Args:
        trace_id: Optional trace ID
        user_query: The user query for context
        thread_id: Session thread ID
        enable_stream_callback: Enable real-time stream callbacks
    """
    tracer = ExecutionTracer(
        trace_id=trace_id,
        user_query=user_query,
        thread_id=thread_id,
        enable_stream_callback=enable_stream_callback,
    )
    tracer.start_trace()

    try:
        yield tracer
        tracer.end_trace(success=True)
    except Exception as e:
        tracer.end_trace(success=False, error_message=str(e))
        raise


__all__ = [
    "ExecutionTracer",
    "traced_session",
]
