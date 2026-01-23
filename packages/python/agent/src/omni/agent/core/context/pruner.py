"""
pruner.py - Smart Context Trimming Strategies

Implements the "Token Diet" philosophy:
1. Preserve System Context (Identity)
2. Preserve Recent Short-term Memory (Continuity)
3. Prune/Summarize Middle Context (Efficiency)

Future Enhancements:
- Token counting via tiktoken
- Semantic importance scoring
- RAG-backed summary generation
"""

from typing import List, Dict, Any, Literal, Tuple
from dataclasses import dataclass
from enum import Enum


class ImportanceLevel(Enum):
    """Semantic importance levels for message prioritization."""

    CRITICAL = 3  # System prompts, tool definitions
    HIGH = 2  # User intent, final decisions
    MEDIUM = 1  # Reasoning, intermediate steps
    LOW = 0  # Error logs, trivial acknowledgments


@dataclass
class PruningConfig:
    """Configuration for context pruning behavior."""

    max_tokens: int = 128000
    retained_turns: int = 10
    preserve_system: bool = True
    preserve_recent: bool = True
    strategy: Literal["truncate", "summarize"] = "truncate"


class ContextPruner:
    """
    Intelligent message pruner to keep token usage within limits
    while maintaining conversation coherence.
    """

    def __init__(self, config: PruningConfig | None = None):
        """
        Initialize the pruner with configuration.

        Args:
            config: PruningConfig instance. Uses defaults if None.
        """
        self.config = config or PruningConfig()

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """
        Estimate token count for messages.

        Simple heuristic: ~4 chars per token average.
        Future: Replace with tiktoken for accurate counting.

        Args:
            messages: List of message dictionaries.

        Returns:
            Estimated token count.
        """
        if not messages:
            return 0

        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        return total_chars // 4

    def classify_importance(self, message: Dict[str, Any]) -> ImportanceLevel:
        """
        Classify a message by its semantic importance.

        Args:
            message: A single message dictionary.

        Returns:
            ImportanceLevel enum value.
        """
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

    def prune(
        self,
        messages: List[Dict[str, Any]],
        summary_content: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Prune messages to fit within context window limits.

        Strategy:
        1. Always preserve System messages if configured.
        2. Keep the last N complete turns (user+assistant pairs).
        3. If still over limit, truncate oldest non-system messages.
        4. Optionally prepend a summary of pruned content.

        Args:
            messages: Full message history.
            summary_content: Optional summary to prepend if pruning occurred.

        Returns:
            Pruned message list ready for LLM inference.
        """
        if not messages:
            return []

        # Estimate current token usage
        current_tokens = self.estimate_tokens(messages)

        # If under limit, return as-is
        if current_tokens <= self.config.max_tokens:
            return messages.copy()

        # Step 1: Separate System messages (preserved)
        system_msgs = [m for m in messages if m.get("role") == "system"]
        chat_msgs = [m for m in messages if m.get("role") != "system"]

        # Step 2: Keep recent turns
        if self.config.preserve_recent:
            retain_count = self.config.retained_turns * 2  # user + assistant
            recent_msgs = chat_msgs[-retain_count:]
            older_msgs = chat_msgs[:-retain_count]
        else:
            recent_msgs = []
            older_msgs = chat_msgs

        # Step 3: If still over limit, prune older messages by importance
        result_msgs: List[Dict[str, Any]] = []

        if self.config.preserve_system:
            result_msgs.extend(system_msgs)

        # Add summary if provided and we pruned something
        if summary_content and older_msgs:
            summary_msg = {
                "role": "system",
                "content": f"[Context Summary: {len(older_msgs)} messages summarized]\n{summary_content}",
            }
            result_msgs.append(summary_msg)

        # Add recent messages
        result_msgs.extend(recent_msgs)

        # Step 4: Final token check - if still over, truncate from oldest
        # Find the start index for chat messages (after system + summary)
        chat_start = len(system_msgs)
        if summary_content and older_msgs:
            chat_start += 1

        while (
            self.estimate_tokens(result_msgs) > self.config.max_tokens
            and len(result_msgs) > chat_start + 2
        ):
            # Remove oldest chat message (after system/summary)
            result_msgs.pop(chat_start)

        return result_msgs

    def get_summary_candidates(
        self,
        messages: List[Dict[str, Any]],
        max_candidates: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Identify messages that are good candidates for summarization.

        Returns messages that are:
        - Not system messages
        - Not in the recent N turns
        - Medium or higher importance

        Args:
            messages: Full message history.
            max_candidates: Maximum number of candidates to return.

        Returns:
            List of candidate messages for summarization.
        """
        chat_msgs = [m for m in messages if m.get("role") != "system"]

        # Skip recent messages
        retain_count = self.config.retained_turns * 2
        older_msgs = chat_msgs[:-retain_count] if len(chat_msgs) > retain_count else []

        if not older_msgs:
            return []

        # Score by importance and position
        candidates = []
        for msg in older_msgs:
            importance = self.classify_importance(msg)
            if importance.value >= ImportanceLevel.MEDIUM.value:
                candidates.append(msg)

        return candidates[:max_candidates]

    def segment(
        self,
        messages: List[Dict[str, Any]],
        system_msgs: List[Dict[str, Any]] | None = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Segment message history into three distinct parts for compression.

        This method splits messages into:
        1. System Messages (immutable - identity, instructions)
        2. To-Summarize (old context - candidates for compression)
        3. Recent Messages (short-term memory - preserved)

        Args:
            messages: Chat message history (user/assistant roles only).
            system_msgs: Optional system messages. If None, extracted from messages.

        Returns:
            Tuple of (system_msgs, to_summarize, recent_msgs):
            - system_msgs: All messages with role="system" (or provided system_msgs)
            - to_summarize: Chat messages before the recent window
            - recent_msgs: Last N turns of chat messages
        """
        if not messages:
            return (system_msgs or []), [], []

        # Use provided system_msgs or extract from messages (backward compat)
        if system_msgs is not None:
            extracted_system = system_msgs
        else:
            extracted_system = [m for m in messages if m.get("role") == "system"]

        # Chat messages are those without system role
        chat_msgs = [m for m in messages if m.get("role") != "system"]

        if not chat_msgs:
            return extracted_system, [], []

        # Calculate retention for recent messages
        retain_count = self.config.retained_turns * 2  # user + assistant pairs

        # Recent messages: last N complete turns
        recent_msgs = chat_msgs[-retain_count:] if len(chat_msgs) > retain_count else chat_msgs

        # To-summarize: everything before the recent window
        to_summarize = chat_msgs[:-retain_count] if len(chat_msgs) > retain_count else []

        return extracted_system, to_summarize, recent_msgs
