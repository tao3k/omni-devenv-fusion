"""
agent/core/orchestrator/state.py
State Persistence for Orchestrator.

 GraphState persistence with StateCheckpointer.
 ContextCompressor for context overflow handling.
"""

from typing import Dict, Any, List
from dataclasses import dataclass

from agent.core.state import create_initial_state


@dataclass
class ContextCompressor:
    """Compress context when approaching token limits.

     Hierarchical Working Memory compression.

    This class provides intelligent context compression that:
    - Preserves system prompt and key decisions
    - Summarizes conversation history
    - Keeps tool outputs and their results
    - Removes redundant information
    """

    # Token thresholds for triggering compression
    WARNING_THRESHOLD: int = 8000  # Start warning at 8k tokens
    COMPRESS_THRESHOLD: int = 12000  # Compress at 12k tokens

    # Compression ratios
    HISTORY_COMPRESSION_RATIO: float = 0.3  # Keep 30% of history
    KEEP_LATEST_MESSAGES: int = 10  # Always keep last 10 messages

    def should_compress(self, message_count: int, estimated_tokens: int) -> bool:
        """Determine if compression is needed.

        Args:
            message_count: Number of messages in context
            estimated_tokens: Estimated token count

        Returns:
            True if compression is recommended
        """
        return estimated_tokens > self.COMPRESS_THRESHOLD

    def compress_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compress message history while preserving key information.

        Args:
            messages: List of conversation messages

        Returns:
            Compressed message list
        """
        if len(messages) <= self.KEEP_LATEST_MESSAGES:
            return messages

        # Always keep system messages
        system_messages = [m for m in messages if m.get("role") == "system"]

        # Keep recent messages
        recent_messages = messages[-self.KEEP_LATEST_MESSAGES :]

        # Summarize older messages
        older_messages = messages[len(system_messages) : -self.KEEP_LATEST_MESSAGES]

        if not older_messages:
            return system_messages + recent_messages

        # Create summary of older messages
        summary_content = self._summarize_message_batch(older_messages)

        summary_message = {
            "role": "system",
            "content": f"[Earlier conversation summarized: {summary_content}]",
            "_compressed": True,
            "_original_count": len(older_messages),
        }

        return system_messages + [summary_message] + recent_messages

    def compress_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Compress a GraphState for token limit management.

        Args:
            state: GraphState dictionary

        Returns:
            Compressed state
        """
        messages = state.get("messages", [])

        # Estimate tokens (rough approximation)
        estimated_tokens = self._estimate_tokens(messages)

        if not self.should_compress(len(messages), estimated_tokens):
            return state

        # Compress messages
        compressed_messages = self.compress_messages(messages)

        # Create compressed state
        compressed_state = dict(state)
        compressed_state["messages"] = compressed_messages
        compressed_state["_compression_applied"] = True
        compressed_state["_original_message_count"] = len(messages)
        compressed_state["_compressed_message_count"] = len(compressed_messages)

        return compressed_state

    def _summarize_message_batch(self, messages: list[dict[str, Any]]) -> str:
        """Summarize a batch of messages.

        Args:
            messages: List of messages to summarize

        Returns:
            Summary string
        """
        if not messages:
            return "no messages"

        # Count by type
        user_count = sum(1 for m in messages if m.get("role") == "user")
        assistant_count = sum(1 for m in messages if m.get("role") == "assistant")
        tool_count = sum(1 for m in messages if m.get("role") == "tool")

        topics = self._extract_topics(messages)

        return f"{user_count} user messages, {assistant_count} assistant responses, {tool_count} tool calls; topics: {', '.join(topics)}"

    def _extract_topics(self, messages: list[dict[str, Any]]) -> list[str]:
        """Extract main topics from messages.

        Args:
            messages: List of messages

        Returns:
            List of topic keywords
        """
        topics = set()

        for message in messages:
            content = message.get("content", "")
            # Simple keyword extraction
            if "file" in content.lower():
                topics.add("file operations")
            if "code" in content.lower() or "function" in content.lower():
                topics.add("code")
            if "test" in content.lower():
                topics.add("testing")
            if "error" in content.lower() or "fail" in content.lower():
                topics.add("errors")
            if "git" in content.lower() or "commit" in content.lower():
                topics.add("version control")

        return list(topics)[:5]  # Limit to 5 topics

    def _estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Rough token estimation for messages.

        Args:
            messages: List of messages

        Returns:
            Estimated token count
        """
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        # Rough estimate: 4 characters per token on average
        return total_chars // 4


def load_state(self) -> None:
    """Load GraphState from checkpointer on initialization."""
    import structlog

    logger = structlog.get_logger(__name__)

    saved_state = self._checkpointer.get(self._session_id)
    if saved_state:
        self._state = saved_state
        logger.bind(
            session_id=self._session_id,
            message_count=len(saved_state["messages"]),
            current_plan=saved_state.get("current_plan", "")[:50],
        ).info("state_resumed_from_checkpoint")
    else:
        self._state = create_initial_state()
        logger.bind(session_id=self._session_id).info("state_initialized")


def save_state(self, force: bool = False) -> None:
    """Save GraphState to checkpointer."""
    self._checkpointer.put(self._session_id, self._state)


def update_state(self, updates: dict[str, Any]) -> None:
    """Update GraphState with new values."""
    from agent.core.state import merge_state

    self._state = merge_state(self._state, updates)
    self._save_state()


def get_state(self) -> Dict[str, Any]:
    """Get current GraphState."""
    return self._state


def get_state_history(self, limit: int = 10) -> List[Dict[str, Any]]:
    """Get checkpoint history for current session."""
    return [
        {
            "checkpoint_id": cp.checkpoint_id,
            "timestamp": cp.timestamp,
            "state_keys": cp.state_keys,
            "size_bytes": cp.state_size_bytes,
        }
        for cp in self._checkpointer.get_history(self._session_id, limit)
    ]


def get_status(self) -> Dict[str, Any]:
    """Get Orchestrator status for debugging/monitoring."""
    return {
        "router_loaded": self.router is not None,
        "agents_available": list(self.agent_map.keys()),
        "inference_configured": self.inference is not None,
        "session_id": self._session_id,
        "state_messages": len(self._state.get("messages", [])),
        "state_plan": self._state.get("current_plan", "")[:100],
        "use_graph_mode": self.use_graph_mode,
    }


__all__ = [
    "load_state",
    "save_state",
    "update_state",
    "get_state",
    "get_state_history",
    "get_status",
]
