"""
tui_bridge.py - Auto-TUI Injection & Lifecycle Management (Reverse Connection)

Handles the automatic injection of the Rust-based TUI when running in interactive modes.
Acts as a bridge between the Python logic layer and the Rust presentation layer.

Architecture (Reverse Connection):
1. Python creates and binds the Unix Domain Socket first (instant, reliable)
2. Spawns Rust TUI process as child
3. Rust TUI connects to Python's socket as client
4. Python forwards internal events to TUI for rendering

This solves the race condition where Python tried to connect before Rust was ready.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Protocol

from omni.foundation.runtime.gitops import get_project_root

logger = logging.getLogger("omni.agent.cli.tui_bridge")

# Constant for the Rust binary name
RUST_TUI_BIN = "omni-tui"


def get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean value from environment variable."""
    val = os.environ.get(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


@dataclass
class TUIConfig:
    """Configuration for the TUI Bridge (Reverse Connection Mode)."""

    socket_path: str = ""
    connect_timeout: float = 5.0
    binary_path: str = RUST_TUI_BIN
    enabled: bool = True
    theme: str = "dark"

    def __post_init__(self):
        if not self.socket_path:
            # Use UUID to ensure socket path is unique and collision-free
            socket_id = uuid.uuid4().hex[:8]
            self.socket_path = f"/tmp/omni_tui_{socket_id}.sock"


class TUIBridgeProtocol(Protocol):
    """Protocol for TUI communication to avoid circular imports."""

    async def send_event(self, topic: str, payload: dict[str, Any]) -> None: ...
    async def send_log(self, level: str, message: str) -> None: ...
    @property
    def is_active(self) -> bool: ...
    @property
    def is_connected(self) -> bool: ...  # Alias for is_active (used by OmegaRunner)


class NullTUIBridge:
    """No-op TUI bridge for non-interactive environments."""

    @property
    def is_active(self) -> bool:
        return False

    @property
    def is_connected(self) -> bool:
        return False

    async def send_event(self, topic: str, payload: dict[str, Any]) -> None:
        pass

    async def send_log(self, level: str, message: str) -> None:
        pass


class TUIManager:
    """
    Manages the lifecycle of the Rust TUI process and the IPC channel.

    Reverse Connection Pattern (Python = Server, Rust = Client):
    1. Python creates and binds Unix Domain Socket first (instant)
    2. Spawns the Rust TUI process as a child with --role client
    3. Rust TUI connects to Python's socket
    4. Python forwards internal events to TUI for rendering
    """

    def __init__(self, config: Optional[TUIConfig] = None):
        self.config = config or TUIConfig()
        self._process: Optional[subprocess.Popen] = None
        self._server_socket: Optional[socket.socket] = None
        self._conn: Optional[socket.socket] = None
        self._active = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_active(self) -> bool:
        """Check if the TUI bridge is currently active and connected."""
        return self._active

    @property
    def is_connected(self) -> bool:
        """Alias for is_active (used by OmegaRunner)."""
        return self._active

    def should_enable(self) -> bool:
        """
        Determine if TUI should be enabled based on environment.

        Conditions for enabling:
        1. Stdout is a TTY (interactive terminal)
        2. OMNI_MODE is not set to 'mcp' or 'headless'
        3. NO_TUI env var is not set
        4. Config explicitly enables it
        """
        if not self.config.enabled:
            logger.debug("TUI disabled by config")
            return False

        is_tty = sys.stdout.isatty()
        mode = os.environ.get("OMNI_MODE", "default").lower()
        no_tui = get_env_bool("NO_TUI", False)

        should_run = is_tty and mode not in ("mcp", "headless") and not no_tui

        if not should_run:
            logger.debug(f"TUI disabled: tty={is_tty}, mode={mode}, no_tui={no_tui}")

        return should_run

    def _is_development_mode(self) -> bool:
        """Check if running in the omni-dev-fusion development project.

        Returns True if pyproject.toml has project.name = "omni-dev-fusion".
        """
        # Use get_project_root() to get project root directory
        project_root = get_project_root()
        pyproject = project_root / "pyproject.toml"

        if not pyproject.exists():
            return False

        try:
            content = pyproject.read_text()
            # Check for project name = "omni-dev-fusion"
            if 'name = "omni-dev-fusion"' in content:
                return True
        except Exception:
            pass

        return False

    def _find_binary(self) -> str:
        """Find the Rust TUI binary path.

        Development Mode (omni-dev-fusion project):
            1. OMNI_TUI_BIN env var (highest priority)
            2. Local target/debug or target/release binary
            3. Fall back to system PATH

        User Mode (installed package):
            1. OMNI_TUI_BIN env var
            2. System PATH (omni-tui installed separately)
        """
        # Priority 1: Environment variable (works in both modes)
        if env_bin := os.environ.get("OMNI_TUI_BIN"):
            logger.debug(f"Using TUI binary from OMNI_TUI_BIN: {env_bin}")
            return env_bin

        # Development mode: look for local binary
        if self._is_development_mode():
            # Use get_project_root() to get project root directory
            project_root = get_project_root()

            # Prefer debug for faster builds
            for profile in ["debug", "release"]:
                target_bin = project_root / "target" / profile / "omni-tui"
                if target_bin.exists() and os.access(target_bin, os.X_OK):
                    # Add target dir to PATH so "omni-tui" can be found
                    target_dir = str(target_bin.parent)
                    current_path = os.environ.get("PATH", "")
                    if target_dir not in current_path:
                        os.environ["PATH"] = f"{target_dir}:{current_path}"
                    logger.debug(f"Using local TUI binary: {target_bin}")
                    return "omni-tui"

            logger.warning(
                "omni-dev-fusion project detected but omni-tui binary not found. "
                "Run: cd packages/rust && cargo build -p omni-tui"
            )

        # User mode or fallback: use system PATH
        logger.debug("Using system PATH for omni-tui binary")
        return self.config.binary_path

    async def _wait_for_connection(self) -> None:
        """Wait for Rust TUI to connect to our socket."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        timeout = self.config.connect_timeout

        while loop.time() - start_time < timeout:
            try:
                # Try to accept a connection (non-blocking)
                conn = await asyncio.wait_for(loop.sock_accept(self._server_socket), timeout=0.5)
                self._conn = conn[0]
                logger.info(f"Rust TUI connected to {self.config.socket_path}")
                return
            except asyncio.TimeoutError:
                # Check if Rust process died
                if self._process and self._process.poll() is not None:
                    raise RuntimeError("Rust TUI process died before connecting")
                continue
            except OSError:
                # No connection yet, keep waiting
                await asyncio.sleep(0.05)
                # Check if Rust process died
                if self._process and self._process.poll() is not None:
                    raise RuntimeError("Rust TUI process died before connecting")
                continue

        raise TimeoutError(
            f"Timed out waiting for Rust TUI to connect to {self.config.socket_path}"
        )

    @asynccontextmanager
    async def lifecycle(self):
        """
        Async context manager for TUI lifecycle.

        Usage:
            async with tui_manager.lifecycle() as tui:
                await tui.send_event("start", {})
                # ... run tasks ...
        """
        if not self.should_enable():
            logger.debug("TUI not enabled, using NullTUIBridge")
            yield NullTUIBridge()
            return

        self._loop = asyncio.get_running_loop()

        try:
            await self._start_server()
            await self._spawn_rust_process()
            await self._wait_for_connection()
            self._active = True

            # Send initial handshake
            await self.send_event(
                "system/init",
                {
                    "version": "2.0.0",
                    "pid": os.getpid(),
                    "cwd": os.getcwd(),
                    "theme": self.config.theme,
                },
            )

            logger.info("TUI lifecycle started")

            yield self

        except Exception as e:
            logger.warning(f"Failed to initialize TUI: {e}. Falling back to standard output.")
            self._active = False
            await self._cleanup()
            yield NullTUIBridge()
        finally:
            await self._cleanup()

    async def _start_server(self) -> None:
        """Create and bind the Unix Domain Socket (Python = Server)."""
        socket_path = self.config.socket_path

        # Clean up existing socket
        if os.path.exists(socket_path):
            os.remove(socket_path)

        # Create Unix domain socket
        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(socket_path)
        self._server_socket.listen(1)
        self._server_socket.setblocking(False)

        logger.info(f"Unix socket server listening on {socket_path}")

    async def _spawn_rust_process(self) -> None:
        """Spawn the Rust TUI process (Rust = Client)."""
        binary = self._find_binary()
        cmd = [
            binary,
            "--socket",
            self.config.socket_path,
            "--role",
            "client",  # Explicitly tell Rust to connect as client
            "--pid",
            str(os.getpid()),
        ]

        logger.info(f"Launching Rust TUI: {' '.join(cmd)}")

        # Inherit stdin/stdout/stderr so TUI can render to terminal and read keyboard
        # Use start_new_session so Ctrl+C only affects the TUI, not Python
        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,  # Connect stdin for keyboard input
            stdout=None,  # Inherit - allows TUI to render to terminal
            stderr=None,  # Inherit - allows logging to terminal
            start_new_session=True,
        )

    async def send_event(self, topic: str, payload: dict[str, Any]) -> None:
        """
        Send an event to the TUI asynchronously.

        Args:
            topic: Event topic (e.g., 'task/start', 'log/info')
            payload: Data associated with the event
        """
        if not self._active or not self._conn:
            return

        event = {
            "source": "omni-agent",
            "topic": topic,
            "payload": payload,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            data = json.dumps(event) + "\n"
            loop = asyncio.get_running_loop()
            await loop.sock_sendall(self._conn, data.encode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to send TUI event: {e}")
            self._active = False

    async def send_log(self, level: str, message: str) -> None:
        """Send a log message to TUI."""
        await self.send_event("log", {"level": level, "message": message})

    async def _cleanup(self) -> None:
        """Clean up resources."""
        self._active = False

        # Close connection
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

        # Close server socket
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        # Clean up socket file
        if self.config.socket_path and os.path.exists(self.config.socket_path):
            try:
                os.remove(self.config.socket_path)
            except Exception:
                pass

        # Terminate Rust process
        if self._process:
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None

        logger.info("TUI lifecycle cleaned up")


def create_tui_bridge() -> TUIBridgeProtocol:
    """
    Factory function to create the appropriate TUI bridge.

    Returns:
        TUIManager if TUI should be active, otherwise NullTUIBridge
    """
    config = TUIConfig(enabled=True)
    manager = TUIManager(config)

    if manager.should_enable():
        return manager

    return NullTUIBridge()


__all__ = [
    "TUIManager",
    "TUIConfig",
    "TUIBridgeProtocol",
    "NullTUIBridge",
    "create_tui_bridge",
]
