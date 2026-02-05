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

from omni_core_rs.tokenizer import (
    PyContextPruner as RustContextPruner,
    py_count_tokens,
    py_truncate,
    py_truncate_middle,
)

logger = logging.getLogger(__name__)


class PruningConfig:
    """Configuration for context pruning behavior.

    Attributes:
        max_tokens: Maximum tokens for total context.
        retained_turns: Number of message pairs to retain.
        max_tool_output: Maximum characters for tool outputs.
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        retained_turns: int = 4,
        max_tool_output: int = 500,
    ) -> None:
        """Initialize PruningConfig.

        Args:
            max_tokens: Maximum tokens for total context.
            retained_turns: Number of message pairs (user+assistant) to retain.
            max_tool_output: Maximum characters for tool outputs in archive.
        """
        self.max_tokens = max_tokens
        self.retained_turns = retained_turns
        self.max_tool_output = max_tool_output


class ContextPruner:
    """Rust-accelerated Context Pruner.

    Manages the context window budget using high-performance Rust tokenizer.
    Implements "Cognitive Re-anchoring" for AutoFixLoop recovery.

    This class REQUIRES Rust bindings (omni-core-rs) to function.
    Use `uv sync --reinstall-package omni-core-rs` after installation.

    Attributes:
        config: PruningConfig instance with pruning settings.
        rust_pruner: Rust-accelerated pruner instance.
    """

    def __init__(
        self,
        config: Optional[PruningConfig] = None,
        window_size: Optional[int] = None,
        max_tool_output: Optional[int] = None,
        max_context_tokens: Optional[int] = None,
    ) -> None:
        """Initialize the ContextPruner.

        Args:
            config: Optional PruningConfig object. If provided, other args are ignored.
            window_size: Number of message pairs (user+assistant) to keep.
            max_tool_output: Maximum characters for tool outputs in archive.
            max_context_tokens: Maximum tokens for total context.

        Raises:
            ImportError: If Rust bindings are not available.
        """
        # Validate Rust is available
        try:
            _ = py_count_tokens("test")
        except ImportError as e:
            raise ImportError(
                "Rust tokenizer bindings (omni-core-rs) are required. "
                "Install with: uv sync --reinstall-package omni-core-rs"
            ) from e

        # Create config if needed
        if config is not None:
            self.config = config
        else:
            self.config = PruningConfig(
                max_tokens=max_context_tokens if max_context_tokens is not None else 8000,
                retained_turns=window_size if window_size is not None else 4,
                max_tool_output=max_tool_output if max_tool_output is not None else 500,
            )

        # Use config values
        self.window_size = self.config.retained_turns
        self.max_tool_output = self.config.max_tool_output
        self.max_context_tokens = self.config.max_tokens

        # Initialize Rust pruner
        self.rust_pruner = RustContextPruner(self.window_size, self.max_tool_output)
        logger.info(
            f"ContextPruner initialized (Rust) window={self.window_size}, "
            f"max_tokens={self.max_context_tokens}"
        )

    def prune(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Prune messages based on token limit.

        Uses the default "recent" strategy which keeps system messages
        and the most recent N turns.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            Pruned list of messages.
        """
        # Count total tokens
        total_tokens = self.count_messages(messages)

        if total_tokens <= self.max_context_tokens:
            return messages

        # Strategy: Keep system messages + recent turns
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        # Calculate how many turns to keep
        system_token_count = sum(self.count_tokens(msg.get("content", "")) for msg in system_msgs)
        max_other_tokens = self.max_context_tokens - system_token_count

        # Estimate turns: ~1000 tokens per turn
        target_turns = max(1, max_other_tokens // 1000)

        # Keep last N turns (2 messages per turn: user + assistant)
        keep_count = min(target_turns * 2, len(other_msgs))
        pruned_other = other_msgs[-keep_count:]

        return system_msgs + pruned_other

    def get_summary_candidates(
        self, messages: List[Dict[str, str]], max_candidates: int = 5
    ) -> list[dict[str, Any]]:
        """Get messages that are good candidates for summarization.

        Args:
            messages: List of message dicts.
            max_candidates: Maximum number of candidates to return.

        Returns:
            List of message dicts with metadata.
        """
        # Look at older messages (not the most recent turn)
        candidates = []
        for i, msg in enumerate(messages[:-2]):  # Exclude last turn
            if msg.get("role") in ("user", "assistant"):
                content = msg.get("content", "")
                candidates.append(
                    {
                        "index": i,
                        "role": msg.get("role"),
                        "content": content[:200],
                        "tokens": self.count_tokens(content),
                    }
                )

        return candidates[-max_candidates:]

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using Rust.

        Args:
            text: The text to tokenize.

        Returns:
            Number of tokens (cl100k_base encoding).
        """
        return py_count_tokens(text)

    def count_messages(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens in a list of messages.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            Total token count.
        """
        return self.rust_pruner.count_message_tokens(
            [{"role": m.get("role", ""), "content": m.get("content", "")} for m in messages]
        )

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
        py_messages = [
            {"role": m.get("role", ""), "content": m.get("content", "")} for m in messages
        ]
        compressed = self.rust_pruner.compress(py_messages)
        return [{"role": m["role"], "content": m["content"]} for m in compressed]

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
        return py_truncate_middle(text, max_tokens)

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
        # Extract system messages (always keep)
        system_msgs = [m for m in messages if m.get("role") == "system"]

        # Create "Lesson Learned" summary
        lesson = (
            f"[AUTO-FIX RECOVERY]\n"
            f"Previous attempt failed: {error}\n"
            f"We have rolled back to a previous checkpoint.\n"
            f"Please analyze the error and try a different approach."
        )

        # Compress remaining messages
        other_msgs = [m for m in messages if m.get("role") != "system"]
        compressed = self.compress_messages(other_msgs)

        # Add recovery message at the start of user messages
        recovery_msg = {"role": "user", "content": lesson}

        # Check token count
        all_msgs = system_msgs + [recovery_msg] + compressed
        current_tokens = self.count_messages(all_msgs)

        if current_tokens > max_tokens:
            # Need additional pruning
            logger.info(
                f"Context still too large ({current_tokens} tokens), applying middle truncation"
            )
            # Truncate the middle of the compressed messages
            compressed_content = "\n".join(m.get("content", "") for m in compressed)
            truncated_content = self.truncate_middle(
                compressed_content,
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

    Raises:
        ImportError: If Rust bindings are not available.
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
