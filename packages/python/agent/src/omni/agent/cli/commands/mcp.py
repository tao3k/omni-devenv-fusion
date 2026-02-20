"""
mcp.py - MCP Server Command

High-performance MCP Server using omni.mcp transport layer.

Usage:
    omni mcp --transport stdio     # Claude Desktop (default)
    omni mcp --transport sse --port 3000  # Claude Code CLI / debugging
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
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
from typing import Any

from omni.agent.mcp_server.startup import (
    initialize_handler_on_server_loop as _initialize_handler_on_server_loop,
    wait_for_sse_server_readiness as _wait_for_sse_server_readiness,
)
from omni.foundation.config.logging import configure_logging, get_logger
from omni.foundation.utils.asyncio import run_async_blocking

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
            start = time.perf_counter()
            vectors = await asyncio.to_thread(embed_service.embed_batch, texts)
            duration_ms = (time.perf_counter() - start) * 1000.0
            result = {
                "success": True,
                "count": len(vectors),
                "vectors": vectors,
                "preview": [v[:10] for v in vectors] if vectors else [],
            }
            logger.debug(
                "embedding_http_embed_texts_done count=%s duration_ms=%.2f",
                len(vectors),
                duration_ms,
            )

            return _web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": _json.dumps(result)}],
                        "isError": False,
                    },
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
            start = time.perf_counter()
            vectors = await asyncio.to_thread(embed_service.embed, text)
            vector = vectors[0] if vectors else []
            duration_ms = (time.perf_counter() - start) * 1000.0
            result = {"success": True, "vector": vector, "preview": vector[:10] if vector else []}
            logger.debug("embedding_http_embed_single_done duration_ms=%.2f", duration_ms)

            return _web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": _json.dumps(result)}],
                        "isError": False,
                    },
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


def _is_transient_embedding_warm_error(error: Exception) -> bool:
    message = str(error).lower()
    transient_markers = (
        "apiconnectionerror",
        "server disconnected without sending a response",
        "connection refused",
        "failed to connect",
        "remoteprotocolerror",
        "temporarily unavailable",
        "read timeout",
        "connect timeout",
    )
    return any(marker in message for marker in transient_markers)


async def _warm_embedding_after_startup(
    timeout_seconds: float = 8.0,
    *,
    max_attempts: int = 8,
    retry_delay_seconds: float = 0.3,
) -> None:
    """Warm embedding backend with bounded timeout and transient-connection retries."""
    logger = get_logger("omni.mcp.embedding")
    try:
        from omni.foundation.services.embedding import get_embedding_service

        embed_svc = get_embedding_service()
        if embed_svc.backend == "unavailable":
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(timeout_seconds, 0.1)
        attempts = 0
        last_error: Exception | None = None

        while attempts < max(1, max_attempts):
            attempts += 1
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: embed_svc.embed("_warm_")),
                    timeout=remaining,
                )
                logger.info(
                    "Embedding model warmed (Ollama model loaded for fast first request) "
                    "attempt=%s/%s",
                    attempts,
                    max(1, max_attempts),
                )
                return
            except asyncio.TimeoutError:
                logger.warning(
                    "Embedding warm timed out after %.1fs; continue startup", timeout_seconds
                )
                return
            except Exception as error:
                last_error = error
                if not _is_transient_embedding_warm_error(error):
                    logger.warning("Embedding warm skipped: %s", error)
                    return
                if attempts >= max(1, max_attempts):
                    break
                logger.info(
                    "Embedding warm transient failure; retrying (attempt=%s/%s): %s",
                    attempts,
                    max(1, max_attempts),
                    error,
                )
                sleep_seconds = min(max(retry_delay_seconds, 0.0), max(0.0, deadline - loop.time()))
                if sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)

        if last_error is not None:
            logger.warning(
                "Embedding warm skipped after %s attempts: %s",
                attempts,
                last_error,
            )
    except asyncio.TimeoutError:
        logger.warning("Embedding warm timed out after %.1fs; continue startup", timeout_seconds)
    except Exception as e:
        logger.warning("Embedding warm skipped: %s", e)


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
_server_loop_ref: asyncio.AbstractEventLoop | None = None


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
            _stop_transport_for_shutdown(transport_ref)

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


def _run_coroutine_for_shutdown(
    coro: Any,
    *,
    timeout_seconds: float,
    action: str,
) -> None:
    """Run shutdown coroutine on the SSE server loop when available."""
    loop = _server_loop_ref
    if loop is not None and loop.is_running() and not loop.is_closed():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            future.result(timeout=timeout_seconds)
            return
        except FutureTimeoutError as e:
            future.cancel()
            raise TimeoutError(f"{action} timed out after {timeout_seconds}s") from e
    run_async_blocking(coro)


def _stop_transport_for_shutdown(transport_ref, *, timeout_seconds: float = 10.0) -> None:
    """Stop transport during shutdown without crossing event loops."""
    logger = get_logger("omni.mcp.shutdown")
    try:
        _run_coroutine_for_shutdown(
            transport_ref.stop(),
            timeout_seconds=timeout_seconds,
            action="transport stop",
        )
    except Exception as e:
        logger.warning("Transport stop failed during shutdown: %s", e)


def _stop_ollama_if_started() -> None:
    """Stop the Ollama subprocess if we started it (MCP exit)."""
    from omni.agent.ollama_lifecycle import _stop_managed_ollama

    _stop_managed_ollama()


def _sync_graceful_shutdown() -> None:
    """Sync wrapper for graceful shutdown (for signal handler)."""
    global _handler_ref
    logger = get_logger("omni.mcp.shutdown")
    _stop_ollama_if_started()
    if _handler_ref is not None:
        try:
            _run_coroutine_for_shutdown(
                _graceful_shutdown(_handler_ref),
                timeout_seconds=30.0,
                action="graceful shutdown",
            )
        except Exception as e:
            logger.error("Graceful shutdown failed: %s", e)


def register_mcp_command(app_instance: typer.Typer) -> None:
    """Register mcp command directly with the main app."""
    from omni.agent.cli.load_requirements import register_requirements

    register_requirements("mcp", ollama=True, embedding_index=True)

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
        no_embedding: bool = typer.Option(
            False,
            "--no-embedding",
            help="Skip embedding service (lightweight mode; knowledge.recall will fail)",
        ),
    ):
        """
        Start Omni MCP Server with high-performance omni.mcp transport layer.

        Uses Rust-powered orjson for 10-50x faster JSON serialization.
        """
        global _handler_ref, _transport_ref, _server_loop_ref

        try:
            if transport == TransportMode.stdio:
                # Configure logging (stdout is used by MCP, so log to stderr)
                log_level = "DEBUG" if verbose else "INFO"
                configure_logging(level=log_level)
                if not verbose:
                    logging.getLogger("litellm").setLevel(logging.WARNING)
                    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
                logger = get_logger("omni.mcp.stdio")

                async def run_stdio():
                    """Run stdio mode with embedding HTTP server."""
                    logger.info("📡 Starting Omni MCP Server (STDIO mode)")

                    if not no_embedding:
                        # If embedding.provider is ollama, ensure Ollama is running (may already be from entry_point).
                        from omni.agent.ollama_lifecycle import ensure_ollama_for_embedding

                        ensure_ollama_for_embedding()
                        # MCP must not load the embedding model in-process (keeps memory low).
                        # Use client-only: connect to an existing embedding service; never start local server.
                        os.environ["OMNI_EMBEDDING_CLIENT_ONLY"] = "1"
                        from omni.foundation.services.embedding import get_embedding_service

                        embed_svc = get_embedding_service()
                        embed_svc.initialize()
                        if embed_svc.backend == "http":
                            logger.info("✅ Embedding: client mode (using existing service)")
                        elif embed_svc.backend == "litellm":
                            logger.info("✅ Embedding: LiteLLM backend (Ollama/Xinference) ready")
                        elif embed_svc.backend == "unavailable":
                            logger.warning(
                                "Embedding service unreachable; cortex indexing will be skipped. "
                                "Start Ollama (or set embedding.provider=ollama and run omni mcp) or an embedding HTTP service (e.g. port 18501)."
                            )
                        else:
                            logger.info("✅ Embedding: %s mode", embed_svc.backend)
                        if embed_svc.backend != "unavailable":
                            await _warm_embedding_after_startup()
                    else:
                        logger.info("⏭️ Embedding service skipped (--no-embedding)")

                    # Run stdio server (it handles its own server/handler creation)
                    from omni.agent.mcp_server.stdio import run_stdio as old_run_stdio

                    await old_run_stdio(verbose=verbose)

                    # Stop embedding HTTP server (only if we started it)
                    if not no_embedding:
                        await _stop_embedding_http_server()
                    _stop_ollama_if_started()

                run_async_blocking(run_stdio())

            else:  # SSE mode - uses sse.py module
                # Configure logging
                log_level = "DEBUG" if verbose else "INFO"
                configure_logging(level=log_level)
                if not verbose:
                    logging.getLogger("litellm").setLevel(logging.WARNING)
                    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
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
                handler.set_verbose(verbose)
                _handler_ref = handler

                # Import SSE server
                from omni.agent.mcp_server.sse import run_sse

                # Start SSE server FIRST (so MCP clients can connect immediately)
                # Use threading to run server in background while we initialize services
                import threading

                server_loop_ready = threading.Event()
                server_loop_holder: dict[str, asyncio.AbstractEventLoop] = {}
                server_error = [None]

                def run_server():
                    global _server_loop_ref
                    loop = asyncio.new_event_loop()
                    try:
                        asyncio.set_event_loop(loop)
                        _server_loop_ref = loop
                        server_loop_holder["loop"] = loop
                        server_loop_ready.set()
                        loop.run_until_complete(run_sse(handler, host, port))
                    except Exception as e:
                        server_error[0] = e
                    finally:
                        if _server_loop_ref is loop:
                            _server_loop_ref = None
                        server_loop_ready.set()
                        if not loop.is_closed():
                            loop.close()

                server_thread = threading.Thread(target=run_server, daemon=True)
                server_thread.start()
                server_loop_ready.wait(timeout=2.0)

                # Wait for server readiness and fail fast if startup failed.
                _wait_for_sse_server_readiness(host, port, server_thread, server_error)

                logger.info(f"✅ SSE server started on http://{host}:{port}")

                # Initialize handler first so MCP initialize/tool discovery can respond quickly.
                server_loop = server_loop_holder.get("loop")
                init_started = time.perf_counter()
                if server_loop is not None and server_loop.is_running():
                    _initialize_handler_on_server_loop(handler, server_loop, timeout_seconds=90.0)
                else:
                    logger.warning(
                        "SSE server loop unavailable for handler init; falling back to temporary loop"
                    )
                    run_async_blocking(handler.initialize())
                logger.info(
                    "✅ MCP handler initialized (init_ms=%.1f)",
                    (time.perf_counter() - init_started) * 1000.0,
                )

                # Initialize embedding services after MCP handler is ready.
                if not no_embedding:
                    # If embedding.provider is ollama, ensure Ollama is running (may already be from entry_point).
                    from omni.agent.ollama_lifecycle import ensure_ollama_for_embedding

                    ensure_ollama_for_embedding()
                    # MCP must not load the embedding model in-process (keeps memory low).
                    os.environ["OMNI_EMBEDDING_CLIENT_ONLY"] = "1"
                    from omni.foundation.services.embedding import get_embedding_service

                    embed_svc = get_embedding_service()
                    embed_svc.initialize()
                    if embed_svc.backend == "http":
                        logger.info("✅ Embedding: client mode (using existing service)")
                    elif embed_svc.backend == "litellm":
                        logger.info("✅ Embedding: LiteLLM backend (Ollama/Xinference) ready")
                    elif embed_svc.backend == "unavailable":
                        logger.warning(
                            "Embedding service unreachable; cortex indexing will be skipped. "
                            "Start Ollama (or set embedding.provider=ollama and run omni mcp) or an embedding HTTP service (e.g. port 18501)."
                        )
                    else:
                        logger.info("✅ Embedding: %s mode", embed_svc.backend)
                    if embed_svc.backend != "unavailable":
                        run_async_blocking(_warm_embedding_after_startup())
                else:
                    logger.info("⏭️ Embedding service skipped (--no-embedding)")

                # Keep main thread alive until server thread exits (e.g. Ctrl+C)
                try:
                    server_thread.join()
                except KeyboardInterrupt:
                    logger.info("Server stopped")

                # Server thread exited; run graceful shutdown and exit (do not start server again)
                shutdown_logger = get_logger("omni.mcp.shutdown")
                shutdown_logger.info("👋 Shutting down...")
                _sync_graceful_shutdown()
                sys.exit(0)

        except KeyboardInterrupt:
            shutdown_logger = get_logger("omni.mcp.shutdown")
            shutdown_logger.info("👋 Server interrupted by user")
            if _handler_ref is not None:
                _sync_graceful_shutdown()
            sys.exit(0)
        except Exception as e:
            from omni.foundation.services.embedding import EmbeddingPortInUseError

            if isinstance(e, EmbeddingPortInUseError):
                err_console.print(
                    Panel(
                        f"[bold red]Embedding port conflict:[/bold red]\n\n{e}\n\n"
                        "Edit packages/conf/settings.yaml and set embedding.http_port to a free port.",
                        style="red",
                    )
                )
            else:
                err_console.print(Panel(f"[bold red]Server Error:[/bold red] {e}", style="red"))
            if _handler_ref is not None:
                _sync_graceful_shutdown()
            sys.exit(1)

    __all__ = ["register_mcp_command"]
