"""TUI Bridge - Python interface for Rust TUI engine.

Provides high-level TUI operations through the Rust omni-tui crate.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

try:
    from omni_core_rs import PyTuiApp, PyFoldablePanel

    _RUST_TUI_AVAILABLE = True
except ImportError:
    _RUST_TUI_AVAILABLE = False
    PyTuiApp = None  # type: ignore
    PyFoldablePanel = None  # type: ignore


class TuiBridge:
    """Bridge to Rust TUI engine."""

    def __init__(self, title: str = "Omni Dev Fusion"):
        """Initialize TUI bridge."""
        self._app: Optional[PyTuiApp] = None
        self._title = title
        self._is_active = False

        if _RUST_TUI_AVAILABLE:
            self._app = PyTuiApp(title)
        else:
            raise RuntimeError("omni-core-rs TUI bindings not available")

    @property
    def is_available(self) -> bool:
        """Check if TUI is available."""
        return _RUST_TUI_AVAILABLE

    def add_result(self, title: str, content: str) -> None:
        """Add a result panel to the TUI."""
        if self._app is not None:
            self._app.add_result(title, content)

    def add_expanded_panel(self, title: str, content: str) -> None:
        """Add an expanded panel."""
        if self._app is not None:
            self._app.add_panel(title, content, expanded=True)

    def set_status(self, message: str) -> None:
        """Set the status message."""
        if self._app is not None:
            self._app.set_status(message)

    def panel_count(self) -> int:
        """Get number of panels."""
        if self._app is not None:
            return self._app.panel_count()
        return 0

    def run(self) -> None:
        """Run the TUI main loop (blocking)."""
        if self._app is not None:
            self._is_active = True
            # This will block until TUI exits
            # self._app.run()


class TuiPanel:
    """Python wrapper for foldable panel."""

    def __init__(self, title: str, content: str = ""):
        """Create a new foldable panel."""
        if PyFoldablePanel is not None:
            self._panel = PyFoldablePanel.new(title, content)
        else:
            # Fallback to pure Python implementation
            self._title = title
            self._content = content.split("\n")
            self._is_expanded = False
            self._scroll = 0

    def toggle(self) -> None:
        """Toggle fold state."""
        if hasattr(self._panel, "toggle"):
            self._panel.toggle()
        else:
            self._is_expanded = not self._is_expanded

    def is_expanded(self) -> bool:
        """Check if expanded."""
        if hasattr(self._panel, "is_expanded"):
            return self._panel.is_expanded()
        return self._is_expanded

    def set_content(self, content: str) -> None:
        """Set panel content."""
        if hasattr(self._panel, "set_content"):
            self._panel.set_content(content)
        else:
            self._content = content.split("\n")

    def append_line(self, line: str) -> None:
        """Append a line to content."""
        if hasattr(self._panel, "append_line"):
            self._panel.append_line(line)
        else:
            self._content.append(line)

    @property
    def title(self) -> str:
        """Get panel title."""
        if hasattr(self._panel, "title"):
            return self._panel.title()
        return self._title

    @property
    def line_count(self) -> int:
        """Get line count."""
        if hasattr(self._panel, "line_count"):
            return self._panel.line_count()
        return len(self._content)


@contextmanager
def tui_mode(title: str = "Omni Dev Fusion"):
    """Context manager for TUI mode.

    Usage:
        with tui_mode("My App") as tui:
            tui.add_result("Result", "Output...")
            # TUI will render after the context exits
    """
    bridge = TuiBridge(title)
    try:
        yield bridge
        # After yielding, the TUI can be rendered
        # bridge.run()  # Uncomment to enable blocking TUI
    except Exception as e:
        bridge.set_status(f"Error: {e}")
        raise


class CellOutput:
    """Represents output from an execution cell."""

    def __init__(self, cell_id: str, output: str, output_type: str = "text"):
        self.cell_id = cell_id
        self.output = output
        self.output_type = output_type

    def __str__(self) -> str:
        return self.output


class TuiCellRenderer:
    """Render cell outputs in TUI format."""

    def __init__(self, bridge: TuiBridge):
        """Initialize renderer."""
        self._bridge = bridge
        self._cell_counter = 0

    def render_cell(self, cell_output: CellOutput) -> None:
        """Render a cell output."""
        self._cell_counter += 1
        cell_title = f"Cell {self._cell_counter}: {cell_output.output_type}"
        self._bridge.add_result(cell_title, cell_output.output)


def create_cell_renderer(bridge: TuiBridge) -> TuiCellRenderer:
    """Create a cell renderer for the given bridge."""
    return TuiCellRenderer(bridge)


def check_tui_available() -> bool:
    """Check if TUI is available."""
    return _RUST_TUI_AVAILABLE


__all__ = [
    "TuiBridge",
    "TuiPanel",
    "TuiCellRenderer",
    "CellOutput",
    "tui_mode",
    "create_cell_renderer",
    "check_tui_available",
]
