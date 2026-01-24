"""
agent/mcp_server/server.py - Agent MCP Server Entry Point

Trinity Architecture - Agent Layer

Migrated to use the Trinity Architecture:
- Framework: omni.mcp (Generic MCP Package)
- Handler: omni.agent.server.AgentMCPHandler (Thin Client)
- Logging: omni.foundation.config.logging (Foundation Layer)

Usage:
    # STDIO mode (for Claude Desktop/CLI)
    python -m omni.agent.mcp_server.server

    # SSE mode (for HTTP clients)
    python -m omni.agent.mcp_server.server --sse --port 8080
"""

from __future__ import annotations

import asyncio

from omni.agent.server import create_agent_handler
from omni.foundation.config.logging import configure_logging, get_logger
from omni.mcp.server import MCPServer
from omni.mcp.transport.sse import SSEServer
from omni.mcp.transport.stdio import StdioTransport


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging using Foundation layer.

    Must be called BEFORE any get_logger() calls to ensure proper configuration.
    """
    level = "DEBUG" if verbose else "INFO"
    configure_logging(level=level, verbose=verbose)


def _get_logger(name: str):
    """Get logger after logging is configured.

    This wrapper ensures logging is configured before getting the logger.
    """
    configure_logging(level="INFO")  # Ensure logging is configured
    return get_logger(name)


async def run_stdio_server(verbose: bool = False) -> None:
    """Run the Agent in STDIO mode (for Claude Desktop/CLI)."""
    logger = _get_logger("omni.agent.boot")
    logger.info("🚀 Starting Agent MCP Server (STDIO Mode)")

    # Create Handler (The Brain - connects to Kernel)
    handler = create_agent_handler()

    # Enable verbose mode for hot reload in development
    if verbose:
        handler.set_verbose(True)

    # Create Transport (The Ear/Mouth)
    transport = StdioTransport()

    # Create Server (The Body)
    server = MCPServer(handler, transport)

    # Run
    try:
        await server.start()
        await server.run_forever()
    except KeyboardInterrupt:
        logger.info("👋 STDIO server interrupted")
    except Exception as e:
        logger.error("💥 Server crashed", error=str(e))
        raise


async def run_sse_server(port: int = 8080, verbose: bool = False) -> None:
    """Run the Agent in SSE mode (for HTTP Clients)."""
    logger = _get_logger("omni.agent.boot")
    logger.info(f"🚀 Starting Agent MCP Server (SSE Mode on port {port})")

    # Create Handler
    handler = create_agent_handler()

    if verbose:
        handler.set_verbose(True)

    # Create SSE Server (standalone, not using MCPServer)
    server = SSEServer(handler, host="0.0.0.0", port=port)

    # Run
    try:
        await server.start()
        # SSEServer handles its own loop
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("👋 SSE server interrupted")
    except Exception as e:
        logger.error("💥 Server crashed", error=str(e))
        raise


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Omni Agent MCP Server")
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Run in SSE mode instead of STDIO",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for SSE mode (default: 8080)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose mode (debug logging)",
    )

    args = parser.parse_args()

    # Configure logging using Foundation layer
    _setup_logging(verbose=args.verbose)

    if args.sse:
        asyncio.run(run_sse_server(port=args.port, verbose=args.verbose))
    else:
        asyncio.run(run_stdio_server(verbose=args.verbose))


if __name__ == "__main__":
    main()
