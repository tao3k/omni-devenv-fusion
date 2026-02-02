"""Context Pruner - Rust-accelerated Context Window Management.

This module provides high-performance token counting and context pruning
for LangGraph workflows using the Rust omni-tokenizer bindings.

Architecture:
    - Rust (omni-tokenizer): Token counting, truncation, message compression
    - Python: Integration with LangGraph workflows

Features:
    - 20-100x faster token counting than Python tiktoken
    - Smart message compression (keep system + recent, truncate tool outputs)
    - Middle-out truncation for long texts
    - AutoFix integration for memory-efficient recovery

Example:
    >>> from omni.agent.core.context.pruner import ContextPruner
    >>> from omni_core_rs.tokenizer import PyContextPruner
    >>>
    >>> # Use Rust-accelerated pruner
    >>> pruner = ContextPruner(window_size=4, max_tool_output=500)
    >>> compressed = pruner.compress(messages)
    >>>
    >>> # Count tokens
    >>> from omni_core_rs import py_count_tokens
    >>> count = py_count_tokens("Hello, world!")
"""

import logging
from typing import Any, Dict, List, Optional

try:
    from omni_core_rs.tokenizer import (
        PyContextPruner as RustContextPruner,
        py_count_tokens,
        py_truncate,
        py_truncate_middle,
    )

    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    logging.warning("Rust tokenizer bindings not available, falling back to estimation")

logger = logging.getLogger(__name__)


class ContextPruner:
    """Rust-accelerated Context Pruner.

    Manages the context window budget using high-performance Rust tokenizer.
    Implements "Cognitive Re-anchoring" for AutoFixLoop recovery.

    Attributes:
        window_size: Number of message pairs to keep in working memory.
        max_tool_output: Maximum characters for tool outputs in archive.
        rust_pruner: Rust-accelerated pruner instance (if available).
    """

    def __init__(
        self,
        window_size: int = 4,
        max_tool_output: int = 500,
        max_context_tokens: int = 8000,
    ) -> None:
        """Initialize the ContextPruner.

        Args:
            window_size: Number of message pairs (user+assistant) to keep.
            max_tool_output: Maximum characters for tool outputs in archive.
            max_context_tokens: Maximum tokens for total context.
        """
        self.window_size = window_size
        self.max_tool_output = max_tool_output
        self.max_context_tokens = max_context_tokens

        if RUST_AVAILABLE:
            self.rust_pruner = RustContextPruner(window_size, max_tool_output)
            logger.info(f"ContextPruner initialized with Rust acceleration (window={window_size})")
        else:
            self.rust_pruner = None
            logger.warning("ContextPruner falling back to estimation mode")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using Rust.

        Args:
            text: The text to tokenize.

        Returns:
            Number of tokens (cl100k_base encoding).
        """
        if RUST_AVAILABLE:
            return py_count_tokens(text)
        # Fallback: rough estimation (~4 chars per token)
        return len(text) // 4

    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens in a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            Total token count.
        """
        if RUST_AVAILABLE and self.rust_pruner:
            # Convert to format expected by Rust
            py_messages = [msg.copy() for msg in messages]
            return self.rust_pruner.count_message_tokens(py_messages)
        # Fallback
        return sum(self.count_tokens(msg.get("content", "")) for msg in messages)

    def compress_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Compress message history while preserving important information.

        Strategy:
        1. Always keep system messages
        2. Keep last N*2 messages (user+assistant pairs) as "working memory"
        3. Truncate tool outputs in older "archive" messages

        Args:
            messages: List of message dicts.

        Returns:
            Compressed list of message dicts.
        """
        if RUST_AVAILABLE and self.rust_pruner:
            # Use Rust pruner
            py_messages = [msg.copy() for msg in messages]
            compressed = self.rust_pruner.compress(py_messages)
            return [dict(m) for m in compressed]

        # Fallback: Simple Python implementation
        return self._python_compress(messages)

    def _python_compress(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Python fallback for message compression."""
        if not messages:
            return []

        # 1. Identify System Messages (Always Keep)
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        # 2. Determine Safety Zone
        safe_count = self.window_size * 2

        if len(other_msgs) <= safe_count:
            return messages

        # 3. Process Archive (Compress Tool Outputs)
        archive = other_msgs[:-safe_count]
        working = other_msgs[-safe_count:]

        processed_archive = []
        for msg in archive:
            new_msg = msg.copy()
            if msg.get("role") in ("tool", "function"):
                if len(new_msg.get("content", "")) > self.max_tool_output:
                    preview = new_msg["content"][: self.max_tool_output]
                    removed_len = len(new_msg["content"]) - self.max_tool_output
                    new_msg["content"] = (
                        f"{preview}\n[SYSTEM NOTE: Output truncated. {removed_len} chars hidden.]"
                    )
            processed_archive.append(new_msg)

        # 4. Reassemble
        return system_msgs + processed_archive + working

    def truncate_middle(self, text: str, max_tokens: int) -> str:
        """Truncate text preserving head and tail.

        Useful for long system prompts where you want to keep
        the beginning (instructions) and end (recent context).

        Args:
            text: The text to truncate.
            max_tokens: Maximum tokens allowed.

        Returns:
            Truncated text.
        """
        if RUST_AVAILABLE:
            return py_truncate_middle(text, max_tokens)

        # Fallback
        tokens = self.count_tokens(text)
        if tokens <= max_tokens:
            return text

        # Strings are already sequences of characters in Python
        chars = list(text)
        total_chars = len(chars)
        keep_first = (max_tokens * 40) / 100
        split_point = int(total_chars * keep_first / tokens)
        first = "".join(chars[:split_point])
        last = "".join(chars[split_point:])
        return f"{first}\n\n[... truncated ...]\n\n{last}"

    def prune_for_retry(
        self,
        messages: List[Dict[str, str]],
        error: str,
        max_tokens: int = 6000,
    ) -> List[Dict[str, str]]:
        """Prune messages for AutoFix retry.

        Creates a compressed context for retrying after failure.
        Includes a "Lesson Learned" summary instead of full error trace.

        Args:
            messages: Current message history.
            error: The error that occurred.
            max_tokens: Maximum tokens for retry context.

        Returns:
            Pruned message list for retry.
        """
        # 1. Extract system messages (always keep)
        system_msgs = [m for m in messages if m.get("role") == "system"]

        # 2. Create "Lesson Learned" summary
        lesson = (
            f"[AUTO-FIX RECOVERY]\n"
            f"Previous attempt failed: {error}\n"
            f"We have rolled back to a previous checkpoint.\n"
            f"Please analyze the error and try a different approach."
        )

        # 3. Compress remaining messages
        other_msgs = [m for m in messages if m.get("role") != "system"]
        compressed = self.compress_messages(other_msgs)

        # 4. Add recovery message at the start of user messages
        recovery_msg = {"role": "user", "content": lesson}

        # 5. Check token count
        all_msgs = system_msgs + [recovery_msg] + compressed
        current_tokens = self.count_messages(all_msgs)

        if current_tokens > max_tokens:
            # Need additional pruning
            logger.info(
                f"Context still too large ({current_tokens} tokens), applying middle truncation"
            )
            # Truncate the middle of the compressed messages
            truncated_content = self.truncate_middle(
                "\n".join(m.get("content", "") for m in compressed),
                max_tokens - self.count_messages(system_msgs) - self.count_tokens(lesson) - 500,
            )
            compressed = [{"role": "compressed", "content": truncated_content}]

        return system_msgs + [recovery_msg] + compressed

    def estimate_compression_ratio(self, messages: List[Dict[str, str]]) -> float:
        """Estimate the compression ratio achieved.

        Args:
            messages: List of messages.

        Returns:
            Ratio of original tokens to compressed tokens.
        """
        original = self.count_messages(messages)
        if original == 0:
            return 1.0

        compressed = self.compress_messages(messages)
        compressed_tokens = self.count_messages(compressed)

        return original / compressed_tokens if compressed_tokens > 0 else 1.0


def create_pruner_for_model(
    model: str = "gpt-4o",
    window_size: Optional[int] = None,
) -> ContextPruner:
    """Factory function to create a pruner optimized for a specific model.

    Args:
        model: The model name (e.g., "gpt-4o", "gpt-3.5-turbo").
        window_size: Override for window size.

    Returns:
        Configured ContextPruner.
    """
    # Model-specific configurations
    model_configs = {
        "gpt-4o": {"window": 6, "max_tokens": 120000},
        "gpt-4-turbo": {"window": 6, "max_tokens": 128000},
        "gpt-4": {"window": 4, "max_tokens": 8192},
        "gpt-3.5-turbo": {"window": 8, "max_tokens": 16384},
    }

    config = model_configs.get(model, {"window": 4, "max_tokens": 8000})
    ws = window_size or config["window"]
    max_tokens = config["max_tokens"]

    return ContextPruner(window_size=ws, max_context_tokens=max_tokens)
