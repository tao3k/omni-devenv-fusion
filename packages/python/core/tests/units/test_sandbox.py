"""Tests for NCL-driven sandbox executor Python bindings."""

import pytest
import sys

# Import from the Rust bindings
try:
    from omni_core_rs import (
        sandbox_detect_platform,
        sandbox_is_nsjail_available,
        sandbox_is_seatbelt_available,
        ExecutionResult,
        SandboxConfig,
        MountConfig,
        NsJailExecutor,
        SeatbeltExecutor,
    )

    HAS_SANDBOX_BINDINGS = True
except ImportError:
    HAS_SANDBOX_BINDINGS = False


# Skip all tests if bindings are not available
pytestmark = pytest.mark.skipif(
    not HAS_SANDBOX_BINDINGS, reason="omni_core_rs sandbox bindings not available"
)


class TestPlatformDetection:
    """Test platform detection functions."""

    def test_detect_platform_returns_valid_value(self):
        """Platform should be one of: linux, macos, unknown."""
        platform = sandbox_detect_platform()
        assert platform in ["linux", "macos", "unknown"]

    def test_detect_platform_matches_os(self):
        """Platform should match current OS."""
        import sys

        platform = sandbox_detect_platform()
        if sys.platform == "linux":
            assert platform == "linux"
        elif sys.platform == "darwin":
            assert platform == "macos"

    def test_is_nsjail_available(self):
        """Check nsjail availability function runs without error."""
        result = sandbox_is_nsjail_available()
        assert isinstance(result, bool)

    def test_is_seatbelt_available(self):
        """Check seatbelt availability function runs without error."""
        result = sandbox_is_seatbelt_available()
        assert isinstance(result, bool)


class TestExecutionResult:
    """Test ExecutionResult class."""

    def test_execution_result_creation(self):
        """Test creating an ExecutionResult."""
        result = ExecutionResult(
            success=True,
            exit_code=0,
            stdout="test output",
            stderr="",
            execution_time_ms=100,
            memory_used_bytes=1024,
            error=None,
        )
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "test output"
        assert result.stderr == ""
        assert result.execution_time_ms == 100
        assert result.memory_used_bytes == 1024
        assert result.error is None

    def test_execution_result_error(self):
        """Test ExecutionResult with error."""
        result = ExecutionResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="command not found",
            execution_time_ms=50,
            memory_used_bytes=None,
            error="Execution failed",
        )
        assert result.success is False
        assert result.exit_code == 1
        assert result.error == "Execution failed"


class TestSandboxConfig:
    """Test SandboxConfig class."""

    def test_sandbox_config_creation(self):
        """Test creating a SandboxConfig."""
        config = SandboxConfig(
            skill_id="test-skill",
            mode="EXEC",
            hostname="test-container",
            cmd=["/bin/ls", "/tmp"],
            env=["PATH=/usr/bin"],
            mounts=[
                MountConfig(
                    src="/tmp",
                    dst="/tmp",
                    fstype="tmpfs",
                    rw=True,
                )
            ],
            rlimit_as=100_000_000,
            rlimit_cpu=60,
            rlimit_fsize=10_000_000,
            seccomp_mode=2,
            log_level="info",
        )

        assert config.skill_id == "test-skill"
        assert config.mode == "EXEC"
        assert config.hostname == "test-container"
        assert len(config.cmd) == 2
        assert len(config.env) == 1
        assert len(config.mounts) == 1
        assert config.rlimit_as == 100_000_000
        assert config.rlimit_cpu == 60
        assert config.seccomp_mode == 2

    def test_sandbox_config_empty_mounts(self):
        """Test config with empty mounts."""
        config = SandboxConfig(
            skill_id="test",
            mode="EXEC",
            hostname="test",
            cmd=["/bin/echo"],
            env=[],
            mounts=[],
            rlimit_as=0,
            rlimit_cpu=0,
            rlimit_fsize=0,
            seccomp_mode=0,
            log_level="info",
        )
        assert len(config.mounts) == 0


class TestMountConfig:
    """Test MountConfig class."""

    def test_mount_config_read_write(self):
        """Test read-write mount."""
        mount = MountConfig(
            src="/data",
            dst="/app/data",
            fstype="bind",
            rw=True,
        )
        assert mount.src == "/data"
        assert mount.dst == "/app/data"
        assert mount.fstype == "bind"
        assert mount.rw is True

    def test_mount_config_read_only(self):
        """Test read-only mount."""
        mount = MountConfig(
            src="/etc",
            dst="/app/etc",
            fstype="bind",
            rw=False,
        )
        assert mount.rw is False


class TestNsJailExecutor:
    """Test NsJailExecutor class."""

    def test_nsjail_executor_creation(self):
        """Test creating NsJailExecutor with default path."""
        executor = NsJailExecutor(None, 60)
        assert executor.name() == "nsjail"

    def test_nsjail_executor_custom_path(self):
        """Test creating NsJailExecutor with custom path."""
        executor = NsJailExecutor("/custom/path/nsjail", 120)
        assert executor.name() == "nsjail"


class TestSeatbeltExecutor:
    """Test SeatbeltExecutor class."""

    def test_seatbelt_executor_creation(self):
        """Test creating SeatbeltExecutor."""
        executor = SeatbeltExecutor(60)
        assert executor.name() == "seatbelt"

    def test_seatbelt_executor_name(self):
        """Test SeatbeltExecutor name is consistent."""
        executor = SeatbeltExecutor(30)
        assert executor.name() == "seatbelt"


class TestSandboxAvailability:
    """Test sandbox availability checking."""

    def test_sandbox_functions_return_bool(self):
        """All availability functions should return boolean."""
        platform = sandbox_detect_platform()
        assert isinstance(platform, str)

        nsjail = sandbox_is_nsjail_available()
        assert isinstance(nsjail, bool)

        seatbelt = sandbox_is_seatbelt_available()
        assert isinstance(seatbelt, bool)

    def test_at_least_one_platform_detected(self):
        """Should detect either linux or macos."""
        platform = sandbox_detect_platform()
        assert platform in ["linux", "macos", "unknown"]
