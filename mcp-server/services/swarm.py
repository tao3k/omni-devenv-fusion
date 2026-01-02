# mcp-server/services/swarm.py
"""
Swarm Infrastructure v2 (Robust Edition)
Handles process lifecycle, IPC (Inter-Process Communication), and error recovery.
"""
import sys
import os
import asyncio
import json
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Optional, Dict, List, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Tool

# Default timeout settings
CONNECT_TIMEOUT = 10.0  # seconds
EXECUTION_TIMEOUT = 120.0 # seconds

class SwarmNode:
    """
    A single worker node running in a subprocess.
    """
    def __init__(self, name: str, script_path: str, env: Optional[Dict[str, str]] = None):
        self.name = name
        self.script_path = Path(script_path).resolve()
        self.env = env or {}
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self._proc = None
        self._connected = False

    async def connect(self) -> bool:
        """Launches the subprocess and establishes the MCP session."""
        if not self.script_path.exists():
            print(f"[Swarm] Node {self.name}: Script not found at {self.script_path}", file=sys.stderr)
            return False

        print(f"[Swarm] Connecting to {self.name}...", file=sys.stderr)

        # 1. Environment Preparation
        # Inherit current environment, override key variables
        worker_env = os.environ.copy()
        worker_env.update(self.env)

        # [CRITICAL] Force disable Python output buffering
        # This is the core fix for "Honking..."/"Churning..." deadlock
        worker_env["PYTHONUNBUFFERED"] = "1"

        # [CRITICAL] Inject PYTHONPATH
        # Ensure Worker can find modules in mcp-server root (e.g., coder.py, mcp_core)
        # Directory structure: mcp-server/services/swarm.py -> parent -> parent -> mcp-server root
        server_root = Path(__file__).parent.parent.resolve()
        current_path = worker_env.get("PYTHONPATH", "")
        worker_env["PYTHONPATH"] = f"{server_root}:{current_path}"

        # 2. Define subprocess parameters
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(self.script_path)],
            env=worker_env
        )

        try:
            # 3. Connection attempt with timeout
            async with asyncio.timeout(CONNECT_TIMEOUT):
                # Establish Stdio pipe
                read, write = await self.exit_stack.enter_async_context(
                    stdio_client(server_params)
                )

                # Establish MCP session
                self.session = await self.exit_stack.enter_async_context(
                    ClientSession(read, write)
                )

                await self.session.initialize()

            self._connected = True
            print(f"[Swarm] Linked to {self.name}", file=sys.stderr)
            return True

        except TimeoutError:
            print(f"[Swarm] Connection timed out for {self.name} ({CONNECT_TIMEOUT}s)", file=sys.stderr)
            await self.close()
            return False
        except Exception as e:
            print(f"[Swarm] Failed to connect to {self.name}: {e}", file=sys.stderr)
            await self.close()
            return False

    async def list_tools(self) -> List[Tool]:
        """List tools with safety checks."""
        if not self.is_connected:
            raise RuntimeError(f"Node {self.name} is not connected")

        try:
            result = await self.session.list_tools()
            return result.tools
        except Exception as e:
            print(f"[Swarm] Error listing tools for {self.name}: {e}", file=sys.stderr)
            return []

    async def call_tool(self, name: str, arguments: dict) -> CallToolResult:
        """Call tool with Execution Timeout."""
        if not self.is_connected:
            raise RuntimeError(f"Node {self.name} is not connected")

        try:
            # [CRITICAL] Execution timeout protection
            async with asyncio.timeout(EXECUTION_TIMEOUT):
                return await self.session.call_tool(name, arguments)
        except TimeoutError:
            raise TimeoutError(f"Tool execution '{name}' timed out after {EXECUTION_TIMEOUT}s")
        except Exception as e:
            raise RuntimeError(f"Tool execution failed: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected and self.session is not None

    async def close(self):
        """Graceful shutdown."""
        self._connected = False
        try:
            await self.exit_stack.aclose()
        except Exception:
            pass
        print(f"[Swarm] Disconnected {self.name}", file=sys.stderr)

# Singleton manager (optional, for Orchestrator)
class SwarmManager:
    _instance = None

    def __init__(self):
        self.nodes = {}

    def register(self, name: str, script_path: str):
        self.nodes[name] = SwarmNode(name, script_path)

    async def get_or_connect(self, name: str) -> Optional[SwarmNode]:
        node = self.nodes.get(name)
        if not node:
            return None

        if not node.is_connected:
            success = await node.connect()
            if not success:
                return None
        return node
