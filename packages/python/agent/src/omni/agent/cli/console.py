"""
console.py - Console and Output Formatting

Modular CLI Architecture

Provides:
- err_console: stderr console for logs and UI
- Output formatting functions (metadata panels, results)
- TUIBridge: Real-time state sync with Rust TUI (omni-tui)

Event System:
- Uses omni-events format: {"source": "...", "topic": "...", "payload": {...}, "timestamp": "..."}
- See: packages/rust/crates/omni-events/src/lib.rs

UNIX Philosophy:
- stderr: Logs, progress, UI elements (visible to user, invisible to pipes)
- stdout: Only skill results (pure data for pipes)
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

# err_console: responsible for UI, panels, logs, spinners (user visible, pipe invisible)
err_console = Console(stderr=True)


class TUIBridge:
    """
    Bridge for sending events from Python Agent to Rust TUI (omni-tui).

    Communication via Unix Domain Socket:
    - Writes JSON events to the socket
    - TUI subscribes and renders in real-time

    Event Format (omni-events compatible):
        {
            "source": "omega",
            "topic": "omega/mission/start",
            "payload": {"message": "...", "data": {...}},
            "timestamp": "ISO8601"
        }

    Usage:
        bridge = TUIBridge()
        bridge.connect("/tmp/omni-omega.sock")
        bridge.send_event({"source": "omega", "topic": "omega/mission/start", ...})
        bridge.disconnect()
    """

    def __init__(self, socket_path: str = "/tmp/omni-omega.sock"):
        """Initialize TUIBridge."""
        self.socket_path = Path(socket_path)
        self.socket: socket.socket | None = None
        self._connected = False
        self._lock = threading.Lock()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._event_queue: list[str] = []
        self._worker_thread: threading.Thread | None = None
        self._running = False

    def connect(self, socket_path: str | None = None) -> bool:
        """Connect to TUI socket."""
        if socket_path:
            self.socket_path = Path(socket_path)

        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(str(self.socket_path))
            self.socket.setblocking(False)
            self._connected = True
            self._reconnect_attempts = 0

            # Start background worker to flush queue
            self._running = True
            self._worker_thread = threading.Thread(target=self._flush_worker, daemon=True)
            self._worker_thread.start()

            err_console.print(f"[green]✓[/] Connected to TUI at {self.socket_path}")
            return True

        except (socket.error, FileNotFoundError) as e:
            err_console.print(f"[yellow]⚠[/] TUI not connected: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from TUI socket."""
        self._running = False

        with self._lock:
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass
                self.socket = None
            self._connected = False

    def is_connected(self) -> bool:
        """Check if connected to TUI."""
        return self._connected and self.socket is not None

    def send_event(self, event: dict) -> bool:
        """
        Send event to TUI.

        Args:
            event: Dictionary in omni-events format

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            msg = json.dumps(event) + "\n"

            with self._lock:
                if self._connected and self.socket:
                    try:
                        self.socket.sendall(msg.encode())
                        return True
                    except (socket.error, BlockingIOError):
                        # Queue for later sending
                        self._event_queue.append(msg)
                        return True
                else:
                    # Not connected, queue
                    self._event_queue.append(msg)
                    return False

        except Exception:
            return False

    def _flush_worker(self):
        """Background worker to flush queued events."""
        while self._running:
            try:
                with self._lock:
                    if not self._connected or not self._event_queue:
                        continue

                    # Try to send queued events
                    queue_copy = self._event_queue.copy()
                    self._event_queue.clear()

                for msg in queue_copy:
                    if self._connected and self.socket:
                        try:
                            self.socket.sendall(msg.encode())
                        except (socket.error, BlockingIOError):
                            with self._lock:
                                self._event_queue.append(msg)
                                break
                    else:
                        with self._lock:
                            self._event_queue.insert(0, msg)
                            break

            except Exception:
                pass

            # Sleep briefly
            time.sleep(0.05)


# Global TUI bridge instance
_tui_bridge: TUIBridge | None = None


def get_tui_bridge() -> TUIBridge:
    """Get or create global TUI bridge instance."""
    global _tui_bridge
    if _tui_bridge is None:
        _tui_bridge = TUIBridge()
    return _tui_bridge


def init_tui(socket_path: str = "/tmp/omni-omega.sock") -> bool:
    """Initialize TUI bridge and connect."""
    bridge = get_tui_bridge()
    return bridge.connect(socket_path)


def shutdown_tui():
    """Shutdown TUI bridge."""
    global _tui_bridge
    if _tui_bridge:
        _tui_bridge.disconnect()
        _tui_bridge = None


def cli_log_handler(message: str) -> None:
    """Log callback - all logs go to stderr.

    Args:
        message: Log message to display
    """
    style = "dim"
    prefix = "  │"
    if "[Swarm]" in message:
        style = "cyan"
        prefix = "🚀"
    elif "Error" in message:
        style = "red"
        prefix = "❌"

    err_console.print(f"{prefix} {message}", style=style)


# Known metadata field names (from MCP tool result schema and execution context)
_METADATA_FIELDS = {
    "isError",
    "error",
    "execution_time",
    "execution_time_ms",
    "skill_name",
    "command_name",
    "timestamp",
    "version",
    "schema_version",
}


def print_metadata_box(result: Any) -> None:
    """Draw a beautiful metadata box on stderr.

    Only shows true metadata fields (isError, execution_time, etc.)
    not business data (status, document_count, etc.)

    Args:
        result: The skill execution result
    """
    if isinstance(result, dict):
        # Extract only known metadata fields
        metadata = {k: v for k, v in result.items() if k in _METADATA_FIELDS}
        if metadata:
            err_console.print(
                Panel(
                    JSON.from_data(metadata),
                    title="[bold blue]Skill Metadata[/bold blue]",
                    border_style="blue",
                    expand=False,
                )
            )


def print_result(result: Any, is_tty: bool = False, json_output: bool = False) -> None:
    """Print skill result with dual-channel output.

    UNIX Philosophy:
    - stdout: Only skill results (pure data for pipes)
    - stderr: Logs, progress, metadata (visible to user, invisible to pipes)

    Args:
        result: The skill execution result (ExecutionResult, CommandResult, or dict)
        is_tty: Whether stdout is a terminal
        json_output: If True, output raw JSON to stdout
    """
    # Handle ExecutionResult from SkillCommand.execute
    if hasattr(result, "model_dump"):
        # Pydantic model (ExecutionResult)
        if json_output:
            sys.stdout.write(result.model_dump_json(indent=2) + "\n")
            return
        content = result.output
        metadata = {"success": result.success, "duration_ms": result.duration_ms}
        if result.error:
            metadata["error"] = result.error
    elif hasattr(result, "data") and result.data is not None:
        # CommandResult object from @skill_command decorator
        if isinstance(result.data, dict):
            content = result.data.get("content", result.data.get("markdown", ""))
            metadata = result.data.get("metadata", {})
        else:
            content = str(result.data)
            metadata = {}
    elif isinstance(result, dict):
        # Handle CommandResult format: data.content / data.metadata
        if "data" in result and isinstance(result["data"], dict):
            content = result["data"].get("content", result["data"].get("markdown", ""))
            metadata = result["data"].get("metadata", {})
        else:
            # MCP canonical shape from @skill_command: content = [{ "type": "text", "text": "..." }] or plain string
            raw_content = result.get("content", result.get("markdown"))
            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, list) and raw_content and isinstance(raw_content[0], dict):
                content = raw_content[0].get("text", "")
            else:
                content = raw_content if raw_content is not None else ""
            metadata = result.get("metadata", {})
            if "isError" in result:
                metadata["isError"] = result["isError"]
            # If no content/markdown key, show full result as JSON
            if content is None or content == "":
                content = json.dumps(result, indent=2, ensure_ascii=False)
                metadata = {}
    elif isinstance(result, str):
        content = result
        metadata = {}
    else:
        content = str(result)
        metadata = {}

    # [TTY Mode]
    if is_tty:
        # Show metadata panel only when there is something meaningful (error, timing, etc.)
        # Skip when it would only show isError: false
        if metadata and not (len(metadata) == 1 and metadata.get("isError") is False):
            err_console.print(
                Panel(
                    JSON.from_data(metadata),
                    title="[bold blue]Skill Metadata[/bold blue]",
                    border_style="blue",
                    expand=False,
                )
            )
        # Show content on stderr (user can see it)
        if content:
            err_console.print(Panel(content, title="Result", expand=False))
    else:
        # [Pipe Mode] - Content to stdout for pipes
        if content:
            sys.stdout.write(content)
            if not content.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()


__all__ = [
    "cli_log_handler",
    "err_console",
    "print_metadata_box",
    "print_result",
    # TUI Bridge
    "TUIBridge",
    "get_tui_bridge",
    "init_tui",
    "shutdown_tui",
]
