"""
mcp.py - MCP Server Command

High-performance MCP Server using omni.mcp transport layer.

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

# CRITICAL: Python 3.13 compatibility fix - MUST be before ANY other imports
# Python 3.13 removed code.InteractiveConsole, but torch.distributed imports pdb
# which tries to use it at module load time. Add dummy class before any imports.
if sys.version_info >= (3, 13):
    import code

    if not hasattr(code, "InteractiveConsole"):

        class _DummyInteractiveConsole:
            def __init__(self, *args, **kwargs):
                pass

        code.InteractiveConsole = _DummyInteractiveConsole

# Also set the env var as a belt-and-suspenders measure
if sys.version_info >= (3, 13):
    if "TORCH_DISTRIBUTED_DETECTION" not in os.environ:
        os.environ["TORCH_DISTRIBUTED_DETECTION"] = "1"

import typer
from mcp import types
from rich.panel import Panel
from typing import TYPE_CHECKING, Any

from omni.foundation.config.logging import configure_logging, get_logger
from omni.foundation.utils.asyncio import run_async_blocking

if TYPE_CHECKING:
    from omni.agent.server import AgentMCPHandler

# =============================================================================
# Lightweight HTTP Server for Embedding (STDIO mode only)
# =============================================================================

import json as _json
from aiohttp import web as _web

_embedding_http_app = None
_embedding_http_runner = None


async def _handle_embedding_request(request: _web.Request) -> _web.Response:
    """Handle embedding requests via MCP tools/call protocol."""
    logger = get_logger("omni.mcp.embedding.http")

    try:
        # Parse JSON-RPC request
        body = await request.json()
        method = body.get("method", "")
        params = body.get("params", {})
        req_id = body.get("id")

        if method != "tools/call":
            return _web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )

        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Handle embedding tools
        if tool_name in ("embed_texts", "embedding.embed_texts"):
            texts = arguments.get("texts", [])
            if not texts:
                return _web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "'texts' parameter required"},
                    }
                )

            from omni.foundation.services.embedding import get_embedding_service

            embed_service = get_embedding_service()
            vectors = embed_service.embed_batch(texts)
            result = {
                "success": True,
                "count": len(vectors),
                "vectors": vectors,
                "preview": [v[:10] for v in vectors] if vectors else [],
            }

            return _web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": _json.dumps(result)}]},
                }
            )

        elif tool_name in ("embed_single", "embedding.embed_single"):
            text = arguments.get("text", "")
            if not text:
                return _web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": "'text' parameter required"},
                    }
                )

            from omni.foundation.services.embedding import get_embedding_service

            embed_service = get_embedding_service()
            vector = embed_service.embed(text)[0]
            result = {"success": True, "vector": vector, "preview": vector[:10] if vector else []}

            return _web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": _json.dumps(result)}]},
                }
            )

        else:
            return _web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown embedding tool: {tool_name}"},
                }
            )

    except Exception as e:
        logger.error(f"Embedding HTTP error: {e}")
        return _web.json_response(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
        )


async def _handle_embedding_health(_request: _web.Request) -> _web.Response:
    """Health endpoint for embedding HTTP service."""
    return _web.json_response({"status": "ok"})


async def _check_embedding_service(host: str = "127.0.0.1", port: int = 3001) -> bool:
    """Check if embedding HTTP service is already running on the port."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    except Exception:
        return False
    finally:
        sock.close()


async def _run_embedding_http_server(host: str = "127.0.0.1", port: int = 3001) -> bool:
    """Run a lightweight HTTP server for embedding requests (stdio mode only).

    This allows external tools like 'omni route test' to share the preloaded
    embedding model without reloading it.

    Returns:
        True if we started a new server, False if we connected to an existing one.
    """
    global _embedding_http_app, _embedding_http_runner, _i_started_server

    logger = get_logger("omni.mcp.embedding.http")

    # Check if service already exists
    if await _check_embedding_service(host, port):
        logger.info(f"🔌 Using existing embedding service on http://{host}:{port}")
        _i_started_server = False
        return False

    logger.info(f"🚀 Starting embedding HTTP server on http://{host}:{port}")

    _embedding_http_app = _web.Application()
    _embedding_http_app.router.add_post("/message", _handle_embedding_request)
    _embedding_http_app.router.add_get("/health", _handle_embedding_health)

    runner = _web.AppRunner(_embedding_http_app)
    await runner.setup()
    site = _web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"✅ Embedding HTTP server running on http://{host}:{port}")
    _embedding_http_runner = runner
    _i_started_server = True
    return True


async def _stop_embedding_http_server() -> None:
    """Stop the embedding HTTP server only if we started it."""
    global _embedding_http_runner, _i_started_server

    # Only stop if we started this server (to avoid shutting down shared service)
    if not _i_started_server or _embedding_http_runner is None:
        return

    logger = get_logger("omni.mcp.embedding.http")
    logger.info("Stopping embedding HTTP server...")
    await _embedding_http_runner.cleanup()
    _embedding_http_runner = None
    _i_started_server = False


# Track whether we started the server (for shared instance safety)
_i_started_server = False


# =============================================================================
# MCP Session Handler for SSE Transport
# =============================================================================


async def _run_mcp_session(
    handler: "AgentMCPHandler",
    read_stream: Any,
    write_stream: Any,
) -> None:
    """Run MCP session by processing messages from read_stream and writing to write_stream.

    This bridges the SSE transport streams with the AgentMCPHandler.
    """
    import anyio
    from mcp.types import JSONRPCRequest, JSONRPCResponse

    logger = get_logger("omni.mcp.session")

    async def read_messages():
        """Read messages from the read_stream and process them."""
        try:
            async for session_message in read_stream:
                # SessionMessage contains the MCP message
                message = session_message.message
                logger.debug(f"Received MCP message: {message.method}")

                # Handle the message using handler
                if hasattr(message, "id") and message.id is not None:
                    # It's a request (expects response)
                    request_dict = message.model_dump(by_alias=True, exclude_none=True)
                    response = await handler.handle_request(request_dict)
                    # Send response back
                    await write_stream.send(session_message.response(response))
                else:
                    # It's a notification (no response expected)
                    await handler.handle_notification(
                        message.method,
                        message.params.model_dump(by_alias=True) if message.params else None,
                    )
        except anyio.BrokenResourceError:
            logger.info("SSE session closed")
        except Exception as e:
            logger.error(f"Error in MCP session: {e}")

    # Run the message processing task
    await read_messages()


# =============================================================================

from ..console import err_console


# Transport mode enumeration
class TransportMode(str, Enum):
    stdio = "stdio"  # Production mode (Claude Desktop)
    sse = "sse"  # Development/debug mode (Claude Code CLI)


# Global for graceful shutdown
_shutdown_requested = False
_shutdown_count = 0  # For SSE mode signal handling
_handler_ref = None
_transport_ref = None  # For stdio transport stop


# =============================================================================
# Simple signal handler for stdio mode - mimics old stdio.py behavior
# =============================================================================

_stdio_shutdown_count = 0


def _setup_stdio_signal_handler() -> None:
    """Set up signal handler for stdio mode (simple approach)."""
    import sys as _sys

    def signal_handler(*_args):
        global _stdio_shutdown_count
        _stdio_shutdown_count += 1
        _sys.stderr.write(f"\n[CLI] Signal received! Count: {_stdio_shutdown_count}\n")
        _sys.stderr.flush()
        if _stdio_shutdown_count == 1:
            _sys.exit(0)  # Normal exit
        else:
            import os as _os

            _os._exit(1)  # Force exit on second Ctrl-C

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    _sys.stderr.write("[CLI] Signal handler registered\n")
    _sys.stderr.flush()


def _setup_signal_handler(handler_ref=None, transport_ref=None, stdio_mode=False) -> None:
    """Setup signal handlers for graceful shutdown."""
    global _shutdown_count

    def signal_handler(signum, frame):
        global _shutdown_requested, _shutdown_count
        _shutdown_requested = True
        _shutdown_count += 1

        if stdio_mode:
            # In stdio mode: first Ctrl-C = graceful exit, second = force exit
            import sys as _sys
            import os as _os

            try:
                if _shutdown_count == 1:
                    _sys.stderr.write("\n[CLI] Shutdown signal received, exiting...\n")
                    _sys.stderr.flush()
                    sys.exit(0)  # Allow graceful shutdown
                else:
                    _os._exit(1)  # Force exit on second Ctrl-C
            except Exception:
                _os._exit(1)

        # SSE mode: stop the transport first (breaks the run_loop)
        if transport_ref is not None:
            try:
                run_async_blocking(transport_ref.stop())
            except Exception:
                pass

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
            run_async_blocking(_graceful_shutdown(_handler_ref))
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
                log_level = "DEBUG" if verbose else "INFO"
                configure_logging(level=log_level)
                logger = get_logger("omni.mcp.stdio")

                async def run_stdio():
                    """Run stdio mode with embedding HTTP server."""
                    logger.info("📡 Starting Omni MCP Server (STDIO mode)")

                    # Initialize embedding service FIRST (auto-detects, starts HTTP server on 18501)
                    from omni.foundation.services.embedding import get_embedding_service

                    embed_svc = get_embedding_service()
                    embed_svc.initialize()  # This triggers auto-detection and HTTP server startup
                    logger.info("✅ Embedding service initialized")

                    # Run stdio server (it handles its own server/handler creation)
                    from omni.agent.mcp_server.stdio import run_stdio as old_run_stdio

                    # Start model loading AFTER stdio server starts (non-blocking)
                    embed_svc.start_model_loading()
                    logger.info("🔄 Embedding model loading in background...")

                    await old_run_stdio(verbose=verbose)

                    # Stop embedding HTTP server
                    await _stop_embedding_http_server()

                run_async_blocking(run_stdio())

            else:  # SSE mode - uses sse.py module
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

                # Create handler (lightweight, no initialization yet)
                from omni.agent.server import create_agent_handler

                handler = create_agent_handler()
                _handler_ref = handler

                # Import SSE server
                from omni.agent.mcp_server.sse import run_sse

                # Start SSE server FIRST (so MCP clients can connect immediately)
                # Use threading to run server in background while we initialize services
                import threading

                server_ready = threading.Event()
                server_error = [None]

                def run_server():
                    try:
                        asyncio.run(run_sse(handler, host, port))
                    except Exception as e:
                        server_error[0] = e

                server_thread = threading.Thread(target=run_server, daemon=True)
                server_thread.start()

                # Wait for server to be ready
                import time

                for _ in range(50):  # 5 seconds max wait
                    time.sleep(0.1)
                    try:
                        import httpx

                        resp = httpx.get(f"http://{host}:{port}/health", timeout=0.5)
                        if resp.status_code == 200:
                            break
                    except Exception:
                        pass
                else:
                    logger.warning("Server health check timed out, continuing...")

                logger.info(f"✅ SSE server started on http://{host}:{port}")

                # Now initialize services in background
                # Initialize embedding service
                from omni.foundation.services.embedding import get_embedding_service

                embed_svc = get_embedding_service()
                embed_svc.initialize()
                logger.info("✅ Embedding service initialized")

                # Initialize handler
                run_async_blocking(handler.initialize())
                logger.info("✅ MCP handler initialized")

                # Start model loading in background
                embed_svc.start_model_loading()
                logger.info("🔄 Embedding model loading in background...")

                # Keep main thread alive
                try:
                    server_thread.join()
                except KeyboardInterrupt:
                    logger.info("Server stopped")

                def shutdown_handler(signum, frame):
                    logger.info("Shutdown signal received")
                    raise KeyboardInterrupt()

                signal.signal(signal.SIGINT, shutdown_handler)
                signal.signal(signal.SIGTERM, shutdown_handler)

                # Run SSE server
                asyncio.run(run_sse(handler, host, port))

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
