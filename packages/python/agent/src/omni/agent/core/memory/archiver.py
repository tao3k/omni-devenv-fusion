"""
packages/python/agent/src/omni/agent/core/memory/archiver.py
Responsible for flushing short-term memory (RAM) to long-term storage (Vector DB).
"""

import time
from typing import Any

import structlog

from omni.foundation.services.vector import get_vector_store

logger = structlog.get_logger(__name__)


class MemoryArchiver:
    """
    Background worker that syncs the agent's linear history into the Vector Database.

    Strategy: "Append-Only Log". We keep a cursor (last_archived_idx) and
    periodically flush new messages to the store.
    """

    def __init__(self, batch_size: int = 1, collection: str = "memory"):
        """
        Initialize the Memory Archiver.

        Args:
            batch_size: Number of messages to batch before flushing (default: 1).
            collection: VectorDB collection name for memories (default: "memory").
        """
        self.store = get_vector_store()
        self.batch_size = batch_size
        self.collection = collection
        self.last_archived_idx = 0

    async def archive_turn(self, messages: list[dict[str, Any]]) -> None:
        """
        Identify new messages and flush them to the vector store.

        Args:
            messages: Full message history from the agent loop.
        """
        total_msgs = len(messages)
        if total_msgs <= self.last_archived_idx:
            return

        # Identify New Messages
        new_msgs = messages[self.last_archived_idx :]

        # Convert to Vector Documents
        for msg in new_msgs:
            # Assign global unique sequential ID
            global_idx = self.last_archived_idx

            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))

            # Skip empty or very short messages
            if len(content) < 10:
                self.last_archived_idx = global_idx + 1
                continue

            # Build metadata for retrieval
            metadata = {
                "role": role,
                "step_index": global_idx,
                "timestamp": time.time(),
                "type": "episodic_memory",
                "content_length": len(content),
            }

            try:
                # Proper async await
                await self.store.add(content, metadata=metadata, collection=self.collection)

                logger.debug(
                    f"Archived message {global_idx}",
                    role=role,
                    content_preview=content[:50],
                )

            except Exception as e:
                logger.error(f"Failed to archive message {global_idx}", error=str(e))

            # Update cursor
            self.last_archived_idx = global_idx + 1

    def get_stats(self) -> dict[str, Any]:
        """Get archiver statistics."""
        return {
            "last_archived_idx": self.last_archived_idx,
            "collection": self.collection,
        }
