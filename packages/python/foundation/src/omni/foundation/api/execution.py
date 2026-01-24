"""
execution.py - Execution Control Decorators

Provides decorators for tracing, timing, retrying, and caching function execution.
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

from ..config.logging import get_logger

logger = get_logger("omni.api.execution")

# Type variable for generic callable
F = TypeVar("F", bound=Callable[..., Any])


def trace_execution(
    log_args: bool = False, log_result: bool = True, log_level: str = "debug"
) -> Callable[[F], F]:
    """
    Decorator to trace function execution with structured logging.

    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log the result
        log_level: Logging level ('debug', 'info', 'warning', 'error')

    Usage:
        @trace_execution(log_args=True, log_result=True)
        def my_function(x: int) -> int:
            return x * 2
    """

    def decorator(func: F) -> F:
        log_method = getattr(logger, log_level)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            arg_str = f"({', '.join(map(repr, args))}, {kwargs})" if log_args else ""
            log_method(f"[TRACE] {func.__name__}{arg_str} started")
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                if log_result:
                    log_method(f"[TRACE] {func.__name__} returned: {result} ({elapsed:.2f}ms)")
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                log_method(f"[TRACE] {func.__name__} raised {type(e).__name__}: {e} ({elapsed:.2f}ms)")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            arg_str = f"({', '.join(map(repr, args))}, {kwargs})" if log_args else ""
            log_method(f"[TRACE] {func.__name__}{arg_str} started")
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = (time.perf_counter() - start) * 1000
                if log_result:
                    log_method(f"[TRACE] {func.__name__} returned: {result} ({elapsed:.2f}ms)")
                return result
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                log_method(f"[TRACE] {func.__name__} raised {type(e).__name__}: {e} ({elapsed:.2f}ms)")
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator


def measure_time(unit: str = "ms") -> Callable[[F], F]:
    """
    Decorator to measure and log function execution time.

    Args:
        unit: Time unit ('ms', 's', 'us', 'ns')

    Usage:
        @measure_time(unit="ms")
        def my_function():
            pass
    """

    def decorator(func: F) -> F:
        multipliers = {
            "ns": 1_000_000.0,
            "us": 1000.0,
            "ms": 1.0,
            "s": 0.001,
        }

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.debug(f"[TIMING] {func.__name__} completed in {duration_ms:.2f}ms")
            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            result = func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            logger.debug(f"[TIMING] {func.__name__} completed in {duration_ms:.2f}ms")
            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Retry a function with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Backoff multiplier
        exceptions: Tuple of exception types to catch and retry

    Usage:
        @retry(max_attempts=3, delay=1.0, backoff=2.0)
        def my_function():
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. Retrying in {current_delay:.2f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed: {e}")
                        raise

            raise last_exception  # type: ignore

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {e}. Retrying in {current_delay:.2f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed: {e}")
                        raise

            raise last_exception  # type: ignore

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator


class TimingContext:
    """Context manager for timing code blocks."""

    def __init__(self, name: str, logger_obj: Any | None = None):
        self.name = name
        self.logger = logger_obj or logger
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def __enter__(self) -> TimingContext:
        self.start_time = time.perf_counter()
        self.logger.debug(f"Starting: {self.name}")
        return self

    def __exit__(self, *args: Any) -> None:
        self.end_time = time.perf_counter()
        duration_ms = (self.end_time - self.start_time) * 1000
        self.logger.debug(f"Finished: {self.name} in {duration_ms:.2f}ms")

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def duration_s(self) -> float:
        return self.end_time - self.start_time


def cached(maxsize: int = 128, ttl: float | None = None) -> Callable[[F], F]:
    """
    Simple cache decorator with optional TTL.

    Args:
        maxsize: Maximum cache size
        ttl: Time-to-live in seconds (None = no expiry)

    Usage:
        @cached(maxsize=256, ttl=300)
        def my_function(x: int) -> int:
            return x * 2
    """

    def decorator(func: F) -> F:
        cache: dict[str, tuple[float, Any]] = {}

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time as time_module

            key = f"{args}:{kwargs}"
            now = time_module.time()

            # Check cache with TTL
            if key in cache:
                cached_time, cached_value = cache[key]
                if ttl is None or now - cached_time < ttl:
                    return cached_value

            # Cache miss - call function
            result = await func(*args, **kwargs)
            now = time_module.time()

            # Manage cache size
            if len(cache) >= maxsize:
                # Remove oldest entry
                cache.pop(next(iter(cache)))

            cache[key] = (now, result)
            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            import time as time_module

            key = f"{args}:{kwargs}"
            now = time_module.time()

            # Check cache with TTL
            if key in cache:
                cached_time, cached_value = cache[key]
                if ttl is None or now - cached_time < ttl:
                    return cached_value

            # Cache miss - call function
            result = func(*args, **kwargs)
            now = time_module.time()

            # Manage cache size
            if len(cache) >= maxsize:
                # Remove oldest entry
                cache.pop(next(iter(cache)))

            cache[key] = (now, result)
            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper  # type: ignore[return-value]

    return decorator


__all__ = [
    "TimingContext",
    "cached",
    "measure_time",
    "retry",
    "trace_execution",
]
