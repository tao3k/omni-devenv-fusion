"""TimeTraveler - Rust-accelerated Time Travel for LangGraph Checkpoints.

This module provides high-performance checkpoint time-travel functionality
by leveraging Rust-native timeline retrieval and parsing.

Architecture:
    - Rust: Heavy lifting (I/O, JSON parsing, timeline construction)
    - Python: Orchestration (LangGraph integration, state patching, TUI events)

Example:
    >>> from omni.agent.core.time_travel.traveler import TimeTraveler
    >>> from omni.langgraph.checkpoint.lance import create_checkpointer
    >>>
    >>> checkpointer = create_checkpointer()
    >>> traveler = TimeTraveler(checkpointer)
    >>>
    >>> # Get timeline (Rust-native, fast)
    >>> timeline = await traveler.get_timeline("thread-123")
    >>> for event in timeline[:5]:
    >>>     print(f"Step {event.step}: {event.content_preview[:50]}...")
    >>>
    >>> # Fork and correct (Python orchestration)
    >>> new_config = await traveler.fork_and_correct(
    ...     graph, "thread-123", 3,
    ...     {"goal": "revised goal"},
    ...     "Fixing incorrect goal"
    ... )
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableConfig

from omni.agent.cli.tui_bridge import NullTUIBridge, TUIBridgeProtocol
from omni.langgraph.checkpoint.lance import RustLanceCheckpointSaver

logger = logging.getLogger(__name__)


class PyTimelineEvent:
    """Python wrapper for Rust TimelineEvent.

    V2.1: Aligned with TUI Visual Debugger requirements.
    This class provides a Python-friendly interface to the Rust-native
    timeline events. All field access is direct - no serialization overhead.
    """

    def __init__(
        self,
        checkpoint_id: str,
        thread_id: str,
        step: int,
        timestamp: float,
        preview: str,
        parent_checkpoint_id: Optional[str],
        reason: Optional[str] = None,
    ) -> None:
        self.checkpoint_id = checkpoint_id
        self.thread_id = thread_id
        self.step = step
        self.timestamp = timestamp
        self.preview = preview
        self.parent_checkpoint_id = parent_checkpoint_id
        self.reason = reason

    @property
    def iso_timestamp(self) -> str:
        """Format timestamp as ISO 8601 string."""
        secs = int(self.timestamp)
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(secs, tz=timezone.utc)
        return dt.isoformat()

    @property
    def relative_time(self) -> str:
        """Get relative time string (e.g., '2m ago')."""
        import time

        now_ms = time.time() * 1000
        diff_ms = now_ms - self.timestamp
        secs = diff_ms / 1000.0

        if secs < 60:
            return f"{secs:.0f}s ago"
        elif secs < 3600:
            return f"{secs / 60:.0f}m ago"
        elif secs < 86400:
            return f"{secs / 3600:.0f}h ago"
        else:
            return f"{secs / 86400:.1f}d ago"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for TUI serialization."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "thread_id": self.thread_id,
            "step": self.step,
            "timestamp": self.timestamp,
            "preview": self.preview,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "reason": self.reason,
        }

    def __repr__(self) -> str:
        return (
            f"PyTimelineEvent(step={self.step}, "
            f"checkpoint_id='{self.checkpoint_id[:8]}...', "
            f"timestamp={self.relative_time})"
        )


class TimeTraveler:
    """Rust-accelerated Time Traveler for LangGraph Checkpoints.

    Provides high-performance timeline retrieval and state branching
    for LangGraph workflows. Integrates with Rust TUI for visual feedback.

    Architecture:
        Rust (omni-vector) <-- I/O --> Python (TimeTraveler) <-- Events --> Rust TUI

    Attributes:
        checkpointer: The RustLanceCheckpointSaver instance for checkpoint I/O.
        table_name: The checkpoint table name (default: "checkpoints").
        tui: Optional TUI bridge for visual feedback.
    """

    def __init__(
        self,
        checkpointer: RustLanceCheckpointSaver,
        table_name: str = "checkpoints",
        tui: Optional[TUIBridgeProtocol] = None,
    ) -> None:
        """Initialize the TimeTraveler.

        Args:
            checkpointer: A RustLanceCheckpointSaver instance.
            table_name: Name of the checkpoint table (default: "checkpoints").
            tui: Optional TUI bridge for visual feedback (default: NullTUIBridge).
        """
        self.checkpointer = checkpointer
        self.table_name = table_name
        self.tui = tui or NullTUIBridge()

    async def get_timeline(
        self,
        thread_id: str,
        limit: int = 20,
    ) -> List[PyTimelineEvent]:
        """Get the timeline of checkpoints for a thread.

        This method is Rust-native: all I/O, parsing, and preview generation
        happen in Rust, providing ~10x speedup over pure Python implementations.

        Args:
            thread_id: The thread ID to get timeline for.
            limit: Maximum number of events to return (default: 20).

        Returns:
            List of PyTimelineEvent objects, sorted newest first (step 0 = latest).
        """
        # Call Rust-native method - returns list of PyTimelineEvent objects
        rust_events = self.checkpointer.store.get_timeline(self.table_name, thread_id, limit)

        # Convert to Python wrapper (lightweight, no parsing needed)
        return [
            PyTimelineEvent(
                checkpoint_id=e.checkpoint_id,
                thread_id=e.thread_id,
                step=e.step,
                timestamp=e.timestamp,
                preview=e.preview,
                parent_checkpoint_id=e.parent_checkpoint_id,
                reason=e.reason,
            )
            for e in rust_events
        ]

    async def get_checkpoint_content(
        self,
        checkpoint_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the full content of a specific checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to retrieve.

        Returns:
            The checkpoint content as a dictionary, or None if not found.
        """
        content = self.checkpointer.store.get_checkpoint_content(self.table_name, checkpoint_id)
        if content is None:
            return None
        return json.loads(content)

    async def fork_and_correct(
        self,
        graph: Any,
        thread_id: str,
        steps_back: int,
        patch_state: Dict[str, Any],
        reason: str,
    ) -> RunnableConfig:
        """Fork the graph state at a historical checkpoint and apply corrections.

        This is the primary "time-travel" operation: find a historical state,
        branch from it, and apply state patches to create a corrected execution path.

        Events emitted:
            - time_travel/initiating: When time travel begins
            - time_travel/complete: When new checkpoint is created

        Args:
            graph: The LangGraph to operate on.
            thread_id: The thread ID.
            steps_back: How many steps back to go (1 = previous checkpoint).
            patch_state: The state dictionary to apply to the forked checkpoint.
            reason: Human-readable reason for the correction.

        Returns:
            The new RunnableConfig with the forked state.

        Raises:
            ValueError: If steps_back is beyond available history.
        """
        # 1. Get timeline (Rust-native, fast)
        timeline = await self.get_timeline(thread_id, limit=steps_back + 5)

        if len(timeline) <= steps_back:
            raise ValueError(
                f"History too short. Requested -{steps_back}, available {len(timeline)} checkpoints"
            )

        # 2. Locate target checkpoint
        target_event = timeline[steps_back]
        target_checkpoint_id = target_event.checkpoint_id
        from_step = timeline[0].step

        # 3. Emit TUI event: "We are warping time!"
        await self._emit_tui_event(
            "time_travel/initiating",
            {
                "from_step": from_step,
                "to_step": target_event.step,
                "target_id": target_checkpoint_id,
                "reason": reason,
                "thread_id": thread_id,
            },
        )

        # 4. Build LangGraph configuration (Python orchestration required)
        target_config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": target_checkpoint_id,
            }
        }

        # 5. Fork and patch (LangGraph API, must be in Python)
        new_config = await graph.update_state(
            target_config,
            patch_state,
            as_node="__start__",
        )

        # 6. Emit TUI event: "New Universe Created"
        await self._emit_tui_event(
            "time_travel/complete",
            {
                "new_checkpoint": new_config["configurable"]["checkpoint_id"],
                "parent": target_checkpoint_id,
                "reason": reason,
                "thread_id": thread_id,
            },
        )

        # 7. Log the time-travel event for debugging/audit
        logger.info(
            f"[TimeTraveler] Forked from step -{steps_back} "
            f"(checkpoint: {target_checkpoint_id[:8]}...)"
        )
        logger.info(f"  Reason: {reason}")
        logger.debug(f"  Patch: {json.dumps(patch_state, default=str)}")

        return new_config

    async def compare_checkpoints(
        self,
        checkpoint_a: str,
        checkpoint_b: str,
    ) -> Dict[str, Any]:
        """Compare two checkpoints in a thread.

        Args:
            checkpoint_a: First checkpoint ID.
            checkpoint_b: Second checkpoint ID.

        Returns:
            Dictionary with comparison results (diff, metadata).
        """
        content_a = await self.get_checkpoint_content(checkpoint_a)
        content_b = await self.get_checkpoint_content(checkpoint_b)

        if content_a is None or content_b is None:
            raise ValueError("One or both checkpoints not found")

        # Simple diff by key comparison
        keys_a = set(content_a.keys())
        keys_b = set(content_b.keys())

        added = keys_b - keys_a
        removed = keys_a - keys_b
        changed = {k for k in keys_a & keys_b if content_a[k] != content_b[k]}

        return {
            "checkpoint_a": checkpoint_a,
            "checkpoint_b": checkpoint_b,
            "added": list(added),
            "removed": list(removed),
            "changed": list(changed),
        }

    async def _emit_tui_event(self, topic: str, payload: Dict[str, Any]) -> None:
        """Dispatch event to Rust TUI via socket.

        Args:
            topic: Event topic (e.g., 'time_travel/initiating')
            payload: Event payload data
        """
        try:
            await self.tui.send_event(topic, payload)
        except Exception as e:
            logger.debug(f"Failed to emit TUI event {topic}: {e}")
