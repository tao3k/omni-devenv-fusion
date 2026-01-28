"""
pruner.py - Smart Context Trimming Strategies (Rust-Powered Facade)

Delegates core context pruning and token counting to the Rust `omni_core_rs` module
while maintaining API compatibility for the Python `ContextManager`.
"""

from enum import Enum
from typing import Any, Literal, List, Dict
import structlog
from pydantic import BaseModel
from omni_core_rs import PyContextPruner, count_tokens

logger = structlog.get_logger(__name__)


class ImportanceLevel(Enum):
    """Semantic importance levels for message prioritization."""

    CRITICAL = 3
    HIGH = 2
    MEDIUM = 1
    LOW = 0


class PruningConfig(BaseModel):
    """Configuration for context pruning behavior."""

    max_tokens: int = 128000
    retained_turns: int = 10
    preserve_system: bool = True
    preserve_recent: bool = True
    max_tool_output: int = 1000  # Added for Rust pruner
    strategy: Literal["truncate", "summarize"] = "truncate"


class ContextPruner:
    """
    Intelligent message pruner powered by Rust (omni_core_rs).
    """

    def __init__(self, config: PruningConfig | None = None):
        """
        Initialize the pruner with configuration.

        Args:
            config: PruningConfig instance. Uses defaults if None.
        """
        self.config = config or PruningConfig()

        # Initialize Rust engine
        # Map retained_turns to window_size
        window_size = self.config.retained_turns
        # Use config value or default to 1000 chars for tool output
        max_tool_output = getattr(self.config, "max_tool_output", 1000)

        try:
            self._engine = PyContextPruner(window_size, max_tool_output)
        except Exception as e:
            logger.error("Failed to initialize Rust PyContextPruner", error=str(e))
            self._engine = None

    def estimate_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        Estimate token count using Rust tokenizer (tiktoken via omni_core_rs).

        Args:
            messages: List of message dictionaries.

        Returns:
            Accurate token count using cl100k_base encoding.
        """
        if not messages:
            return 0

        total_tokens = 0
        try:
            for m in messages:
                content = str(m.get("content", ""))
                total_tokens += count_tokens(content)
        except Exception as e:
            logger.warning("Token counting failed, using heuristic", error=str(e))
            # Fallback: ~4 chars per token
            total_chars = sum(len(str(m.get("content", ""))) for m in messages)
            total_tokens = total_chars // 4

        return total_tokens

    def prune(
        self,
        messages: list[dict[str, Any]],
        summary_content: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Prune messages using Rust-native compression.

        Delegates to Rust implementation which handles:
        - System message preservation
        - Window-based retention
        - Tool output truncation/compression

        Args:
            messages: Full message history.
            summary_content: Optional summary to prepend.

        Returns:
            Pruned message list.
        """
        if not messages:
            return []

        if not self._engine:
            logger.warning("Rust engine not available, returning messages as-is")
            return messages

        try:
            # Call Rust engine
            # Rust compress handles: system preservation, window keeping, tool output truncation
            compressed = self._engine.compress(messages)

            # If summary provided, inject it after system messages
            if summary_content:
                insert_idx = 0
                for i, m in enumerate(compressed):
                    if m.get("role") != "system":
                        insert_idx = i
                        break

                summary_msg = {"role": "system", "content": f"[Context Summary]\n{summary_content}"}
                compressed.insert(insert_idx, summary_msg)

            # Post-compression check for token limits (compatibility with legacy tests)
            # Only if we have truncate strategy
            if self.config.strategy == "truncate" and compressed:
                # Check estimated tokens
                # (Note: estimate_tokens calls Rust count_tokens, so it's reasonably fast)
                current_tokens = self.estimate_tokens(compressed)

                # If strictly over limit, we must truncate further (older messages first)
                if current_tokens > self.config.max_tokens:
                    # Separate system and chat
                    system_msgs = [m for m in compressed if m.get("role") == "system"]
                    chat_msgs = [m for m in compressed if m.get("role") != "system"]

                    # Keep popping from start of chat until under limit
                    # We prioritize preserving system messages
                    while (
                        chat_msgs
                        and self.estimate_tokens(system_msgs + chat_msgs) > self.config.max_tokens
                    ):
                        chat_msgs.pop(0)

                    return system_msgs + chat_msgs

            return compressed

        except Exception as e:
            logger.error("Rust pruner failed, falling back to simple slicing", error=str(e))
            # Fallback: simple slice based on retention config
            retain_count = self.config.retained_turns * 2

            # Separate system messages
            system_msgs = [m for m in messages if m.get("role") == "system"]
            chat_msgs = [m for m in messages if m.get("role") != "system"]

            # Keep recent
            if len(chat_msgs) > retain_count:
                return system_msgs + chat_msgs[-retain_count:]
            return messages

    def segment(
        self,
        messages: list[dict[str, Any]],
        system_msgs: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Segment message history into (system, to_summarize, recent).
        Kept in Python for ContextManager compatibility.
        """
        if not messages:
            return (system_msgs or []), [], []

        if system_msgs is not None:
            extracted_system = system_msgs
        else:
            extracted_system = [m for m in messages if m.get("role") == "system"]

        chat_msgs = [m for m in messages if m.get("role") != "system"]

        if not chat_msgs:
            return extracted_system, [], []

        retain_count = self.config.retained_turns * 2

        if len(chat_msgs) > retain_count:
            recent_msgs = chat_msgs[-retain_count:]
            to_summarize = chat_msgs[:-retain_count]
        else:
            recent_msgs = chat_msgs
            to_summarize = []

        return extracted_system, to_summarize, recent_msgs

    def get_summary_candidates(
        self,
        messages: list[dict[str, Any]],
        max_candidates: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Identify messages for summarization.
        Kept in Python for ContextManager compatibility.
        """
        chat_msgs = [m for m in messages if m.get("role") != "system"]
        retain_count = self.config.retained_turns * 2

        older_msgs = chat_msgs[:-retain_count] if len(chat_msgs) > retain_count else []

        # Simple heuristic: return last few older messages
        return older_msgs[-max_candidates:]

    def classify_importance(self, message: dict[str, Any]) -> ImportanceLevel:
        """Classify a message by its semantic importance."""
        role = message.get("role", "").lower()
        content = str(message.get("content", "")).lower()

        # System messages are always critical
        if role == "system":
            return ImportanceLevel.CRITICAL

        # Tool definitions and final decisions are high importance
        if "tool_use" in message or "tool_result" in message:
            return ImportanceLevel.HIGH
        if content.startswith(("final", "result:", "decision:")):
            return ImportanceLevel.HIGH

        # Explicit reasoning markers suggest medium importance
        reasoning_markers = ["reasoning", "analysis", "step", "consider"]
        if any(marker in content for marker in reasoning_markers):
            return ImportanceLevel.MEDIUM

        # Default to low importance
        return ImportanceLevel.LOW
