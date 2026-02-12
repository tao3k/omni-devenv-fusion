"""Tests for ContextPruner - Rust-accelerated context window management."""

import pytest

from omni.agent.core.context.pruner import ContextPruner, create_pruner_for_model


class TestContextPruner:
    """Tests for ContextPruner class."""

    def test_empty_messages(self):
        """Test pruning empty message list."""
        pruner = ContextPruner()
        result = pruner.compress_messages([])
        assert result == []

    def test_single_message(self):
        """Test compressing single message."""
        pruner = ContextPruner()
        messages = [{"role": "user", "content": "Hello"}]
        result = pruner.compress_messages(messages)
        assert len(result) == 1
        assert result[0]["content"] == "Hello"

    def test_preserves_system_messages(self):
        """Test that system messages are always preserved."""
        pruner = ContextPruner()
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Assistant response"},
        ]
        result = pruner.compress_messages(messages)
        assert result[0]["role"] == "system"
        assert len(result) == 3

    def test_truncates_tool_outputs_in_archive(self):
        """Test that tool outputs in archive are truncated."""
        pruner = ContextPruner(window_size=2, max_tool_output=50)
        long_output = "A" * 100  # 100 character tool output

        messages = [
            {"role": "system", "content": "System"},
            {"role": "tool", "content": long_output, "tool_call_id": "call_1"},
            {"role": "user", "content": "User 1"},
            {"role": "assistant", "content": "Assistant 1"},
            {"role": "user", "content": "User 2"},
            {"role": "assistant", "content": "Assistant 2"},
        ]
        result = pruner.compress_messages(messages)

        # The tool message should be truncated
        tool_msg = [m for m in result if m.get("role") == "tool"][0]
        # The truncated message includes preview + system note.
        # Ensure we have truncation marker and avoid runaway growth.
        assert len(tool_msg["content"]) <= 160
        assert "truncated" in tool_msg["content"]
        assert "hidden" in tool_msg["content"]

    def test_preserves_recent_messages(self):
        """Test that recent messages are preserved."""
        pruner = ContextPruner(window_size=2)
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Old user"},
            {"role": "assistant", "content": "Old assistant"},
            {"role": "user", "content": "Recent user"},
            {"role": "assistant", "content": "Recent assistant"},
        ]
        result = pruner.compress_messages(messages)

        # Recent messages should be preserved
        recent_contents = [m["content"] for m in result if m["role"] == "user"]
        assert "Recent user" in recent_contents

    def test_count_tokens(self):
        """Test token counting."""
        pruner = ContextPruner()
        count = pruner.count_tokens("Hello, world!")
        assert count > 0

    def test_count_messages(self):
        """Test counting tokens in messages."""
        pruner = ContextPruner()
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        tokens = pruner.count_messages(messages)
        assert tokens > 0

    def test_truncate_middle(self):
        """Test middle truncation."""
        pruner = ContextPruner()
        long_text = "A" * 1000
        truncated = pruner.truncate_middle(long_text, max_tokens=50)
        # The output should contain truncation markers
        assert "..." in truncated or "truncated" in truncated
        # The output should be different from the original
        assert truncated != long_text

    def test_estimate_compression_ratio(self):
        """Test compression ratio estimation."""
        pruner = ContextPruner()
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User"},
        ]
        ratio = pruner.estimate_compression_ratio(messages)
        assert ratio >= 1.0


class TestPruneForRetry:
    """Tests for prune_for_retry method (AutoFix integration)."""

    def test_prune_for_retry_basic(self):
        """Test basic prune for retry functionality."""
        pruner = ContextPruner()
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User message 1"},
            {"role": "assistant", "content": "Assistant response 1"},
            {"role": "user", "content": "User message 2"},
            {"role": "assistant", "content": "Assistant response 2"},
        ]
        error = "Some error occurred"
        result = pruner.prune_for_retry(messages, error)

        # Should include system messages
        assert any(m.get("role") == "system" for m in result)

        # Should include recovery message
        assert any("AUTO-FIX RECOVERY" in m.get("content", "") for m in result)

    def test_prune_for_retry_adds_lesson_learned(self):
        """Test that prune_for_retry adds lesson learned summary."""
        pruner = ContextPruner()
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Test"},
        ]
        error = "ValueError: invalid input"
        result = pruner.prune_for_retry(messages, error)

        # Check that the error is mentioned in the recovery message
        recovery_msg = [m for m in result if "AUTO-FIX RECOVERY" in m.get("content", "")][0]
        assert "ValueError" in recovery_msg["content"] or "invalid input" in recovery_msg["content"]

    def test_prune_for_retry_empty_messages(self):
        """Test prune_for_retry with empty messages."""
        pruner = ContextPruner()
        result = pruner.prune_for_retry([], "error")
        # Should still include recovery message
        assert len(result) >= 1
        assert "AUTO-FIX RECOVERY" in result[0].get("content", "")


class TestCreatePrunerForModel:
    """Tests for create_pruner_for_model factory."""

    def test_gpt_4o_config(self):
        """Test creating pruner for gpt-4o."""
        pruner = create_pruner_for_model("gpt-4o")
        assert pruner.window_size == 6
        assert pruner.max_context_tokens == 120000

    def test_gpt_4_config(self):
        """Test creating pruner for gpt-4."""
        pruner = create_pruner_for_model("gpt-4")
        assert pruner.window_size == 4
        assert pruner.max_context_tokens == 8192

    def test_gpt_3_5_turbo_config(self):
        """Test creating pruner for gpt-3.5-turbo."""
        pruner = create_pruner_for_model("gpt-3.5-turbo")
        assert pruner.window_size == 8
        assert pruner.max_context_tokens == 16384

    def test_unknown_model_defaults(self):
        """Test that unknown models get default config."""
        pruner = create_pruner_for_model("unknown-model")
        assert pruner.window_size == 4
        assert pruner.max_context_tokens == 8000

    def test_custom_window_size_override(self):
        """Test overriding window size."""
        pruner = create_pruner_for_model("gpt-4o", window_size=10)
        assert pruner.window_size == 10
