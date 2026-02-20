"""
omni.core.services.persistence - Async Persistence Service

Handles asynchronous checkpoint saving by subscribing to events from the Rust Event Bus.
This enables non-blocking state persistence for the agent loop.

# Architecture

```text
Rust GLOBAL_BUS.publish("agent", "agent/step_complete", payload)
              ↓
Kernel Reactor (Python)
              ↓
AsyncPersistenceService.handle_agent_step()
              ↓
Rust CheckpointStore.save_checkpoint()
```

# Usage

```python
from omni.core.kernel.reactor import get_reactor
from omni.core.services.persistence import AsyncPersistenceService

# Get persistence service (created with Rust store wrapper)
service = AsyncPersistenceService(rust_store)

# Register handler with reactor
reactor = get_reactor()
reactor.register_handler("agent/step_complete", service.handle_agent_step)
```

"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.services.persistence")

# Event topic constant
AGENT_STEP_COMPLETE = "agent/step_complete"


class AsyncPersistenceService:
    """Async service for persisting agent state via event bus.

    Subscribes to 'agent/step_complete' events and saves checkpoints to the
    Rust-optimized LanceDB backend. Enables fire-and-forget persistence
    without blocking the agent loop.
    """

    def __init__(self, rust_store: Any) -> None:
        """Initialize the persistence service.

        Args:
            rust_store: Rust CheckpointStore wrapper with save_checkpoint method.
        """
        self._store = rust_store
        self._pending_saves: asyncio.Queue[str] = asyncio.Queue(maxsize=1000)
        self._worker_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background save worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._save_worker())
        logger.info("AsyncPersistenceService started")

    async def stop(self) -> None:
        """Stop the background save worker."""
        if not self._running:
            return

        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        logger.info("AsyncPersistenceService stopped")

    async def handle_agent_step(self, event: dict) -> None:
        """Handler for agent step complete events.

        Called by the Reactor when 'agent/step_complete' events are received.
        Queues the checkpoint for async saving.

        Args:
            event: OmniEvent dict with 'payload' containing state data.
        """
        try:
            payload = event.get("payload", {})

            # Extract checkpoint data
            thread_id = payload.get("thread_id", "unknown")
            step = payload.get("step", 0)
            state = payload.get("state", {})
            timestamp = payload.get("timestamp", 0)

            # Create checkpoint ID
            checkpoint_id = f"{thread_id}_{step}"

            # Queue for background saving
            await self._pending_saves.put(
                json.dumps(
                    {
                        "checkpoint_id": checkpoint_id,
                        "thread_id": thread_id,
                        "step": step,
                        "state": state,
                        "timestamp": timestamp,
                    }
                )
            )

            logger.debug(f"Queued checkpoint: {checkpoint_id}")

        except asyncio.QueueFull:
            logger.warning("Checkpoint queue full, dropping save request")
        except Exception as e:
            logger.error(f"Error handling agent step event: {e}")

    async def _save_worker(self) -> None:
        """Background worker that processes queued checkpoints."""
        logger.debug("Persistence worker started")

        while self._running:
            try:
                # Wait for queued checkpoints
                try:
                    item = await asyncio.wait_for(self._pending_saves.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                data = json.loads(item)
                await self._save_to_store(data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in persistence worker: {e}")

        # Process remaining items before exit
        while not self._pending_saves.empty():
            try:
                item = self._pending_saves.get_nowait()
                data = json.loads(item)
                await self._save_to_store(data)
            except Exception:
                break

        logger.debug("Persistence worker stopped")

    async def _save_to_store(self, data: dict) -> None:
        """Save checkpoint to the Rust store.

        Args:
            data: Checkpoint data dictionary.
        """
        try:
            from omni.foundation.api.checkpoint_schema import validate_checkpoint_write

            checkpoint_id = data["checkpoint_id"]
            thread_id = data["thread_id"]
            state = json.dumps(data["state"])
            timestamp = data["timestamp"]
            payload = {
                "checkpoint_id": checkpoint_id,
                "thread_id": thread_id,
                "timestamp": timestamp,
                "content": state,
                "parent_id": None,
                "embedding": None,
                "metadata": None,
            }
            validate_checkpoint_write("checkpoints", payload)

            # Call Rust store wrapper
            if hasattr(self._store, "save_checkpoint"):
                await self._store.save_checkpoint(
                    table_name="checkpoints",
                    checkpoint_id=payload["checkpoint_id"],
                    thread_id=payload["thread_id"],
                    content=payload["content"],
                    timestamp=payload["timestamp"],
                    parent_id=None,
                    embedding=payload["embedding"],
                    metadata=payload["metadata"],
                )
                logger.debug(f"💾 Checkpoint saved: {checkpoint_id}")
            else:
                logger.warning("Rust store does not have save_checkpoint method")

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    @property
    def is_running(self) -> bool:
        """Check if the service is running."""
        return self._running

    def get_queue_size(self) -> int:
        """Get the current queue size."""
        return self._pending_saves.qsize()
