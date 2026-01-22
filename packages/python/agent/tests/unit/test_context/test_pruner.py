"""Tests for ContextPruner."""

import pytest
from omni.agent.core.context.pruner import (
    ContextPruner,
    PruningConfig,
    ImportanceLevel,
)


class TestPruningConfig:
    """Tests for PruningConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PruningConfig()
        assert config.max_tokens == 128000
        assert config.retained_turns == 10
        assert config.preserve_system is True
        assert config.preserve_recent is True
        assert config.strategy == "truncate"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = PruningConfig(
            max_tokens=64000,
            retained_turns=5,
            preserve_system=False,
            strategy="summarize",
        )
        assert config.max_tokens == 64000
        assert config.retained_turns == 5
        assert config.preserve_system is False
        assert config.strategy == "summarize"


class TestContextPruner:
    """Tests for ContextPruner class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pruner = ContextPruner()

    def test_empty_messages(self):
        """Test pruning empty message list."""
        result = self.pruner.prune([])
        assert result == []

    def test_estimate_tokens(self):
        """Test token estimation."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        tokens = self.pruner.estimate_tokens(messages)
        assert tokens > 0

    def test_classify_importance_system(self):
        """Test importance classification for system messages."""
        msg = {"role": "system", "content": "You are an AI."}
        importance = self.pruner.classify_importance(msg)
        assert importance == ImportanceLevel.CRITICAL

    def test_classify_importance_tool_use(self):
        """Test importance classification for tool messages."""
        msg = {"role": "user", "content": "", "tool_use": {"name": "test"}}
        importance = self.pruner.classify_importance(msg)
        assert importance == ImportanceLevel.HIGH

    def test_classify_importance_reasoning(self):
        """Test importance classification for reasoning messages."""
        msg = {"role": "assistant", "content": "Let me analyze this step by step."}
        importance = self.pruner.classify_importance(msg)
        assert importance == ImportanceLevel.MEDIUM

    def test_preserves_system_messages(self):
        """Test that system messages are always preserved."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "Assistant response"},
        ]
        result = self.pruner.prune(messages)
        assert result[0]["role"] == "system"
        assert len(result) == 3

    def test_prune_excess_messages(self):
        """Test pruning when messages exceed retain limit."""
        # Create pruner with small max_tokens to trigger pruning
        pruner = ContextPruner(PruningConfig(max_tokens=100, retained_turns=2))

        # Build many messages with longer content to exceed token limit
        messages = [{"role": "system", "content": "System prompt " * 50}]
        for i in range(20):
            messages.append({"role": "user", "content": f"User message {i} " * 50})
            messages.append({"role": "assistant", "content": f"Assistant response {i} " * 50})

        result = pruner.prune(messages)

        # Should have fewer messages due to token limit
        assert len(result) < len(messages)

    def test_get_summary_candidates(self):
        """Test identifying summary candidates."""
        pruner = ContextPruner(PruningConfig(retained_turns=2))

        messages = [{"role": "system", "content": "System"}]
        for i in range(10):
            messages.append({"role": "user", "content": f"User {i}"})
            messages.append({"role": "assistant", "content": f"Assistant {i}"})

        candidates = pruner.get_summary_candidates(messages, max_candidates=3)
        assert len(candidates) <= 3


class TestContextPrunerIntegration:
    """Integration tests for ContextPruner with various scenarios."""

    def test_under_limit_returns_all(self):
        """Test that messages under limit are returned unchanged."""
        pruner = ContextPruner(PruningConfig(max_tokens=100000))
        messages = [
            {"role": "system", "content": "Short system prompt"},
            {"role": "user", "content": "Short message"},
        ]
        result = pruner.prune(messages)
        assert len(result) == 2

    def test_with_summary_content(self):
        """Test summary insertion when pruning occurs."""
        # Use small token limit to trigger pruning
        pruner = ContextPruner(PruningConfig(max_tokens=100, retained_turns=1))

        messages = [{"role": "system", "content": "System prompt " * 20}]
        for i in range(5):
            messages.append({"role": "user", "content": f"User message {i} " * 20})
            messages.append({"role": "assistant", "content": f"Assistant response {i} " * 20})

        summary = "Conversation about project setup"
        result = pruner.prune(messages, summary_content=summary)

        # Check that result is smaller than input (pruning occurred)
        assert len(result) < len(messages)


class TestContextPrunerSegment:
    """Tests for ContextPruner.segment() method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pruner = ContextPruner(PruningConfig(retained_turns=2))

    def test_segment_empty_messages(self):
        """Test segmenting empty message list."""
        system, to_summarize, recent = self.pruner.segment([])
        assert system == []
        assert to_summarize == []
        assert recent == []

    def test_segment_only_system(self):
        """Test segmenting with only system messages."""
        messages = [
            {"role": "system", "content": "System 1"},
            {"role": "system", "content": "System 2"},
        ]
        system, to_summarize, recent = self.pruner.segment(messages)
        assert len(system) == 2
        assert to_summarize == []
        assert recent == []

    def test_segment_with_chat_messages(self):
        """Test segmenting with system and chat messages."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "User 1"},
            {"role": "assistant", "content": "Assistant 1"},
            {"role": "user", "content": "User 2"},
            {"role": "assistant", "content": "Assistant 2"},
            {"role": "user", "content": "User 3"},
            {"role": "assistant", "content": "Assistant 3"},
        ]
        system, to_summarize, recent = self.pruner.segment(messages)

        # System should have all system messages
        assert len(system) == 1
        assert system[0]["role"] == "system"

        # Recent should have last 4 messages (2 turns)
        assert len(recent) == 4
        assert recent[0]["content"] == "User 2"
        assert recent[-1]["content"] == "Assistant 3"

        # To-summarize should have middle messages
        assert len(to_summarize) == 2
        assert to_summarize[0]["content"] == "User 1"

    def test_segment_fewer_messages_than_retained(self):
        """Test segmenting when total messages < retained turns."""
        pruner = ContextPruner(PruningConfig(retained_turns=10))
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User 1"},
            {"role": "assistant", "content": "Assistant 1"},
        ]
        system, to_summarize, recent = pruner.segment(messages)

        assert len(system) == 1
        assert to_summarize == []
        assert len(recent) == 2

    def test_segment_returns_tuple_types(self):
        """Test that segment returns correct types."""
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User"},
        ]
        result = self.pruner.segment(messages)

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)
        assert isinstance(result[2], list)
