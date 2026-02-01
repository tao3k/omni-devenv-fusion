"""Unit tests for OmniCellRunner.

Trinity Architecture - Core Layer

Tests the Python wrapper for Rust OmniCell Executor.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestActionType:
    """Tests for ActionType enum."""

    def test_action_type_values(self):
        """Verify action type enum values."""
        from omni.core.skills.runtime.omni_cell import ActionType

        assert ActionType.OBSERVE.value == "observe"
        assert ActionType.MUTATE.value == "mutate"

    def test_action_type_from_string(self):
        """Test creating ActionType from string."""
        from omni.core.skills.runtime.omni_cell import ActionType

        assert ActionType("observe") == ActionType.OBSERVE
        assert ActionType("mutate") == ActionType.MUTATE


class TestCellResult:
    """Tests for CellResult model."""

    def test_cell_result_success(self):
        """Test successful result creation."""
        from omni.core.skills.runtime.omni_cell import CellResult

        result = CellResult(
            status="success",
            data={"name": "test.txt", "size": 1024},
            metadata={"mode": "observe"},
        )

        assert result.status == "success"
        assert result.data["name"] == "test.txt"
        assert result.security_check == "pass"

    def test_cell_result_error(self):
        """Test error result creation."""
        from omni.core.skills.runtime.omni_cell import CellResult

        result = CellResult(
            status="error",
            metadata={"error_msg": "Command failed", "command": "rm -rf /"},
        )

        assert result.status == "error"
        assert result.data is None
        assert "Command failed" in result.metadata["error_msg"]

    def test_cell_result_blocked(self):
        """Test blocked result creation."""
        from omni.core.skills.runtime.omni_cell import CellResult

        result = CellResult(
            status="blocked",
            metadata={"reason": "Security policy violation"},
        )

        assert result.status == "blocked"


class TestOmniCellRunner:
    """Tests for OmniCellRunner class."""

    @pytest.fixture
    def runner_without_rust(self):
        """Create runner with mocked-out Rust bridge."""
        from omni.core.skills.runtime.omni_cell import OmniCellRunner

        runner = OmniCellRunner()
        runner._rust_bridge = None  # Force fallback mode
        return runner

    def test_runner_initialization(self, runner_without_rust):
        """Test runner initializes without Rust bridge."""
        assert runner_without_rust is not None

    def test_classify_observe_command(self, runner_without_rust):
        """Test classification of read-only commands."""
        commands = ["ls -la", "cat file.txt", "pwd", "whoami", "ps aux"]

        for cmd in commands:
            result = runner_without_rust.classify(cmd)
            assert result.value == "observe", f"'{cmd}' should be observe"

    def test_classify_mutation_command(self, runner_without_rust):
        """Test classification of side-effect commands."""
        commands = ["rm file.txt", "cp a b", "mv old new", "mkdir -p dir"]

        for cmd in commands:
            result = runner_without_rust.classify(cmd)
            assert result.value == "mutate", f"'{cmd}' should be mutate"

    def test_classify_with_pipe(self, runner_without_rust):
        """Test classification preserves intent with pipes."""
        result = runner_without_rust.classify("ls | grep txt")
        assert result.value == "observe"

    @pytest.mark.asyncio
    async def test_run_observe_success(self, runner_without_rust):
        """Test successful observe command execution."""
        from omni.core.skills.runtime.omni_cell import ActionType

        with patch.object(runner_without_rust, "_run_fallback", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock(
                status="success",
                data=[{"name": "test.py"}],
                metadata={},
            )

            result = await runner_without_rust.run("ls", ActionType.OBSERVE)

            assert result.status == "success"
            assert len(result.data) == 1
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_mutation_blocked(self, runner_without_rust):
        """Test blocking dangerous mutation commands."""
        from omni.core.skills.runtime.omni_cell import ActionType

        dangerous_commands = ["rm -rf /", "mkfs.ext4 /dev/sda"]

        for cmd in dangerous_commands:
            result = await runner_without_rust.run(cmd, ActionType.MUTATE)
            assert result.status == "blocked", f"'{cmd}' should be blocked"

    @pytest.mark.asyncio
    async def test_run_auto_classify(self, runner_without_rust):
        """Test auto-classification when action not specified."""
        from omni.core.skills.runtime.omni_cell import ActionType

        with patch.object(runner_without_rust, "_run_fallback", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock(status="success", data=None, metadata={})

            # Should auto-detect observe
            await runner_without_rust.run("ls")


class TestMutationSafety:
    """Tests for mutation safety checking."""

    @pytest.fixture
    def runner(self):
        """Create runner without Rust bridge."""
        from omni.core.skills.runtime.omni_cell import OmniCellRunner

        runner = OmniCellRunner()
        runner._rust_bridge = None
        return runner

    def test_rm_rf_blocked(self, runner):
        """Test rm -rf / is blocked."""
        result = runner._check_mutation_safety("rm -rf /")
        assert result["safe"] is False
        assert "Root deletion" in result["reason"]

    def test_mkfs_blocked(self, runner):
        """Test mkfs is blocked."""
        result = runner._check_mutation_safety("mkfs.ext4 /dev/sda")
        assert result["safe"] is False
        assert "formatting" in result["reason"]

    def test_fork_bomb_blocked(self, runner):
        """Test fork bomb is blocked."""
        result = runner._check_mutation_safety(":(){ :|:& };:")
        assert result["safe"] is False

    def test_safe_mutation_allowed(self, runner):
        """Test safe mutations are allowed."""
        result = runner._check_mutation_safety("mkdir -p new_dir")
        assert result["safe"] is True

        result = runner._check_mutation_safety("cp a.txt b.txt")
        assert result["safe"] is True


class TestGetRunner:
    """Tests for module-level runner singleton."""

    def test_get_runner_returns_instance(self):
        """Test get_runner returns an OmniCellRunner."""
        from omni.core.skills.runtime import omni_cell

        # Reset singleton for test
        omni_cell._default_runner = None

        runner = omni_cell.get_runner()
        assert runner is not None

        # Cleanup
        omni_cell._default_runner = None

    @pytest.mark.asyncio
    async def test_run_command_convenience(self):
        """Test the convenience run_command function."""
        from omni.core.skills.runtime import omni_cell

        # Reset singleton
        original = omni_cell._default_runner
        omni_cell._default_runner = None

        try:
            # Mock the runner
            mock_result = MagicMock()
            mock_result.status = "success"
            mock_result.data = None
            mock_result.metadata = {}

            with patch.object(omni_cell, "get_runner") as mock_get:
                mock_runner = MagicMock()
                mock_runner.run = AsyncMock(return_value=mock_result)
                mock_get.return_value = mock_runner

                result = await omni_cell.run_command("ls")

                assert result.status == "success"
        finally:
            omni_cell._default_runner = original
