"""
mcp.py - MCP Server Command

High-performance MCP Server using omni.mcp transport layer.

Usage:
    omni mcp --transport stdio     # Claude Desktop (default)
    omni mcp --transport sse --port 3000  # Claude Code CLI / debugging
"""

from __future__ import annotations

import asyncio
import signal
import sys
from enum import Enum

import typer
from rich.panel import Panel

from omni.foundation.config.logging import configure_logging, get_logger

from ..console import err_console


# Transport mode enumeration
class TransportMode(str, Enum):
    stdio = "stdio"  # Production mode (Claude Desktop)
    sse = "sse"  # Development/debug mode (Claude Code CLI)


# Global for graceful shutdown
_shutdown_requested = False
_handler_ref = None
_transport_ref = None  # For stdio transport stop


def _setup_signal_handler(handler_ref=None, transport_ref=None, stdio_mode=False) -> None:
    """Setup signal handlers for graceful shutdown."""

    def signal_handler(signum, frame):
        global _shutdown_requested
        _shutdown_requested = True
        logger = get_logger("omni.mcp.shutdown")
        logger.warning("⚠️  Received shutdown signal, gracefully stopping...")

        if stdio_mode:
            # In stdio mode, just exit cleanly - the process communicates via stdin/stdout
            # with the MCP client, so we should just exit on interrupt
            logger.info("👋 Exiting stdio mode...")
            sys.exit(0)
        else:
            # SSE mode: stop the transport first (breaks the run_loop)
            if transport_ref is not None:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(transport_ref.stop())
                    loop.close()
                    logger.debug("Transport stopped")
                except Exception as e:
                    logger.error(f"Error stopping transport: {e}")

            _sync_graceful_shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def _graceful_shutdown(handler) -> None:
    """Perform graceful shutdown of kernel and server."""
    logger = get_logger("omni.mcp.shutdown")

    try:
        # Shutdown kernel gracefully
        if hasattr(handler, "_kernel") and handler._kernel is not None:
            kernel = handler._kernel
            if kernel.is_ready or kernel.state.value in ("ready", "running"):
                logger.info("🛑 Initiating graceful shutdown...")
                await kernel.shutdown()
                logger.info("✅ Kernel shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


def _sync_graceful_shutdown() -> None:
    """Sync wrapper for graceful shutdown (for signal handler)."""
    global _handler_ref
    if _handler_ref is not None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_graceful_shutdown(_handler_ref))
            finally:
                loop.close()
        except Exception:
            pass


def register_mcp_command(app_instance: typer.Typer) -> None:
    """Register mcp command directly with the main app."""

    @app_instance.command("mcp", help="Start Omni MCP Server (Level 2 Transport)")
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
        verbose: bool = typer.Option(
            False,
            "--verbose",
            "-v",
            help="Enable verbose mode (hot reload, debug logging)",
        ),
    ):
        """
        Start Omni MCP Server with high-performance omni.mcp transport layer.

        Uses Rust-powered orjson for 10-50x faster JSON serialization.
        """
        global _handler_ref, _transport_ref

        try:
            if transport == TransportMode.stdio:
                # Configure logging (stdout is used by MCP, so log to stderr)
                configure_logging(level="INFO")
                logger = get_logger("omni.mcp.stdio")

                # Use omni.mcp transport with AgentMCPHandler
                from omni.agent.server import create_agent_handler
                from omni.mcp import MCPServer
                from omni.mcp.transport.stdio import StdioTransport

                handler = create_agent_handler()
                _handler_ref = handler  # Store for signal handler

                # Create stdio transport
                stdio_transport = StdioTransport()
                _transport_ref = stdio_transport  # Store for signal handler
                _setup_signal_handler(handler, stdio_transport, stdio_mode=True)

                server = MCPServer(handler=handler, transport=stdio_transport)

                async def run_stdio():
                    try:
                        await handler.initialize()
                        await server.start()
                        await stdio_transport.run_loop(server)
                    except asyncio.CancelledError:
                        logger.info("STDIO loop cancelled")
                        await _graceful_shutdown(handler)

                logger.info("📡 Starting Omni MCP Server (STDIO mode)")
                asyncio.run(run_stdio())

            else:  # SSE mode
                # Configure logging
                log_level = "DEBUG" if verbose else "INFO"
                configure_logging(level=log_level)
                logger = get_logger("omni.mcp.sse")

                err_console.print(
                    Panel(
                        f"[bold green]🚀 Starting Omni MCP in {transport.value.upper()} mode on port {port}[/bold green]"
                        + (" [cyan](verbose, hot-reload enabled)[/cyan]" if verbose else ""),
                        style="green",
                    )
                )

                # Use omni.mcp SSE transport with AgentMCPHandler
                from omni.agent.server import create_agent_handler
                from omni.mcp import MCPServer
                from omni.mcp.transport.sse import SSEServer

                handler = create_agent_handler()
                _handler_ref = handler
                _setup_signal_handler(handler)

                server = SSEServer(handler, host=host, port=port)

                async def run_sse():
                    try:
                        await handler.initialize()
                        await server.start()
                        # Keep running until interrupted
                        while not _shutdown_requested:
                            await asyncio.sleep(1)
                        await server.stop()  # Stop SSE server
                        await _graceful_shutdown(handler)
                    except asyncio.CancelledError:
                        logger.info("SSE server cancelled")
                        await _graceful_shutdown(handler)

                asyncio.run(run_sse())

        except KeyboardInterrupt:
            shutdown_logger = get_logger("omni.mcp.shutdown")
            shutdown_logger.info("👋 Server interrupted by user")
            if _handler_ref is not None:
                _sync_graceful_shutdown()
            sys.exit(0)
        except Exception as e:
            err_console.print(Panel(f"[bold red]Server Error:[/bold red] {e}", style="red"))
            if _handler_ref is not None:
                _sync_graceful_shutdown()
            sys.exit(1)

    __all__ = ["register_mcp_command"]
