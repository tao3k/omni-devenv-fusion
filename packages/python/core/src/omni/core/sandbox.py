"""Python SDK wrapper for NCL-driven sandbox executor.

This module provides Python interfaces to the Rust-accelerated sandbox
execution layer for nsjail (Linux) and seatbelt (macOS).
"""

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


def get_platform() -> str:
    """Detect the current platform.

    Returns:
        "linux", "macos", or "unknown"
    """
    return sandbox_detect_platform()


def is_nsjail_available() -> bool:
    """Check if nsjail is installed and available.

    Returns:
        True if nsjail binary is found
    """
    return sandbox_is_nsjail_available()


def is_seatbelt_available() -> bool:
    """Check if sandbox-exec (seatbelt) is available on macOS.

    Returns:
        True only on macOS when sandbox-exec is found
    """
    return sandbox_is_seatbelt_available()


def is_sandbox_available() -> bool:
    """Check if any sandbox executor is available.

    Returns:
        True if nsjail (Linux) or seatbelt (macOS) is available
    """
    platform = get_platform()
    if platform == "linux":
        return is_nsjail_available()
    elif platform == "macos":
        return is_seatbelt_available()
    return False


__all__ = [
    "get_platform",
    "is_nsjail_available",
    "is_seatbelt_available",
    "is_sandbox_available",
    "ExecutionResult",
    "SandboxConfig",
    "MountConfig",
    "NsJailExecutor",
    "SeatbeltExecutor",
]
