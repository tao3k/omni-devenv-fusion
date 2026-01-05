"""
src/agent/dashboard.py
The Sidecar Dashboard - Replays events from the MCP Server.

Usage:
    # Terminal 2: Run the dashboard
    $ python -m agent.dashboard

    # Or using the CLI script (after pyproject.toml update)
    $ omni monitor

This script tails the event log and replays UI events in real-time.
"""

import time
import json
import os
import sys
from pathlib import Path

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from agent.core.ux import UXManager, EVENT_LOG_PATH


def tail_events(filepath: Path):
    """
    Generator that yields new lines from a file (like tail -f).
    """
    filepath = Path(filepath)

    # Ensure file exists
    if not filepath.exists():
        filepath.touch()

    with open(filepath, "r") as f:
        # Move to end to avoid replaying old history
        f.seek(0, 2)

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.05)
                continue
            yield line


def clear_event_log() -> None:
    """Clear the event log on startup."""
    if EVENT_LOG_PATH.exists():
        with open(EVENT_LOG_PATH, "w") as f:
            f.write("")


def run_dashboard(clear_log: bool = True) -> None:
    """
    Run the sidecar dashboard.

    Args:
        clear_log: Whether to clear the event log on startup.
    """
    # Clear old events if requested
    if clear_log:
        clear_event_log()

    # Force UXManager into TUI rendering mode
    ux = UXManager(force_mode="tui")
    console = Console()

    # Clear screen and show header
    console.clear()
    console.rule("[bold cyan]Omni-DevEnv Glass Cockpit[/]")
    console.print(f"[dim]Listening for events at {EVENT_LOG_PATH}...[/]")
    console.print("[dim]Press Ctrl+C to stop.[/]")
    console.print()

    try:
        for line in tail_events(EVENT_LOG_PATH):
            try:
                event = json.loads(line)
                method_name = event.get("method")
                params = event.get("params", {})

                # Try to call the render method directly
                render_method = getattr(ux, f"_render_{method_name}", None)

                if render_method and callable(render_method):
                    render_method(**params)
                else:
                    # Fallback: try calling the public method (should work in tui mode)
                    public_method = getattr(ux, method_name, None)
                    if public_method and callable(public_method):
                        public_method(**params)

            except json.JSONDecodeError:
                # Skip malformed lines
                continue
            except Exception as e:
                console.print(f"[red]Error processing event: {e}[/]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/]")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Omni-DevEnv Sidecar Dashboard - Visualize agent operations in real-time"
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear the event log on startup (replay historical events)",
    )
    args = parser.parse_args()

    run_dashboard(clear_log=not args.no_clear)


if __name__ == "__main__":
    main()
