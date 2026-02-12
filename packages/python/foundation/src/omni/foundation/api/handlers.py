"""
handlers.py - Skill Command Handler (v2.2)

Unified error handling, logging, and result filtering for skill commands.

Features:
- Automatic error capture and formatting
- Structured execution logging
- Result filtering and validation
- Standardized CommandResult output

Usage:
    @skill_command(
        name="my_command",
        error_handler=ErrorHandlers.RAISE,  # or SUPPRESS, LOG_ONLY
        result_filter=ResultFilters.SUCCESS_ONLY,
        logger=LoggerConfig(level="debug", trace_args=True),
    )
    def my_command():
        ...
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from ..config.logging import get_logger

logger = get_logger("omni.api.handler")


class ErrorStrategy(Enum):
    """Error handling strategies for skill commands."""

    RAISE = "raise"  # Re-raise exception after logging
    SUPPRESS = "suppress"  # Return error in result, don't raise
    LOG_ONLY = "log_only"  # Log and continue without error


class LogLevel(Enum):
    """Log levels for skill command execution."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    OFF = "off"


@dataclass
class LoggerConfig:
    """Configuration for skill command logging."""

    level: LogLevel = LogLevel.INFO
    trace_args: bool = False
    trace_result: bool = True
    trace_timing: bool = True
    log_success: bool = True
    log_failure: bool = True

    def should_log(self, level: str) -> bool:
        """Check if a log level should be output."""
        if self.level == LogLevel.OFF:
            return False
        levels = ["debug", "info", "warning", "error"]
        return levels.index(level) >= levels.index(self.level.value)


@dataclass
class ResultConfig:
    """Configuration for result filtering and formatting."""

    filter_empty: bool = True
    max_result_depth: int = 3
    include_timing: bool = True
    include_metadata: bool = True


@dataclass
class ExecutionResult:
    """Standardized result from skill command execution."""

    success: bool
    data: Any | None = None
    error: str | None = None
    error_type: str | None = None
    timing_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {
            "success": self.success,
        }
        if self.success:
            if self.data is not None:
                result["data"] = self.data
            if self.metadata.get("include_timing", True):
                result["timing_ms"] = round(self.timing_ms, 2)
        else:
            if self.error is not None:
                result["error"] = self.error
            if self.error_type is not None:
                result["error_type"] = self.error_type
        return result

    @classmethod
    def ok(cls, data: Any = None, timing_ms: float = 0.0) -> "ExecutionResult":
        """Create a successful result."""
        return cls(success=True, data=data, timing_ms=timing_ms)

    @classmethod
    def fail(
        cls,
        error: str,
        error_type: str | None = None,
        timing_ms: float = 0.0,
    ) -> "ExecutionResult":
        """Create a failed result."""
        return cls(
            success=False,
            error=error,
            error_type=error_type or "UnknownError",
            timing_ms=timing_ms,
        )


class SkillCommandHandler:
    """Unified handler for skill command execution.

    Provides:
    - Error handling with configurable strategy
    - Structured logging with timing
    - Result filtering and formatting
    - Standardized ExecutionResult output
    """

    def __init__(
        self,
        name: str,
        *,
        # Error handling
        error_strategy: ErrorStrategy = ErrorStrategy.RAISE,
        # Logging
        log_config: LoggerConfig | None = None,
        # Result handling
        result_config: ResultConfig | None = None,
    ):
        self.name = name
        self.error_strategy = error_strategy
        self.log_config = log_config or LoggerConfig()
        self.result_config = result_config or ResultConfig()

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Log a message if the level is enabled."""
        if not self.log_config.should_log(level):
            return
        log_method = getattr(logger, level)
        extra = {"skill": self.name}
        log_method(f"[{self.name}] {message}", extra=extra)

    def _execute_sync(self, func: Callable, *args: Any, **kwargs: Any) -> ExecutionResult:
        """Execute a synchronous function with error handling and logging."""
        start_time = time.perf_counter()

        # Log execution start
        if self.log_config.trace_args:
            arg_str = f"args={args}, kwargs={kwargs}"
            self._log("debug", f"Executing: {func.__name__}({arg_str})")
        else:
            self._log("debug", f"Executing: {func.__name__}")

        try:
            # Execute the function
            result = func(*args, **kwargs)
            timing_ms = (time.perf_counter() - start_time) * 1000

            # Process successful result
            data = self._filter_result(result)
            execution_result = ExecutionResult.ok(data=data, timing_ms=timing_ms)

            if self.log_config.log_success:
                self._log("info", f"Success: {func.__name__}", timing_ms=round(timing_ms, 2))

            return execution_result

        except Exception as e:
            # Process exception
            timing_ms = (time.perf_counter() - start_time) * 1000
            error_type = type(e).__name__
            error_message = str(e)

            if self.log_config.log_failure:
                self._log("error", f"Failed: {error_type}: {error_message}")

            if self.error_strategy == ErrorStrategy.RAISE:
                # Re-raise after logging
                raise

            # Return error result (SUPPRESS or LOG_ONLY)
            return ExecutionResult.fail(
                error=error_message,
                error_type=error_type,
                timing_ms=timing_ms,
            )

    async def _execute_async(self, func: Callable, *args: Any, **kwargs: Any) -> ExecutionResult:
        """Execute an async function with error handling and logging."""
        start_time = time.perf_counter()

        if self.log_config.trace_args:
            arg_str = f"args={args}, kwargs={kwargs}"
            self._log("debug", f"Async Executing: {func.__name__}({arg_str})")
        else:
            self._log("debug", f"Async Executing: {func.__name__}")

        try:
            result = await func(*args, **kwargs)
            timing_ms = (time.perf_counter() - start_time) * 1000

            data = self._filter_result(result)
            execution_result = ExecutionResult.ok(data=data, timing_ms=timing_ms)

            if self.log_config.log_success:
                self._log("info", f"Async Success: {func.__name__}", timing_ms=round(timing_ms, 2))

            return execution_result

        except Exception as e:
            timing_ms = (time.perf_counter() - start_time) * 1000
            error_type = type(e).__name__
            error_message = str(e)

            if self.log_config.log_failure:
                self._log("error", f"Async Failed: {error_type}: {error_message}")

            if self.error_strategy == ErrorStrategy.RAISE:
                raise

            return ExecutionResult.fail(
                error=error_message,
                error_type=error_type,
                timing_ms=timing_ms,
            )

    def _filter_result(self, result: Any) -> Any:
        """Filter and format the result."""
        if result is None:
            return None

        if self.result_config.filter_empty:
            if isinstance(result, dict) and not result:
                return None
            if isinstance(result, list) and not result:
                return None

        return result

    def __call__(self, func: Callable) -> Callable:
        """Decorate a function with this handler."""

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> ExecutionResult:
            return self._execute_sync(func, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> ExecutionResult:
            return await self._execute_async(func, *args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper


def create_handler(
    name: str,
    *,
    error_strategy: str = "raise",
    log_level: str = "info",
    trace_args: bool = False,
    trace_result: bool = True,
) -> SkillCommandHandler:
    """Factory function to create a SkillCommandHandler.

    Args:
        name: Skill command name
        error_strategy: "raise", "suppress", or "log_only"
        log_level: "debug", "info", "warning", "error", or "off"
        trace_args: Whether to log function arguments
        trace_result: Whether to log successful results

    Usage:
        handler = create_handler(
            name="my_command",
            error_strategy="raise",
            log_level="debug",
            trace_args=True,
        )

        @skill_command(name="my_command")
        @handler
        def my_command():
            ...
    """
    return SkillCommandHandler(
        name=name,
        error_strategy=ErrorStrategy(error_strategy),
        log_config=LoggerConfig(
            level=LogLevel(log_level),
            trace_args=trace_args,
            trace_result=trace_result,
        ),
    )


# Convenience instances
DEFAULT_HANDLER = SkillCommandHandler(
    name="default",
    error_strategy=ErrorStrategy.RAISE,
    log_config=LoggerConfig(level=LogLevel.INFO),
)

DEBUG_HANDLER = SkillCommandHandler(
    name="debug",
    error_strategy=ErrorStrategy.RAISE,
    log_config=LoggerConfig(level=LogLevel.DEBUG, trace_args=True),
)

SILENT_HANDLER = SkillCommandHandler(
    name="silent",
    error_strategy=ErrorStrategy.RAISE,
    log_config=LoggerConfig(level=LogLevel.OFF),
)


class GraphNodeHandler:
    """Handler for LangGraph node execution.

    Features:
    - Structured logging with node name
    - Automatic error logging and re-raise
    - Execution timing tracking
    - Seamless integration with LangGraph error handling

    Usage:
        @graph_node(name="setup")
        def node_setup(state: ResearchState) -> dict:
            ...
    """

    def __init__(
        self,
        name: str,
        *,
        log_level: str = "info",
        trace_timing: bool = True,
    ):
        self.name = name
        self.log_level = LogLevel(log_level)
        self.trace_timing = trace_timing
        self._logger = get_logger(f"graph.node.{name}")

    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Log a message if the level is enabled."""
        if self.log_level == LogLevel.OFF:
            return
        levels = ["debug", "info", "warning", "error"]
        if levels.index(level) < levels.index(self.log_level.value):
            return
        log_method = getattr(self._logger, level)
        extra = {"node": self.name}
        log_method(message, extra=extra)

    def __call__(self, func: Callable) -> Callable:
        """Decorate a LangGraph node function."""

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            node_name = getattr(func, "__name__", self.name)

            try:
                result = func(*args, **kwargs)
                timing_ms = (time.perf_counter() - start_time) * 1000

                if self.trace_timing:
                    self._log("debug", f"Node completed", timing_ms=round(timing_ms, 2))

                return result

            except Exception as e:
                timing_ms = (time.perf_counter() - start_time) * 1000
                error_type = type(e).__name__
                self._log(
                    "error",
                    f"Node failed: {error_type}: {str(e)}",
                    timing_ms=round(timing_ms, 2),
                )
                # Re-raise for LangGraph error handling
                raise

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            node_name = getattr(func, "__name__", self.name)

            try:
                result = await func(*args, **kwargs)
                timing_ms = (time.perf_counter() - start_time) * 1000

                if self.trace_timing:
                    self._log("debug", f"Async node completed", timing_ms=round(timing_ms, 2))

                return result

            except Exception as e:
                timing_ms = (time.perf_counter() - start_time) * 1000
                error_type = type(e).__name__
                self._log(
                    "error",
                    f"Async node failed: {error_type}: {str(e)}",
                    timing_ms=round(timing_ms, 2),
                )
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper


def graph_node(name: str, *, log_level: str = "info") -> GraphNodeHandler:
    """Factory function to create a GraphNodeHandler.

    Args:
        name: Node name for logging
        log_level: "debug", "info", "warning", "error", or "off"

    Usage:
        @graph_node(name="setup")
        def node_setup(state: ResearchState) -> dict:
            ...
    """
    return GraphNodeHandler(name=name, log_level=log_level)


__all__ = [
    "SkillCommandHandler",
    "GraphNodeHandler",
    "ExecutionResult",
    "ErrorStrategy",
    "LogLevel",
    "LoggerConfig",
    "ResultConfig",
    "create_handler",
    "DEFAULT_HANDLER",
    "DEBUG_HANDLER",
    "SILENT_HANDLER",
]
