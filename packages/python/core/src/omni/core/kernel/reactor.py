"""
omni.core.kernel.reactor - Event-Driven Kernel Reactor

Reactive architecture bridge between Rust Event Bus and Python components.
Consumes events from the Rust GLOBAL_BUS and dispatches to Python handlers.

# Architecture

```text
Rust GLOBAL_BUS (tokio broadcast)
              ↓
KernelReactor (Python async consumer)
              ↓
┌─────────────┼─────────────┬─────────────┐
│             │             │             │
↓             ↓             ↓             ↓
Cortex    Checkpoint    Sniffer     Watcher
Indexer      Saver     Context    (Python)
```

# Usage

```python
from omni.core.kernel.reactor import KernelReactor, get_reactor

# Get global reactor
reactor = get_reactor()

# Register handlers
@reactor.register_handler("file/changed")
async def handle_file_change(event):
    await cortex.index_single(event.payload["path"])
```
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.reactor")

# Event type alias
OmniEvent = dict[str, Any]


class EventTopic(Enum):
    """Core event topics matching Rust omni-events crate."""

    FILE_CHANGED = "file/changed"
    FILE_CREATED = "file/created"
    FILE_DELETED = "file/deleted"
    AGENT_THINK = "agent/think"
    AGENT_ACTION = "agent/action"
    AGENT_RESULT = "agent/result"
    MCP_REQUEST = "mcp/request"
    MCP_RESPONSE = "mcp/response"
    SYSTEM_READY = "system/ready"
    SYSTEM_SHUTDOWN = "system/shutdown"
    CORTEX_INDEX_UPDATED = "cortex/index_updated"
    CORTEX_QUERY = "cortex/query"

    @classmethod
    def from_string(cls, topic: str) -> "EventTopic | None":
        """Convert string to EventTopic."""
        for member in cls:
            if member.value == topic:
                return member
        return None


@dataclass
class EventHandler:
    """Registered event handler."""

    callback: Callable[[OmniEvent], Coroutine[Any, Any, None]]
    topic: str
    priority: int = 0


@dataclass
class ReactorStats:
    """Reactor runtime statistics."""

    events_received: int = 0
    events_processed: int = 0
    events_failed: int = 0
    handlers_registered: int = 0
    start_time: float = 0.0
    is_running: bool = False


class KernelReactor:
    """
    Event-Driven Kernel Reactor.

    Consumes events from Rust Event Bus and dispatches to registered Python handlers.
    Provides:
    - Topic-based subscription
    - Handler priority ordering
    - Graceful shutdown propagation
    - Runtime statistics
    """

    def __init__(self, *, max_queue_size: int = 1000) -> None:
        """Initialize the kernel reactor."""
        self._handlers: dict[str, list[EventHandler]] = {}
        self._default_handlers: list[EventHandler] = []
        self._stats = ReactorStats()
        self._running = False
        self._consumer_task: asyncio.Task[None] | None = None
        self._queue: asyncio.Queue[OmniEvent] = asyncio.Queue(maxsize=max_queue_size)

        # Thread-safe event filtering
        self._topic_filters: set[str] = set()

    @property
    def stats(self) -> ReactorStats:
        """Get reactor statistics."""
        return self._stats

    def register_handler(
        self,
        topic: str | EventTopic,
        callback: Callable[[OmniEvent], Coroutine[Any, Any, None]],
        *,
        priority: int = 0,
    ) -> None:
        """
        Register an event handler for a specific topic.

        Args:
            topic: Event topic string or EventTopic enum
            callback: Async callback function receiving OmniEvent dict
            priority: Handler priority (higher = runs first)
        """
        topic_str = topic.value if isinstance(topic, EventTopic) else topic

        handler = EventHandler(callback=callback, topic=topic_str, priority=priority)

        if topic_str == "*":
            self._default_handlers.append(handler)
        else:
            if topic_str not in self._handlers:
                self._handlers[topic_str] = []
            self._handlers[topic_str].append(handler)
            # Sort by priority descending
            self._handlers[topic_str].sort(key=lambda h: -h.priority)

        self._stats.handlers_registered += 1
        logger.debug(f"Registered handler for topic '{topic_str}' with priority {priority}")

    def unregister_handler(
        self,
        topic: str | EventTopic,
        callback: Callable[[OmniEvent], Coroutine[Any, Any, None]],
    ) -> bool:
        """
        Unregister an event handler.

        Args:
            topic: Event topic string or EventTopic enum
            callback: The callback to remove

        Returns:
            True if handler was found and removed
        """
        topic_str = topic.value if isinstance(topic, EventTopic) else topic

        if topic_str == "*":
            removed = self._remove_handler(self._default_handlers, callback)
        elif topic_str in self._handlers:
            removed = self._remove_handler(self._handlers[topic_str], callback)
            if not self._handlers[topic_str]:
                del self._handlers[topic_str]
        else:
            removed = False

        if removed:
            self._stats.handlers_registered = max(0, self._stats.handlers_registered - 1)

        return removed

    def _remove_handler(
        self,
        handlers: list[EventHandler],
        callback: Callable[[OmniEvent], Coroutine[Any, Any, None]],
    ) -> bool:
        """Remove a handler from a list."""
        original_len = len(handlers)
        self._default_handlers[:] = [h for h in handlers if h.callback != callback]
        return len(self._default_handlers) < original_len

    async def start(self) -> None:
        """Start the reactor consumer loop."""
        if self._running:
            logger.warning("Reactor is already running")
            return

        self._running = True
        self._stats.start_time = asyncio.get_event_loop().time()
        self._stats.is_running = True

        # Start consumer task
        self._consumer_task = asyncio.create_task(self._consumer_loop())
        logger.info("KernelReactor started")

    async def stop(self) -> None:
        """Stop the reactor and all handlers."""
        if not self._running:
            return

        logger.info("Stopping KernelReactor...")

        # Signal shutdown
        self._running = False

        # Cancel consumer task
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

        # Send shutdown event to handlers
        shutdown_event: OmniEvent = {
            "id": "shutdown",
            "source": "reactor",
            "topic": EventTopic.SYSTEM_SHUTDOWN.value,
            "payload": {},
        }

        # Call all handlers with shutdown event
        for handlers in self._handlers.values():
            for handler in handlers:
                await self._safe_call(handler.callback, shutdown_event)

        for handler in self._default_handlers:
            await self._safe_call(handler.callback, shutdown_event)

        self._stats.is_running = False
        logger.info("KernelReactor stopped")

    async def _consumer_loop(self) -> None:
        """Main event consumer loop."""
        logger.debug("Reactor consumer loop started")

        while self._running:
            try:
                # Get event from queue (with timeout for checking _running)
                event = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reactor consumer loop: {e}", exc_info=True)

        logger.debug("Reactor consumer loop ended")

    async def _dispatch(self, event: OmniEvent) -> None:
        """Dispatch an event to registered handlers."""
        self._stats.events_received += 1
        topic = event.get("topic", "")

        # Get handlers for this topic
        handlers = self._handlers.get(topic, [])

        # Also call default handlers (*)
        all_handlers = handlers + self._default_handlers

        if not all_handlers:
            logger.debug(f"No handlers for event topic: {topic}")
            return

        # Dispatch to all handlers (fan-out)
        for handler in all_handlers:
            await self._safe_call(handler.callback, event)

        self._stats.events_processed += 1

    async def _safe_call(
        self, callback: Callable[[OmniEvent], Coroutine[Any, Any, None]], event: OmniEvent
    ) -> None:
        """Safely call a handler with error handling."""
        try:
            await callback(event)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._stats.events_failed += 1
            logger.error(f"Handler error for event {event.get('topic')}: {e}", exc_info=True)

    def set_topic_filter(self, topics: set[str] | None) -> None:
        """Set topic filters (only process these topics)."""
        self._topic_filters = topics or set()

    def clear_topic_filter(self) -> None:
        """Clear topic filters (process all topics)."""
        self._topic_filters.clear()

    @property
    def is_running(self) -> bool:
        """Check if reactor is running."""
        return self._running

    def get_registered_topics(self) -> list[str]:
        """Get list of registered topics."""
        return list(self._handlers.keys())


# Global reactor instance
_reactor: KernelReactor | None = None


def get_reactor() -> KernelReactor:
    """Get the global reactor instance."""
    global _reactor
    if _reactor is None:
        _reactor = KernelReactor()
    return _reactor


def reset_reactor() -> None:
    """Reset the global reactor instance."""
    global _reactor
    if _reactor and _reactor.is_running:
        import warnings

        warnings.warn("Resetting running reactor", RuntimeWarning)
    _reactor = None
