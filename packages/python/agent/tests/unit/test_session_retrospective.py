"""
test_session_retrospective.py

Tests for the Session Retrospective feature - post-execution memory distillation.
"""

import pytest


class TestSessionRetrospective:
    """Test cases for session retrospective functionality."""

    def test_retrospective_creation(self):
        """Test creating a basic retrospective from session data."""
        from omni.agent.core.memory.retrospective import (
            create_session_retrospective,
        )

        messages = [
            {"role": "user", "content": "Test task"},
            {"role": "assistant", "content": "I'll help with that"},
            {"role": "tool", "content": "read_files(paths=['test.py'])"},
            {"role": "assistant", "content": "SUCCESS: Task completed"},
        ]
        tool_calls = [{"name": "read_files", "status": "success"}]

        retro = create_session_retrospective(
            session_id="test-001",
            messages=messages,
            tool_calls=tool_calls,
            outcome="COMPLETED",
        )

        assert retro["session_id"] == "test-001"
        assert retro["outcome"] == "COMPLETED"
        assert retro["metrics"]["total_messages"] == 4
        assert retro["metrics"]["total_tool_calls"] == 1

    def test_retrospective_role_counts(self):
        """Test that role counts are correctly calculated."""
        from omni.agent.core.memory.retrospective import (
            create_session_retrospective,
        )

        messages = [
            {"role": "user", "content": "Task 1"},
            {"role": "user", "content": "Task 2"},  # 2 user messages
            {"role": "assistant", "content": "Response 1"},
            {"role": "assistant", "content": "Response 2"},
            {"role": "assistant", "content": "Response 3"},  # 3 assistant messages
            {"role": "tool", "content": "Tool output"},  # 1 tool message
        ]

        retro = create_session_retrospective(
            session_id="test-002",
            messages=messages,
            tool_calls=[],
            outcome="COMPLETED",
        )

        assert retro["role_counts"]["user"] == 2
        assert retro["role_counts"]["assistant"] == 3
        assert retro["role_counts"]["tool"] == 1

    def test_retrospective_tools_used(self):
        """Test that tools are correctly identified and deduplicated."""
        from omni.agent.core.memory.retrospective import (
            create_session_retrospective,
        )

        tool_calls = [
            {"name": "read_files", "status": "success"},
            {"name": "read_files", "status": "success"},  # Duplicate
            {"name": "write_file", "status": "success"},
            {"name": "git_status", "status": "success"},
        ]

        retro = create_session_retrospective(
            session_id="test-003",
            messages=[],
            tool_calls=tool_calls,
            outcome="COMPLETED",
        )

        assert len(retro["tools_used"]) == 3
        assert "read_files" in retro["tools_used"]
        assert "write_file" in retro["tools_used"]
        assert "git_status" in retro["tools_used"]

    def test_retrospective_success_rate(self):
        """Test success rate calculation."""
        from omni.agent.core.memory.retrospective import (
            create_session_retrospective,
        )

        tool_calls = [
            {"name": "read_files", "status": "success"},
            {"name": "write_file", "status": "success"},
            {"name": "git_commit", "status": "failed"},
        ]

        retro = create_session_retrospective(
            session_id="test-004",
            messages=[],
            tool_calls=tool_calls,
            outcome="PARTIAL",
        )

        # Success rate = 2/3 = 66.7%
        assert retro["metrics"]["success_rate"] == pytest.approx(0.667, rel=0.01)

    def test_format_retrospective(self):
        """Test formatting retrospective as readable output."""
        from omni.agent.core.memory.retrospective import (
            create_session_retrospective,
            format_retrospective,
        )

        messages = [
            {"role": "user", "content": "Fix the bug"},
            {"role": "assistant", "content": "SUCCESS: Bug fixed"},
        ]

        retro = create_session_retrospective(
            session_id="test-005",
            messages=messages,
            tool_calls=[],
            outcome="COMPLETED",
        )

        formatted = format_retrospective(retro)

        assert "SESSION RETROSPECTIVE" in formatted
        assert "test-005" in formatted
        assert "COMPLETED" in formatted
        assert "METRICS" in formatted

    def test_empty_session(self):
        """Test retrospective with empty session."""
        from omni.agent.core.memory.retrospective import (
            create_session_retrospective,
        )

        retro = create_session_retrospective(
            session_id="test-006",
            messages=[],
            tool_calls=[],
            outcome="EMPTY",
        )

        assert retro["session_id"] == "test-006"
        assert retro["metrics"]["total_messages"] == 0
        assert retro["metrics"]["total_tool_calls"] == 0
        # 0/0 = 0.0 in Python (no successful calls among no calls)
        assert retro["metrics"]["success_rate"] == 0.0


class TestMemoryArchiver:
    """Test cases for memory archiving with retrospective integration."""

    def test_archive_turn_with_retrospective(self):
        """Test that archiving includes retrospective generation."""
        from omni.agent.core.memory.archiver import MemoryArchiver

        archiver = MemoryArchiver()

        messages = [
            {"role": "user", "content": "Create a new feature"},
            {"role": "assistant", "content": "I'll create the feature for you"},
            {"role": "tool", "content": "write_file(path='feature.py', content='...')"},
            {"role": "assistant", "content": "SUCCESS: Feature created"},
        ]

        # Archive should work without errors
        archiver.archive_turn(messages)
        stats = archiver.get_stats()

        assert stats["last_archived_idx"] == 4


class TestEpisodicMemoryProvider:
    """Test cases for episodic memory provider with retrospective."""

    @pytest.mark.asyncio
    async def test_recall_with_retrospective_context(self):
        """Test that recall works with retrospective-style queries."""
        from omni.core.context.providers import EpisodicMemoryProvider

        provider = EpisodicMemoryProvider(top_k=3)

        state = {
            "messages": [{"role": "user", "content": "How did we fix the bug last time?"}],
            "current_task": "How did we fix the bug last time?",
        }

        # Should return None when no memories exist (clean slate)
        result = await provider.provide(state, budget=1000)
        # Result may be None if VectorDB is not available
        assert result is None or result.name == "episodic_memory"
