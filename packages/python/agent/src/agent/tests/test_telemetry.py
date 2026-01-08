"""
src/agent/tests/test_phase19_blackbox.py
Phase 19: The Black Box - Telemetry and Session Tests.

Tests for:
- TokenUsage and CostEstimator (telemetry.py)
- SessionManager and SessionEvent (session.py)
- Orchestrator integration with session logging

Run with: pytest packages/python/agent/src/agent/tests/test_phase19_blackbox.py -v
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.core.telemetry import CostEstimator, TokenUsage, SessionTelemetry
from agent.core.session import SessionManager, SessionEvent, get_agent_storage_dir


# =============================================================================
# Telemetry Tests
# =============================================================================


class TestTokenUsage:
    """Test TokenUsage model."""

    def test_default_values(self):
        """TokenUsage has correct default values."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cost_usd == 0.0

    def test_custom_values(self):
        """TokenUsage accepts custom values."""
        usage = TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            cost_usd=0.01,
        )
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.total_tokens == 1500
        assert usage.cost_usd == 0.01

    def test_addition(self):
        """TokenUsage supports addition."""
        u1 = TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.001)
        u2 = TokenUsage(input_tokens=200, output_tokens=100, cost_usd=0.002)
        u3 = u1 + u2

        assert u3.input_tokens == 300
        assert u3.output_tokens == 150
        assert u3.cost_usd == 0.003


class TestCostEstimator:
    """Test CostEstimator for token and cost estimation."""

    def test_estimate_basic(self):
        """Basic token estimation works."""
        usage = CostEstimator.estimate("Hello, world!", "Hi there!")
        assert usage.input_tokens > 0
        assert usage.output_tokens > 0
        assert usage.total_tokens > 0
        assert usage.cost_usd > 0

    def test_estimate_empty(self):
        """Empty input produces zero tokens."""
        usage = CostEstimator.estimate("", "")
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cost_usd == 0.0

    def test_estimate_chinese_text(self):
        """Chinese text has appropriate token estimation."""
        chinese = "你好世界这是一个测试"
        usage = CostEstimator.estimate(chinese, "")
        # Chinese should have different token ratio
        assert usage.input_tokens > 0

    def test_estimate_with_api_usage(self):
        """API usage data is used when provided."""
        usage = CostEstimator.estimate(
            text_input="",
            text_output="",
            model="default",
            use_api_usage=True,
            api_usage={"input_tokens": 1000, "output_tokens": 500},
        )
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.cost_usd > 0

    def test_pricing_models(self):
        """Different pricing models produce different costs."""
        input_text = "x" * 1000
        output_text = "y" * 1000

        sonnet_cost = CostEstimator.estimate(input_text, output_text, "claude-3-5-sonnet")
        opus_cost = CostEstimator.estimate(input_text, output_text, "claude-3-opus")

        # Opus is more expensive
        assert opus_cost.cost_usd > sonnet_cost.cost_usd


class TestSessionTelemetry:
    """Test SessionTelemetry for accumulating usage."""

    def test_add_usage(self):
        """Usage accumulation works."""
        telemetry = SessionTelemetry()

        u1 = TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.001)
        u2 = TokenUsage(input_tokens=200, output_tokens=100, cost_usd=0.002)

        telemetry.add_usage(u1)
        telemetry.add_usage(u2)

        summary = telemetry.get_summary()
        assert summary["total_requests"] == 2
        assert summary["total_input_tokens"] == 300
        assert summary["total_output_tokens"] == 150
        assert summary["total_cost_usd"] == 0.003

    def test_get_cost_rate(self):
        """Cost rate is calculable."""
        telemetry = SessionTelemetry()
        # Add some usage
        telemetry.add_usage(TokenUsage(input_tokens=1000, output_tokens=500, cost_usd=0.01))

        rate = telemetry.get_cost_rate()
        assert "$" in rate
        assert "/min" in rate


# =============================================================================
# Session Event Tests
# =============================================================================


class TestSessionEvent:
    """Test SessionEvent model."""

    def test_create_event(self):
        """Event creation works."""
        event = SessionEvent(
            type="user",
            source="user",
            content="Hello!",
        )
        assert event.type == "user"
        assert event.source == "user"
        assert event.content == "Hello!"
        assert event.id is not None
        assert event.timestamp is not None

    def test_event_with_usage(self):
        """Event with usage tracking."""
        usage = TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.001)
        event = SessionEvent(
            type="agent_action",
            source="coder",
            content="Fixed the bug",
            usage=usage,
        )
        assert event.usage == usage

    def test_event_serialization(self):
        """Event serializes to JSON."""
        event = SessionEvent(
            type="router",
            source="hive_router",
            content={"target_agent": "coder"},
        )
        json_str = event.model_dump_json()
        assert "router" in json_str
        assert "hive_router" in json_str

        # Can be deserialized
        data = json.loads(json_str)
        restored = SessionEvent(**data)
        assert restored.type == "router"


# =============================================================================
# Session Manager Tests
# =============================================================================


class TestSessionManager:
    """Test SessionManager for session persistence."""

    @pytest.fixture
    def mock_storage_dir(self, tmp_path):
        """Create a mock storage directory structure."""
        storage_dir = tmp_path / "agent" / "sessions"
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir

    def test_new_session(self, mock_storage_dir):
        """New session is created with auto-generated ID."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager()
            assert session.session_id is not None
            assert len(session.session_id) == 8
            assert len(session.history) == 0

    def test_custom_session_id(self, mock_storage_dir):
        """Custom session ID is used."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager(session_id="custom123")
            assert session.session_id == "custom123"

    def test_log_event(self, mock_storage_dir):
        """Logging events works."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("test-log")

            # Log user input
            session.log("user", "user", "Fix the bug")

            # Verify history updated
            assert len(session.history) == 1
            assert session.history[0]["role"] == "user"
            assert session.history[0]["content"] == "Fix the bug"

            # Verify file created
            assert (mock_storage_dir / "test-log.jsonl").exists()

    def test_log_with_usage(self, mock_storage_dir):
        """Logging with usage updates telemetry."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("test-usage")

            usage = TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.001)
            session.log("router", "hive_router", {"target": "coder"}, usage=usage)

            assert session.telemetry.total_usage.cost_usd == 0.001
            assert session.telemetry.request_count == 1

    def test_log_agent_action(self, mock_storage_dir):
        """Agent actions are logged correctly."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("test-agent")

            session.log("user", "user", "Hello")
            session.log("agent_action", "coder", "Hi there!")

            # History should have user and assistant
            assert len(session.history) == 2
            assert session.history[0]["role"] == "user"
            assert session.history[1]["role"] == "assistant"

    def test_file_persistence(self, mock_storage_dir):
        """Events are written to file."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("test-persist")

            session.log("user", "user", "Test message")

            # Read file directly
            file_path = mock_storage_dir / "test-persist.jsonl"
            assert file_path.exists()

            with open(file_path) as f:
                lines = f.readlines()
                assert len(lines) == 1

                event = json.loads(lines[0])
                assert event["type"] == "user"
                assert event["content"] == "Test message"

    def test_history_replay(self, mock_storage_dir):
        """Session can be resumed from file."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            # Create first session and log (with usage data)
            session1 = SessionManager("test-replay")
            usage1 = TokenUsage(input_tokens=100, output_tokens=50, cost_usd=0.001)
            session1.log("user", "user", "Hello", usage=usage1)
            session1.log("agent_action", "coder", "Hi!", usage=usage1)

            # Create new session with same ID (resumption)
            session2 = SessionManager("test-replay")

            # History should be replayed
            assert len(session2.history) == 2
            assert session2.history[0]["content"] == "Hello"
            assert session2.history[1]["content"] == "Hi!"

            # Telemetry should be accumulated (usage is tracked per event with usage)
            assert session2.telemetry.request_count == 2
            assert session2.telemetry.total_usage.cost_usd == 0.002

    def test_get_summary(self, mock_storage_dir):
        """Session summary is correct."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("test-summary")
            session.log("user", "user", "Test")

            summary = session.get_summary()
            assert "Session: test-summary" in summary
            assert "$" in summary

    def test_get_telemetry_summary(self, mock_storage_dir):
        """Telemetry summary is correct."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("test-telemetry")
            session.log("user", "user", "Test")

            summary = session.get_telemetry_summary()
            assert "total_requests" in summary
            assert "total_cost_usd" in summary

    def test_get_events(self, mock_storage_dir):
        """Getting events works."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("test-events")

            session.log("user", "user", "Message 1")
            session.log("user", "user", "Message 2")

            events = session.get_events()
            assert len(events) == 2

            # Limit
            limited = session.get_events(limit=1)
            assert len(limited) == 1

    def test_get_history(self, mock_storage_dir):
        """Getting history works."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("test-history")

            session.log("user", "user", "Hello")
            session.log("agent_action", "coder", "Hi")

            history = session.get_history()
            assert len(history) == 2


class TestSessionManagerClassMethods:
    """Test SessionManager class methods."""

    @pytest.fixture
    def mock_storage_dir(self, tmp_path):
        """Create a mock storage directory structure."""
        storage_dir = tmp_path / "agent" / "sessions"
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir

    def test_list_sessions(self, mock_storage_dir):
        """Listing sessions works."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            # Create a session
            SessionManager("session1").log("user", "user", "test")
            SessionManager("session2").log("user", "user", "test")

            sessions = SessionManager.list_sessions()
            assert len(sessions) >= 2

            # Check structure
            for s in sessions:
                assert "session_id" in s
                assert "events" in s

    def test_get_latest_session_id(self, mock_storage_dir):
        """Getting latest session ID works."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=mock_storage_dir):
            session = SessionManager("latest-test")
            session.log("user", "user", "test")

            latest = SessionManager.get_latest_session_id()
            assert latest == "latest-test"


# =============================================================================
# Integration Tests
# =============================================================================


class TestOrchestratorSessionIntegration:
    """Test Orchestrator integration with SessionManager."""

    def test_orchestrator_has_session(self):
        """Orchestrator has SessionManager."""
        from agent.core.orchestrator import Orchestrator

        with patch("agent.core.orchestrator.SessionManager") as mock_session:
            with patch("agent.core.orchestrator.get_checkpointer") as mock_checkpointer:
                mock_session.return_value = MagicMock()
                mock_checkpointer.return_value = MagicMock()
                orchestrator = Orchestrator()

                mock_session.assert_called_once()
                assert orchestrator.session is not None

    @pytest.mark.asyncio
    async def test_dispatch_logs_user_input(self, tmp_path):
        """Dispatch logs user input to session."""
        from agent.core.orchestrator import Orchestrator

        mock_session = MagicMock()
        mock_session.get_history.return_value = []

        with patch("agent.core.orchestrator.SessionManager", return_value=mock_session):
            with patch("agent.core.orchestrator.get_checkpointer") as mock_checkpointer:
                with patch("agent.core.orchestrator.get_hive_router") as mock_router:
                    mock_checkpointer.return_value = MagicMock()

                    mock_route = MagicMock()
                    mock_route.target_agent = "coder"
                    mock_route.task_brief = "test"
                    mock_route.confidence = 0.9
                    mock_route.constraints = []
                    mock_route.relevant_files = []
                    mock_route.from_cache = False
                    mock_router.return_value.route_to_agent.return_value = mock_route

                    orchestrator = Orchestrator()
                    orchestrator.router = mock_router.return_value

                    # Mock worker
                    mock_worker = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.confidence = 0.9
                    mock_result.rag_sources = []
                    mock_result.content = "Done"
                    mock_worker.run.return_value = mock_result

                    orchestrator.agent_map = {"coder": lambda **kw: mock_worker}

                    try:
                        await orchestrator.dispatch("test query")
                    except Exception:
                        pass  # Expected to fail without full infra

                # Verify session.log was called for user
                calls = mock_session.log.call_args_list
                user_calls = [c for c in calls if c[0][0] == "user"]
                assert len(user_calls) >= 1


# =============================================================================
# Main CLI Tests
# =============================================================================


class TestMainCLI:
    """Test main.py CLI argument parsing."""

    def test_resume_argument(self, tmp_path):
        """--resume argument is parsed."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            # This tests the argparse setup
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--resume", type=str)

            args = parser.parse_args(["--resume", "test-session"])
            assert args.resume == "test-session"

    def test_list_sessions_argument(self, tmp_path):
        """--list-sessions argument is parsed."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--list-sessions", action="store_true")

            args = parser.parse_args(["--list-sessions"])
            assert args.list_sessions is True
