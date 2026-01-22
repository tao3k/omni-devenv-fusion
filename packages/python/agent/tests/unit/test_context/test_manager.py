"""Tests for ContextManager."""

import pytest
from omni.agent.core.context.manager import ContextManager, Turn
from omni.agent.core.context.pruner import ContextPruner, PruningConfig


class TestTurn:
    """Tests for Turn dataclass."""

    def test_turn_creation(self):
        """Test creating a turn with messages."""
        user_msg = {"role": "user", "content": "Hello"}
        assistant_msg = {"role": "assistant", "content": "Hi!"}
        turn = Turn(user_message=user_msg, assistant_message=assistant_msg)

        assert turn.user_message == user_msg
        assert turn.assistant_message == assistant_msg
        assert turn.metadata == {}

    def test_turn_to_dict(self):
        """Test turn serialization."""
        turn = Turn(
            user_message={"role": "user", "content": "Test"},
            assistant_message={"role": "assistant", "content": "Result"},
        )
        data = turn.to_dict()

        assert "user" in data
        assert "assistant" in data
        assert "timestamp" in data
        assert data["user"]["content"] == "Test"


class TestContextManager:
    """Tests for ContextManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pruner = ContextManager(pruner=None)
        self.pruner_with_config = ContextManager(
            pruner=ContextPruner(PruningConfig(retained_turns=3))
        )

    def test_empty_initialization(self):
        """Test empty context manager."""
        ctx = ContextManager()
        assert ctx.turn_count == 0
        assert len(ctx.turns) == 0

    def test_add_system_message(self):
        """Test adding system messages."""
        self.pruner.add_system_message("You are an AI assistant.")
        assert len(self.pruner.system_prompts) == 1
        assert self.pruner.system_prompts[0]["content"] == "You are an AI assistant."

    def test_add_user_message(self):
        """Test adding user message starts a turn."""
        self.pruner.add_user_message("Hello, world!")
        assert len(self.pruner.turns) == 1
        assert self.pruner.turns[0].user_message["content"] == "Hello, world!"

    def test_update_assistant_message(self):
        """Test updating assistant message."""
        self.pruner.add_user_message("Question?")
        self.pruner.update_last_assistant("Answer!")
        assert self.pruner.turns[0].assistant_message["content"] == "Answer!"
        assert self.pruner.turn_count == 1

    def test_add_turn_complete(self):
        """Test adding a complete turn."""
        self.pruner.add_turn("User message", "Assistant response")
        assert len(self.pruner.turns) == 1
        assert self.pruner.turn_count == 1

    def test_add_turn_multiple(self):
        """Test adding multiple turns."""
        self.pruner.add_turn("User 1", "Assistant 1")
        self.pruner.add_turn("User 2", "Assistant 2")
        assert len(self.pruner.turns) == 2
        assert self.pruner.turn_count == 2

    def test_get_active_context_pruned(self):
        """Test getting pruned context."""
        self.pruner.add_system_message("System")
        self.pruner.add_turn("User 1", "Assistant 1")
        self.pruner.add_turn("User 2", "Assistant 2")
        self.pruner.add_turn("User 3", "Assistant 3")

        context = self.pruner.get_active_context(strategy="pruned")
        # Should include system + some chat messages
        assert len(context) >= 1  # At least system

    def test_get_active_context_recent(self):
        """Test getting recent context only."""
        self.pruner.add_system_message("System")
        for i in range(10):
            self.pruner.add_turn(f"User {i}", f"Assistant {i}")

        context = self.pruner.get_active_context(strategy="recent")
        # Should include system + last N turns
        assert context[0]["role"] == "system"
        # Should have limited number of messages
        max_msgs = 1 + (self.pruner.pruner.config.retained_turns * 2)
        assert len(context) <= max_msgs

    def test_get_active_context_full(self):
        """Test getting full context."""
        self.pruner.add_system_message("System")
        self.pruner.add_turn("User 1", "Assistant 1")

        context = self.pruner.get_active_context(strategy="full")
        assert len(context) == 3  # system + user + assistant

    def test_clear(self):
        """Test clearing context."""
        self.pruner.add_system_message("System")
        self.pruner.add_turn("User", "Assistant")
        self.pruner.clear()

        assert len(self.pruner.turns) == 0
        assert self.pruner.turn_count == 0

    def test_snapshot_and_restore(self):
        """Test context serialization and deserialization."""
        # Create context with data
        self.pruner.add_system_message("Important system prompt")
        self.pruner.add_turn("User message", "Assistant response")

        # Take snapshot
        snapshot = self.pruner.snapshot()

        # Create new manager and restore
        new_ctx = ContextManager()
        new_ctx.load_snapshot(snapshot)

        assert new_ctx.turn_count == 1
        assert len(new_ctx.system_prompts) == 1
        assert new_ctx.turns[0].user_message["content"] == "User message"

    def test_stats(self):
        """Test context statistics."""
        self.pruner.add_system_message("System")
        self.pruner.add_turn("User", "Assistant")

        stats = self.pruner.stats()
        assert "turn_count" in stats
        assert "system_messages" in stats
        assert "total_messages" in stats
        assert "estimated_tokens" in stats
        assert stats["turn_count"] == 1

    def test_error_on_update_without_user(self):
        """Test that updating assistant without user raises error."""
        ctx = ContextManager()
        with pytest.raises(RuntimeError, match="No active turn"):
            ctx.update_last_assistant("Answer")

    def test_prune_with_summary(self):
        """Test pruning with summary insertion."""
        # Use manager with low retain turns
        ctx = ContextManager(pruner=ContextPruner(PruningConfig(retained_turns=2)))

        # Add many turns
        for i in range(10):
            ctx.add_turn(f"User {i}", f"Assistant {i}")

        initial_count = len(ctx.turns)

        # Prune with summary
        pruned_count = ctx.prune_with_summary("Conversation about various topics")

        # Should have pruned some turns (keep only 2)
        assert len(ctx.turns) <= 2
        assert len(ctx.system_prompts) > 0  # Summary added


class TestContextManagerCompression:
    """Tests for ContextManager compression functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ctx = ContextManager(pruner=ContextPruner(PruningConfig(retained_turns=2)))

    def test_summary_attribute_initialized(self):
        """Test that summary attribute is initialized to None."""
        ctx = ContextManager()
        assert ctx.summary is None

    def test_segment(self):
        """Test ContextManager.segment() method."""
        self.ctx.add_system_message("System prompt")
        for i in range(5):
            self.ctx.add_turn(f"User {i}", f"Assistant {i}")

        system, to_summarize, recent = self.ctx.segment()

        # System should have system messages
        assert len(system) == 1
        assert system[0]["role"] == "system"

        # Recent should have last 4 messages (2 turns)
        assert len(recent) == 4

        # To-summarize should have remaining
        assert len(to_summarize) == 6  # 5 user + 5 assistant = 10, minus 4 recent = 6

    def test_segment_empty_context(self):
        """Test segmenting empty context."""
        system, to_summarize, recent = self.ctx.segment()
        assert system == []
        assert to_summarize == []
        assert recent == []

    def test_simple_summarize(self):
        """Test _simple_summarize helper method."""
        messages = [
            {
                "role": "user",
                "content": "This is a very long user message that should be summarized properly",
            },
            {
                "role": "assistant",
                "content": "This is a very long assistant response that contains important information about the task",
            },
        ]

        summary = self.ctx._simple_summarize(messages)

        assert len(summary) > 0
        assert "summarized" in summary.lower() or "user" in summary.lower()

    def test_simple_summarize_empty(self):
        """Test _simple_summarize with empty messages."""
        summary = self.ctx._simple_summarize([])
        assert summary == ""

    def test_simple_summarize_short_messages(self):
        """Test _simple_summarize skips very short messages."""
        messages = [
            {"role": "user", "content": "Hi"},  # Too short, should be skipped
            {
                "role": "assistant",
                "content": "This is a much longer response with meaningful content",
            },
        ]

        summary = self.ctx._simple_summarize(messages)

        # Should not include the short message
        assert "Hi" not in summary

    def test_messages_to_trajectory(self):
        """Test _messages_to_trajectory helper method."""
        messages = [
            {"role": "user", "content": "User message one"},
            {"role": "assistant", "content": "Assistant response one"},
            {"role": "user", "content": "User message two"},
        ]

        trajectory = self.ctx._messages_to_trajectory(messages)

        assert len(trajectory) == 3
        assert trajectory[0]["type"] == "goal"
        assert trajectory[1]["type"] == "decision"
        assert trajectory[2]["type"] == "goal"

    def test_extract_summary_content(self):
        """Test _extract_summary_content helper method."""
        markdown = """# Session: test

Date: 2024-01-01
Goal: Test goal

## Summary

This is the summary content with key points about the conversation.

## Decision Path

### 1. First Decision
Content of first decision
"""

        summary = self.ctx._extract_summary_content(markdown)

        assert "summary content" in summary.lower() or "key points" in summary.lower()

    def test_apply_compression(self):
        """Test _apply_compression method."""
        self.ctx.add_system_message("System prompt")
        for i in range(5):
            self.ctx.add_turn(f"User {i}", f"Assistant {i}")

        # Set a summary
        self.ctx.summary = "This is a test summary"

        # Store counts before compression
        old_turn_count = len(self.ctx.turns)

        # Apply compression
        self.ctx._apply_compression(
            system_msgs=self.ctx.system_prompts[:1],
            recent_msgs=self.ctx.get_active_context(strategy="full")[-4:],
        )

        # Should have summary in system prompts
        has_summary = any(msg.get("_is_summary", False) for msg in self.ctx.system_prompts)
        assert has_summary

    def test_clear_clears_summary(self):
        """Test that clear() also clears the summary."""
        self.ctx.add_system_message("System")
        self.ctx.add_turn("User", "Assistant")
        self.ctx.summary = "Some summary"

        self.ctx.clear()

        assert self.ctx.summary is None

    def test_snapshot_includes_summary(self):
        """Test that snapshot() includes summary."""
        self.ctx.add_system_message("System")
        self.ctx.add_turn("User", "Assistant")
        self.ctx.summary = "Test summary"

        snapshot = self.ctx.snapshot()

        assert "summary" in snapshot
        assert snapshot["summary"] == "Test summary"

    def test_load_snapshot_restores_summary(self):
        """Test that load_snapshot() restores summary."""
        self.ctx.load_snapshot(
            {
                "system_prompts": [{"role": "system", "content": "System"}],
                "turns": [],
                "turn_count": 0,
                "summary": "Restored summary",
                "pruner_config": {"max_tokens": 128000, "retained_turns": 10},
            }
        )

        assert self.ctx.summary == "Restored summary"

    def test_stats_includes_has_summary(self):
        """Test that stats() includes has_summary flag."""
        self.ctx.add_system_message("System")
        self.ctx.add_turn("User", "Assistant")

        stats = self.ctx.stats()
        assert "has_summary" in stats
        assert stats["has_summary"] is False

        self.ctx.summary = "Test summary"
        stats = self.ctx.stats()
        assert stats["has_summary"] is True


class TestContextManagerAsyncCompress:
    """Tests for async ContextManager.compress() method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.ctx = ContextManager(pruner=ContextPruner(PruningConfig(retained_turns=2)))

    @pytest.mark.asyncio
    async def test_compress_returns_false_when_nothing_to_summarize(self):
        """Test compress() returns False when no messages to summarize."""
        self.ctx.add_system_message("System")
        self.ctx.add_turn("User", "Assistant")  # Only 1 turn, less than retained_turns

        result = await self.ctx.compress()

        assert result is False

    @pytest.mark.asyncio
    async def test_compress_creates_summary(self):
        """Test compress() creates a summary using fallback."""
        # Add more turns than retained_turns
        for i in range(5):
            self.ctx.add_turn(f"User {i}", f"Assistant {i}" * 10)

        initial_turns = len(self.ctx.turns)

        result = await self.ctx.compress()

        # Compression should have occurred
        assert result is True

        # Should have a summary
        assert self.ctx.summary is not None

        # Turn count should be reduced (or same if recent kept)
        assert len(self.ctx.turns) <= initial_turns
