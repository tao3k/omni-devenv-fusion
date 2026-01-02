# mcp-server/services/swarm.py
"""
Swarm Infrastructure v3 (Antifragile Edition)
Features: Auto-Reconnect, Circuit Breaker, Health Checks, and Metrics.
"""
import sys
import os
import asyncio
import time
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, Tool

# --- Configuration ---
CONNECT_TIMEOUT = 10.0  # Connection timeout
EXECUTION_TIMEOUT = 120.0  # Execution timeout
MAX_RETRIES = 2  # Auto-retry on failure
CIRCUIT_BREAKER_COOLDOWN = 30.0  # Circuit breaker cooldown in seconds

@dataclass
class NodeMetrics:
    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_failure_time: float = 0.0
    last_error: str = ""
    restarts: int = 0
    avg_latency_ms: float = 0.0

class SwarmNode:
    """
    A self-healing worker node with circuit breaker pattern.
    """
    def __init__(self, name: str, script_path: str, env: Optional[Dict[str, str]] = None):
        self.name = name
        self.script_path = Path(script_path).resolve()
        self.env = env or {}
        self.metrics = NodeMetrics()

        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self._connected = False
        self._circuit_open_until = 0.0

    @property
    def is_connected(self) -> bool:
        # Even if connection flag is True, if circuit breaker is open, treat as disconnected
        if time.time() < self._circuit_open_until:
            return False
        return self._connected and self.session is not None

    async def connect(self) -> bool:
        """Establishes connection with circuit breaker check."""
        # 1. Circuit breaker check
        if time.time() < self._circuit_open_until:
            print(f"🛡️ [Swarm] {self.name} is fused. Cooldown until {self._circuit_open_until:.0f}s", file=sys.stderr)
            return False

        if not self.script_path.exists():
            self._record_failure(f"Script not found: {self.script_path}")
            return False

        print(f"🔌 [Swarm] Connecting to {self.name}...", file=sys.stderr)

        # 2. Environment injection (Critical fix)
        worker_env = os.environ.copy()
        worker_env.update(self.env)
        worker_env["PYTHONUNBUFFERED"] = "1"

        # Inject PYTHONPATH
        server_root = Path(__file__).parent.parent.resolve()
        current_path = worker_env.get("PYTHONPATH", "")
        worker_env["PYTHONPATH"] = f"{server_root}:{current_path}"

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(self.script_path)],
            env=worker_env
        )

        try:
            # 3. Connection with timeout
            async with asyncio.timeout(CONNECT_TIMEOUT):
                read, write = await self.exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                self.session = await self.exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await self.session.initialize()

            self._connected = True
            print(f"✅ [Swarm] Linked to {self.name}", file=sys.stderr)
            return True

        except Exception as e:
            self._record_failure(f"Connection failed: {e}")
            await self.close()
            return False

    async def call_tool(self, name: str, arguments: dict, retries: int = MAX_RETRIES) -> CallToolResult:
        """Execute tool with Auto-Retry and Metrics."""
        self.metrics.total_calls += 1
        start_time = time.time()

        # 1. Circuit breaker check
        if time.time() < self._circuit_open_until:
            raise RuntimeError(f"Node {self.name} circuit is OPEN. Try again later.")

        # 2. Auto-reconnect (Auto-Healing)
        if not self.is_connected:
            if not await self.connect():
                raise RuntimeError(f"Node {self.name} is unreachable (Connect failed).")

        try:
            # 3. Execute tool
            async with asyncio.timeout(EXECUTION_TIMEOUT):
                result = await self.session.call_tool(name, arguments)

                # Update metrics
                self.metrics.success_count += 1
                duration = (time.time() - start_time) * 1000
                # Simple moving average
                if self.metrics.avg_latency_ms == 0:
                    self.metrics.avg_latency_ms = duration
                else:
                    self.metrics.avg_latency_ms = (self.metrics.avg_latency_ms * 0.9) + (duration * 0.1)

                return result

        except (RuntimeError, asyncio.TimeoutError, BrokenPipeError, ConnectionResetError) as e:
            # 4. Error recovery logic
            err_msg = str(e)
            print(f"⚠️ [Swarm] Error in {self.name}: {err_msg}. Retries left: {retries}", file=sys.stderr)

            # Force disconnect, clean up state
            await self.close()

            if retries > 0:
                print(f"🔄 [Swarm] Attempting Auto-Restart for {self.name}...", file=sys.stderr)
                self.metrics.restarts += 1
                await asyncio.sleep(0.5)  # Brief cooldown

                # Recursive retry
                if await self.connect():
                    return await self.call_tool(name, arguments, retries - 1)

            # Retry exhausted, trigger circuit breaker
            self._trip_circuit_breaker(err_msg)
            raise

    async def list_tools(self) -> List[Tool]:
        """Safe listing with lazy connect."""
        if not self.is_connected:
            if not await self.connect():
                return []
        try:
            result = await self.session.list_tools()
            return result.tools
        except Exception:
            await self.close()
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Active probe of worker health."""
        status = {
            "name": self.name,
            "connected": self.is_connected,
            "circuit": "OPEN" if time.time() < self._circuit_open_until else "CLOSED",
            "metrics": self.metrics.__dict__
        }

        # Only attempt ping when connected
        if self.is_connected:
            try:
                # Try to call ping tool (added to coder_service.py)
                await self.call_tool("ping", {}, retries=0)
                status["healthy"] = True
            except Exception as e:
                status["healthy"] = False
                status["ping_error"] = str(e)
        else:
            status["healthy"] = False

        return status

    async def close(self):
        """Clean shutdown."""
        self._connected = False
        try:
            await self.exit_stack.aclose()
        except Exception:
            pass

    def _record_failure(self, error: str):
        self.metrics.failure_count += 1
        self.metrics.last_failure_time = time.time()
        self.metrics.last_error = str(error)

    def _trip_circuit_breaker(self, reason: str):
        self._record_failure(reason)
        self._circuit_open_until = time.time() + CIRCUIT_BREAKER_COOLDOWN
        print(f"🔥 [Swarm] CIRCUIT OPEN for {self.name}. Cooldown {CIRCUIT_BREAKER_COOLDOWN}s", file=sys.stderr)

# Singleton manager (optional, for Orchestrator)
class SwarmManager:
    """Orchestrator's interface to the Hive."""
    def __init__(self):
        self.nodes: Dict[str, SwarmNode] = {}

    def register(self, name: str, script_path: str):
        self.nodes[name] = SwarmNode(name, script_path)

    async def get_node(self, name: str) -> Optional[SwarmNode]:
        node = self.nodes.get(name)
        if not node:
            return None
        if not node.is_connected:
            await node.connect()
        return node

    async def get_system_health(self) -> Dict[str, Any]:
        """Aggregate health report."""
        report = {}
        for name, node in self.nodes.items():
            report[name] = await node.health_check()
            report[name]["metrics"] = node.metrics.__dict__
        return report

    async def restart_node(self, name: str) -> bool:
        node = self.nodes.get(name)
        if not node:
            return False
        await node.close()
        return await node.connect()
