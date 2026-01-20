"""
mcp.py - MCP Server Command

Phase 35.2: Modular CLI Architecture with Transport Support

Provides MCP server command with dual transport modes:
- stdio: Production mode for Claude Desktop
- sse: Development/debug mode for Claude Code CLI

Usage:
    omni mcp --transport stdio     # Claude Desktop (default)
    omni mcp --transport sse --port 3000  # Claude Code CLI / debugging
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from enum import Enum

import typer
from rich.panel import Panel

from ..console import err_console
from common.log_config import configure_logging


# Transport mode enumeration
class TransportMode(str, Enum):
    stdio = "stdio"  # Production mode (Claude Desktop)
    sse = "sse"  # Development/debug mode (Claude Code CLI)


def _setup_signal_handlers() -> None:
    """Set up immediate exit handlers for stdio mode."""

    def _exit_now(signum, frame):
        err_console.print("[yellow]📡 Interrupted, exiting immediately...[/yellow]")
        # Force exit immediately (bypasses all cleanup)
        os._exit(0)

    signal.signal(signal.SIGINT, _exit_now)
    signal.signal(signal.SIGTERM, _exit_now)


def register_mcp_command(app_instance: typer.Typer) -> None:
    """Register mcp command directly with the main app."""

    @app_instance.command("mcp", help="Start Omni MCP Server")
    def run_mcp(
        transport: TransportMode = typer.Option(
            TransportMode.sse,  # Default to SSE for Claude Code CLI
            "--transport",
            "-t",
            help="Communication transport mode (stdio for Claude Desktop, sse for Claude Code CLI)",
        ),
        host: str = typer.Option(
            "127.0.0.1",
            "--host",
            "-h",
            help="Host to bind to (SSE only, 127.0.0.1 for local security)",
        ),
        port: int = typer.Option(
            3000,
            "--port",
            "-p",
            help="Port to listen on (only for SSE mode, use 0 for random)",
        ),
    ):
        """
        Start the Omni MCP Server.

        Use --transport stdio for Claude Desktop.
        Use --transport sse for Claude Code CLI or debugging.
        """
        # Configure logging based on transport mode
        if transport == TransportMode.stdio:
            configure_logging(level="INFO")
            # Set up immediate exit handlers BEFORE any async code
            _setup_signal_handlers()
        else:
            configure_logging(level="DEBUG")
            err_console.print(
                Panel(
                    f"[bold green]🚀 Starting Omni MCP in {transport.value.upper()} mode on port {port}[/bold green]",
                    style="green",
                )
            )

        # Import and run the server
        try:
            from agent.mcp_server import run

            asyncio.run(run(transport=transport.value, host=host, port=port))
        except KeyboardInterrupt:
            sys.exit(0)
        except Exception as e:
            err_console.print(Panel(f"[bold red]Server Error:[/bold red] {e}", style="red"))
            sys.exit(1)

    __all__ = ["register_mcp_command"]
