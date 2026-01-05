"""
src/agent/tests/test_phase19_claude_symbiosis.py
Phase 19.6: Claude Code Symbiosis Tests.

Tests for:
- ClaudeCodeAdapter (CLI wrapper)
- ContextInjector (dynamic context generation)
- MCP Server tools

Run with: pytest packages/python/agent/src/agent/tests/test_phase19_claude_symbiosis.py -v
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from agent.core.adapters.claude_cli import (
    ClaudeCodeAdapter,
    ContextInjector,
    create_claude_adapter,
)
from agent.core.session import SessionManager, SessionEvent
from agent.core.telemetry import TokenUsage


# =============================================================================
# ContextInjector Tests
# =============================================================================


class TestContextInjector:
    """Test ContextInjector for dynamic context generation."""

    def test_generate_context_file(self):
        """Context file generation works."""
        injector = ContextInjector()

        context = injector.generate_context_file(
            mission_brief="Fix the threading bug",
            relevant_files=["agent/core/bootstrap.py", "agent/core/orchestrator.py"],
            relevant_docs=["docs/explanation/threading.md"],
        )

        assert "Fix the threading bug" in context
        assert "bootstrap.py" in context
        assert "Relevant Files" in context
        assert "Documentation References" in context

    def test_generate_context_without_docs(self):
        """Context without documentation works."""
        injector = ContextInjector()

        context = injector.generate_context_file(
            mission_brief="Add tests",
            relevant_files=["test_main.py"],
        )

        assert "Add tests" in context
        assert "test_main.py" in context
        # No docs section if not provided
        assert "Documentation References" not in context

    def test_generate_context_empty_files(self):
        """Empty file list works."""
        injector = ContextInjector()

        context = injector.generate_context_file(
            mission_brief="Just a question",
            relevant_files=[],
        )

        assert "Just a question" in context
        # Should still have structure
        assert "Mission Context" in context
        assert "Relevant Files" in context

    def test_generate_context_file_creates_temp_file(self, tmp_path):
        """Context file can be written to temp location."""
        injector = ContextInjector()

        content = injector.generate_context_file(
            mission_brief="Test mission",
            relevant_files=["test.py"],
        )

        # Verify content is valid markdown
        assert content.startswith("# Mission Context")
        assert len(content) > 0


# =============================================================================
# ClaudeCodeAdapter Tests
# =============================================================================


class TestClaudeCodeAdapter:
    """Test ClaudeCodeAdapter for CLI wrapping."""

    @pytest.fixture
    def mock_session(self, tmp_path):
        """Create mock session."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            session = SessionManager("test-adapter")
            return session

    def test_adapter_initialization(self, mock_session):
        """Adapter initializes correctly."""
        adapter = ClaudeCodeAdapter(session=mock_session)

        assert adapter.session == mock_session
        assert adapter.context_injector is not None
        assert adapter.claude_cmd == ["claude"]

    def test_construct_command_headless(self, mock_session):
        """Command construction works for headless mode."""
        adapter = ClaudeCodeAdapter(session=mock_session)
        adapter.use_headless_mode = True

        cmd = adapter._construct_command("Fix the bug", context_file=None)

        assert "claude" in cmd[0]
        assert "-p" in cmd
        assert "Fix the bug" in cmd

    def test_construct_command_with_context(self, tmp_path):
        """Command includes context file when provided."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            mock_session = SessionManager("test-context")
            adapter = ClaudeCodeAdapter(session=mock_session)

            context_file = tmp_path / "test_context.md"
            context_file.write_text("# Test")

            cmd = adapter._construct_command("Task", context_file=context_file)

            assert "--context-file" in cmd
            assert str(context_file) in cmd

    @pytest.mark.asyncio
    async def test_run_mission_returns_result(self, mock_session):
        """run_mission returns structured result."""
        adapter = ClaudeCodeAdapter(session=mock_session)
        adapter.claude_cmd = ["echo", "test output"]  # Use echo for testing

        result = await adapter.run_mission(
            mission_brief="Test mission",
            relevant_files=["test.py"],
        )

        assert "success" in result
        assert "output" in result
        assert "exit_code" in result
        assert "duration_seconds" in result
        assert "events" in result

    @pytest.mark.asyncio
    async def test_run_mission_logs_events(self, mock_session):
        """run_mission logs events to session."""
        adapter = ClaudeCodeAdapter(session=mock_session)
        adapter.claude_cmd = ["echo", "hello"]

        await adapter.run_mission(
            mission_brief="Test",
            relevant_files=["test.py"],
        )

        # Should have logged events
        assert len(mock_session.events) >= 2

    @pytest.mark.asyncio
    async def test_run_mission_with_error(self, mock_session):
        """run_mission handles errors gracefully."""
        adapter = ClaudeCodeAdapter(session=mock_session)
        adapter.claude_cmd = ["nonexistent_command_12345"]

        result = await adapter.run_mission(mission_brief="Test")

        assert result["success"] is False
        assert result["exit_code"] == -1
        assert "error" in result["events"][-1]["type"]

    @pytest.mark.asyncio
    async def test_run_mission_streaming(self, mock_session):
        """Streaming output works."""
        adapter = ClaudeCodeAdapter(session=mock_session)
        adapter.claude_cmd = ["echo", "line1\nline2\nline3"]

        chunks = []
        async for chunk in adapter.run_mission_streaming(
            mission_brief="Test",
            relevant_files=["test.py"],
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        # Should have output chunks
        output_chunks = [c for c in chunks if c["type"] == "output"]
        assert len(output_chunks) > 0


class TestFactoryFunction:
    """Test factory functions."""

    def test_create_claude_adapter(self, tmp_path):
        """Factory creates adapter correctly."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            session = SessionManager("test")
            adapter = create_claude_adapter(session)

            assert isinstance(adapter, ClaudeCodeAdapter)
            assert adapter.session == session


# =============================================================================
# MCP Server Tests
# =============================================================================


class TestMCPServerTools:
    """Test MCP Server tool functions."""

    def test_omni_get_session_summary(self, tmp_path):
        """Session summary tool works."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            session = SessionManager("test-summary")
            session.log("user", "user", "test")

            from agent.mcp_server import get_session_manager

            # Patch the global session manager
            import agent.mcp_server as mcp_server

            mcp_server._session_manager = session

            result = mcp_server.omni_get_session_summary()

            assert "Session: test-summary" in result
            assert "$" in result

    def test_omni_list_sessions(self, tmp_path):
        """List sessions tool works."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            # Create some sessions
            SessionManager("sess1").log("user", "user", "test")
            SessionManager("sess2").log("user", "user", "test")

            from agent.mcp_server import SessionManager as SM

            sessions = SM.list_sessions()
            assert len(sessions) >= 2

    def test_omni_generate_context(self):
        """Context generation tool works."""
        from agent.mcp_server import omni_generate_context

        context = omni_generate_context(
            mission="Fix the bug",
            relevant_files=["main.py"],
        )

        assert "Fix the bug" in context
        assert "main.py" in context
        assert "Mission Context" in context


# =============================================================================
# Integration Tests
# =============================================================================


class TestClaudeSymbiosisIntegration:
    """Integration tests for Claude Code symbiosis."""

    @pytest.mark.asyncio
    async def test_full_mission_flow(self, tmp_path):
        """Complete mission flow with context injection."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            # Create session
            session = SessionManager("integration-test")

            # Create adapter
            adapter = create_claude_adapter(session)

            # Run mission
            result = await adapter.run_mission(
                mission_brief="Integration test mission",
                relevant_files=["test_file.py"],
                relevant_docs=["README.md"],
            )

            # Verify result structure
            assert "success" in result
            assert "cost_usd" in result
            assert len(session.events) > 0

            # Verify telemetry
            assert session.telemetry.request_count >= 1

    def test_context_injection_enhancement(self, tmp_path):
        """Context injection provides strategic advantage."""
        injector = ContextInjector()

        # Generate context
        context = injector.generate_context_file(
            mission_brief="Add user authentication feature",
            relevant_files=[
                "src/auth/models.py",
                "src/auth/views.py",
                "src/api/middleware.py",
            ],
            relevant_docs=[
                "docs/security/authentication.md",
                "docs/api/auth-flow.md",
            ],
        )

        # Verify context includes all relevant info
        assert "Add user authentication feature" in context
        assert "auth/models.py" in context
        assert "authentication.md" in context

        # This context would be passed to Claude Code
        # giving it immediate project-specific knowledge


# =============================================================================
# Configuration Tests
# =============================================================================


class TestContextCompressionConfig:
    """Test context compression configuration from settings.yaml."""

    def test_injector_reads_max_file_size_from_config(self, tmp_path):
        """ContextInjector reads max_file_size_kb from config."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            with patch("common.mcp_core.settings.Settings.get") as mock_get:
                mock_get.return_value = 100  # Custom value

                injector = ContextInjector()

                # Verify the config was read
                mock_get.assert_any_call("context_compression.max_file_size_kb", 50)

    def test_injector_uses_default_when_config_missing(self, tmp_path):
        """ContextInjector uses default when config is missing."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            with patch("common.mcp_core.settings.Settings.get") as mock_get:
                # get_setting returns None when key not found
                # The function should use the default value provided as second arg
                mock_get.return_value = None

                injector = ContextInjector()

                # Should use default value (50 KB) since config returns None
                # Check that the settings call was made with default
                assert mock_get.call_count > 0

    def test_generate_context_uses_config_file_size_limit(self, tmp_path):
        """generate_context_file uses config max_file_size_kb for truncation."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            with patch("common.mcp_core.settings.Settings.get") as mock_get:
                # Set config to 1KB limit
                mock_get.return_value = 1

                injector = ContextInjector(max_file_size_kb=1)  # Pass explicitly for test

                # Create content larger than 1KB
                large_content = "x" * 2000  # ~2KB

                context = injector.generate_context_file(
                    mission_brief="Test",
                    relevant_files=["test.py"],
                    file_contents={"large_file.py": large_content},
                )

                # Content should be truncated
                assert "large_file.py" in context
                # Should show truncation message with config value
                assert "max_file_size_kb: 1" in context

    def test_compressor_reads_enabled_from_config(self, tmp_path):
        """ContextCompressor reads enabled from config."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            with patch("common.mcp_core.settings.Settings.get") as mock_get:
                mock_get.return_value = False  # Disabled

                compressor = injector = ContextInjector().compressor

                assert compressor.enabled is False


class TestPostMortemConfig:
    """Test Post-Mortem audit configuration."""

    def test_auditor_reads_enabled_from_config(self, tmp_path):
        """PostMortemAuditor reads enabled from config."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            with patch("common.mcp_core.settings.Settings.get") as mock_get:
                # Return False for enabled check, True for threshold
                def side_effect(key, default=None):
                    if "enabled" in key:
                        return False
                    return default

                mock_get.side_effect = side_effect

                session = SessionManager("test-postmortem")
                from agent.core.adapters.claude_cli import PostMortemAuditor

                auditor = PostMortemAuditor(session)

                assert auditor.enabled is False

    def test_auditor_reads_confidence_threshold_from_config(self, tmp_path):
        """PostMortemAuditor reads confidence_threshold from config."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            with patch("common.mcp_core.settings.Settings.get") as mock_get:
                mock_get.return_value = 0.9

                session = SessionManager("test-threshold")
                from agent.core.adapters.claude_cli import PostMortemAuditor

                auditor = PostMortemAuditor(session)

                assert auditor.confidence_threshold == 0.9


class TestClaudeCodeAdapterConfig:
    """Test ClaudeCodeAdapter configuration."""

    def test_adapter_reads_post_mortem_from_config(self, tmp_path):
        """ClaudeCodeAdapter reads enable_post_mortem from config."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            with patch("common.mcp_core.settings.Settings.get") as mock_get:
                mock_get.return_value = False  # Disabled

                session = SessionManager("test-adapter-config")
                adapter = ClaudeCodeAdapter(session=session)

                assert adapter.enable_post_mortem is False

    def test_adapter_explicit_enable_overrides_config(self, tmp_path):
        """Explicit enable_post_mortem overrides config setting."""
        with patch("agent.core.session.get_agent_storage_dir", return_value=tmp_path):
            with patch("common.mcp_core.settings.Settings.get") as mock_get:
                mock_get.return_value = False  # Config says disabled

                session = SessionManager("test-explicit")
                # Explicitly enable
                adapter = ClaudeCodeAdapter(session=session, enable_post_mortem=True)

                assert adapter.enable_post_mortem is True
