"""
kernel/lifecycle.py - Kernel Lifecycle Management

State machine for kernel lifecycle:
- UNINITIALIZED -> INITIALIZING -> READY -> RUNNING -> SHUTTING_DOWN -> STOPPED

Thread-safe state transitions with callbacks.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from enum import Enum
from typing import Any


class LifecycleState(Enum):
    """Kernel lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


# Type for lifecycle callbacks
LifecycleCallback = Callable[[], Any]


class LifecycleManager:
    """Manages kernel lifecycle with state machine.

    Provides thread-safe state transitions and callbacks for each state.
    """

    __slots__ = (
        "_lock",
        "_on_ready",
        "_on_running",
        "_on_shutdown",
        "_on_stopped",
        "_state",
    )

    def __init__(
        self,
        *,
        on_ready: LifecycleCallback | None = None,
        on_running: LifecycleCallback | None = None,
        on_shutdown: LifecycleCallback | None = None,
        on_stopped: LifecycleCallback | None = None,
    ) -> None:
        self._state = LifecycleState.UNINITIALIZED
        self._lock = asyncio.Lock()
        self._on_ready = on_ready
        self._on_running = on_running
        self._on_shutdown = on_shutdown
        self._on_stopped = on_stopped

    @property
    def state(self) -> LifecycleState:
        """Get current lifecycle state."""
        return self._state

    def is_initialized(self) -> bool:
        """Check if kernel has been initialized."""
        return self._state not in (
            LifecycleState.UNINITIALIZED,
            LifecycleState.INITIALIZING,
        )

    def is_ready(self) -> bool:
        """Check if kernel is ready."""
        return self._state == LifecycleState.READY

    def is_running(self) -> bool:
        """Check if kernel is running."""
        return self._state == LifecycleState.RUNNING

    def is_shutting_down(self) -> bool:
        """Check if kernel is shutting down."""
        return self._state == LifecycleState.SHUTTING_DOWN

    def is_stopped(self) -> bool:
        """Check if kernel has stopped."""
        return self._state == LifecycleState.STOPPED

    async def initialize(self) -> None:
        """Transition from UNINITIALIZED to INITIALIZING to READY."""
        async with self._lock:
            if self._state not in (
                LifecycleState.UNINITIALIZED,
                LifecycleState.INITIALIZING,
            ):
                return

            self._state = LifecycleState.INITIALIZING

            # Perform initialization
            await self._do_initialize()

            self._state = LifecycleState.READY

            # Fire ready callback
            if self._on_ready:
                await self._call_callback(self._on_ready)

    async def start(self) -> None:
        """Transition from READY to RUNNING."""
        async with self._lock:
            if self._state != LifecycleState.READY:
                return

            self._state = LifecycleState.RUNNING

            # Fire running callback
            if self._on_running:
                await self._call_callback(self._on_running)

    async def shutdown(self) -> None:
        """Transition from RUNNING to SHUTTING_DOWN to STOPPED."""
        async with self._lock:
            if self._state not in (LifecycleState.RUNNING, LifecycleState.READY):
                return

            self._state = LifecycleState.SHUTTING_DOWN

            # Fire shutdown callback
            if self._on_shutdown:
                await self._call_callback(self._on_shutdown)

            # Perform cleanup
            await self._do_shutdown()

            self._state = LifecycleState.STOPPED

            # Fire stopped callback
            if self._on_stopped:
                await self._call_callback(self._on_stopped)

    async def _do_initialize(self) -> None:
        """Perform initialization. Override in subclass."""
        pass

    async def _do_shutdown(self) -> None:
        """Perform shutdown cleanup. Override in subclass."""
        pass

    async def _call_callback(self, callback: LifecycleCallback) -> None:
        """Call a callback, handling both sync and async."""
        if asyncio.iscoroutinefunction(callback):
            await callback()
        else:
            callback()
