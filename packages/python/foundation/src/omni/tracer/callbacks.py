"""
callbacks.py - Callback management system for tracing

UltraRAG-style callback system for handling tracing events.
Provides a pluggable architecture for processing trace events.

Key classes:
- TracingCallback: Abstract base class for callbacks
- CallbackManager: Manages and dispatches callbacks
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from omni.foundation.config.logging import get_logger

if TYPE_CHECKING:
    from .engine import ExecutionTracer
    from .interfaces import ExecutionStep, ExecutionTrace

logger = get_logger("omni.tracer.callbacks")


class TracingCallback(ABC):
    """Abstract base class for tracing callbacks.

    Implement these methods to react to tracing events.

    All methods are async to support non-blocking operations.
    """

    @abstractmethod
    async def on_step_start(self, trace: ExecutionTrace, step: ExecutionStep) -> None:
        """Called when a step starts.

        Args:
            trace: The current execution trace
            step: The step that just started
        """
        pass

    @abstractmethod
    async def on_step_end(self, trace: ExecutionTrace, step: ExecutionStep) -> None:
        """Called when a step ends.

        Args:
            trace: The current execution trace
            step: The step that just ended
        """
        pass

    @abstractmethod
    async def on_thinking(self, trace: ExecutionTrace, step: ExecutionStep, content: str) -> None:
        """Called when thinking content is recorded.

        Args:
            trace: The current execution trace
            step: The step recording thinking
            content: The thinking content chunk
        """
        pass

    @abstractmethod
    async def on_retrieval(
        self,
        trace: ExecutionTrace,
        step: ExecutionStep,
        query: str,
        results: list[dict[str, Any]],
    ) -> None:
        """Called when a retrieval operation occurs.

        Args:
            trace: The current execution trace
            step: The retrieval step
            query: The search query
            results: Retrieved results
        """
        pass

    @abstractmethod
    async def on_memory_save(
        self,
        trace: ExecutionTrace,
        var_name: str,
        value: Any,
        source_step: str,
    ) -> None:
        """Called when data is saved to memory.

        Args:
            trace: The current execution trace
            var_name: Variable name
            value: Saved value
            source_step: Step that saved the memory
        """
        pass

    @abstractmethod
    async def on_trace_end(self, trace: ExecutionTrace) -> None:
        """Called when the trace completes.

        Args:
            trace: The completed execution trace
        """
        pass


class LoggingCallback(TracingCallback):
    """Callback that logs all tracing events for debugging.

    Useful for development and troubleshooting.
    """

    async def on_step_start(self, trace: ExecutionTrace, step: ExecutionStep) -> None:
        logger.debug(
            "callback.step_start",
            trace_id=trace.trace_id,
            step_id=step.step_id,
            step_type=step.step_type.value,
            name=step.name,
        )

    async def on_step_end(self, trace: ExecutionTrace, step: ExecutionStep) -> None:
        logger.debug(
            "callback.step_end",
            trace_id=trace.trace_id,
            step_id=step.step_id,
            duration_ms=step.duration_ms,
            status=step.status,
        )

    async def on_thinking(self, trace: ExecutionTrace, step: ExecutionStep, content: str) -> None:
        logger.debug(
            "callback.thinking",
            trace_id=trace.trace_id,
            step_id=step.step_id,
            content_preview=content[:100] if content else "",
        )

    async def on_retrieval(
        self,
        trace: ExecutionTrace,
        step: ExecutionStep,
        query: str,
        results: list[dict[str, Any]],
    ) -> None:
        logger.debug(
            "callback.retrieval",
            trace_id=trace.trace_id,
            step_id=step.step_id,
            query=query[:100],
            result_count=len(results),
        )

    async def on_memory_save(
        self,
        trace: ExecutionTrace,
        var_name: str,
        value: Any,
        source_step: str,
    ) -> None:
        logger.debug(
            "callback.memory_save",
            trace_id=trace.trace_id,
            var_name=var_name,
            source_step=source_step,
        )

    async def on_trace_end(self, trace: ExecutionTrace) -> None:
        logger.info(
            "callback.trace_end",
            trace_id=trace.trace_id,
            step_count=trace.step_count(),
            success=trace.success,
            duration_ms=trace.duration_ms,
        )


class CallbackManager:
    """Manages and dispatches tracing callbacks.

    Provides a thread-safe way to add/remove callbacks and
    dispatch events to all registered callbacks.
    """

    def __init__(self):
        self._callbacks: list[TracingCallback] = []
        self._lock = __import__("threading").Lock()

    def add_callback(self, callback: TracingCallback) -> None:
        """Add a callback to the manager.

        Args:
            callback: Callback instance to add
        """
        with self._lock:
            self._callbacks.append(callback)

    def remove_callback(self, callback: TracingCallback) -> None:
        """Remove a callback from the manager.

        Args:
            callback: Callback instance to remove
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def clear_callbacks(self) -> None:
        """Remove all callbacks."""
        with self._lock:
            self._callbacks.clear()

    async def emit_step_start(self, trace: ExecutionTrace, step: ExecutionStep) -> None:
        """Emit step_start event to all callbacks."""
        for callback in self._callbacks:
            try:
                await callback.on_step_start(trace, step)
            except Exception as e:
                logger.warning(
                    "callback_error",
                    event="step_start",
                    error=str(e),
                )

    async def emit_step_end(self, trace: ExecutionTrace, step: ExecutionStep) -> None:
        """Emit step_end event to all callbacks."""
        for callback in self._callbacks:
            try:
                await callback.on_step_end(trace, step)
            except Exception as e:
                logger.warning(
                    "callback_error",
                    event="step_end",
                    error=str(e),
                )

    async def emit_thinking(self, trace: ExecutionTrace, step: ExecutionStep, content: str) -> None:
        """Emit thinking event to all callbacks."""
        for callback in self._callbacks:
            try:
                await callback.on_thinking(trace, step, content)
            except Exception as e:
                logger.warning(
                    "callback_error",
                    event="thinking",
                    error=str(e),
                )

    async def emit_retrieval(
        self,
        trace: ExecutionTrace,
        step: ExecutionStep,
        query: str,
        results: list[dict[str, Any]],
    ) -> None:
        """Emit retrieval event to all callbacks."""
        for callback in self._callbacks:
            try:
                await callback.on_retrieval(trace, step, query, results)
            except Exception as e:
                logger.warning(
                    "callback_error",
                    event="retrieval",
                    error=str(e),
                )

    async def emit_memory_save(
        self,
        trace: ExecutionTrace,
        var_name: str,
        value: Any,
        source_step: str,
    ) -> None:
        """Emit memory_save event to all callbacks."""
        for callback in self._callbacks:
            try:
                await callback.on_memory_save(trace, var_name, value, source_step)
            except Exception as e:
                logger.warning(
                    "callback_error",
                    event="memory_save",
                    error=str(e),
                )

    async def emit_trace_end(self, trace: ExecutionTrace) -> None:
        """Emit trace_end event to all callbacks."""
        for callback in self._callbacks:
            try:
                await callback.on_trace_end(trace)
            except Exception as e:
                logger.warning(
                    "callback_error",
                    event="trace_end",
                    error=str(e),
                )


__all__ = [
    "CallbackManager",
    "LoggingCallback",
    "TracingCallback",
]
