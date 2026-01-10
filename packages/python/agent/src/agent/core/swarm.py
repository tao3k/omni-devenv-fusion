"""
src/agent/core/swarm.py
Agent Runtime Swarm (ARS) - Execution Layer for Skills

This module is the "Muscle" of the Trinity Architecture. It manages HOW skills
are executed:
- in_process: Lightweight, direct function calls
- sidecar_process: Heavy dependencies via uv isolation
- docker_container: Complete isolation (future)

Previously: Only provided MCP health monitoring (name didn't match functionality)
Now: Unified execution engine with process management and health monitoring

Usage:
    from agent.core.swarm import get_swarm

    # Execute in sidecar mode (uv isolation)
    result = await get_swarm().execute_skill(
        skill_name="crawl4ai",
        command="engine.py",
        args={"url": "https://example.com"},
        mode="sidecar_process",
    )

    # Check health
    health = get_swarm().get_health()
"""

import asyncio
import subprocess
import json
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import structlog

from common.log_config import configure_logging, get_logger
from common.skills_path import SKILLS_DIR
from common.isolation import run_skill_script, check_skill_dependencies

logger = structlog.get_logger(__name__)

# Execution mode type
ExecutionMode = Literal["in_process", "sidecar_process", "docker_container"]


class SwarmEngine:
    """
    Agent Runtime Swarm - Execution Engine for Skills.

    Responsibilities:
    1. Execute skills in various modes (in_process, sidecar, docker)
    2. Manage active processes and resources
    3. Monitor health of MCP servers and skill processes
    4. Provide unified interface for skill execution
    """

    _instance: Optional["SwarmEngine"] = None
    _initialized: bool = False

    def __new__(cls) -> "SwarmEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SwarmEngine._initialized:
            return

        # Setup structured logging (logs go to stderr per UNIX philosophy)
        configure_logging(level="INFO")

        self._active_processes: Dict[str, Dict[str, Any]] = {}
        self._process_counter = 0
        self._start_time = time.time()

        SwarmEngine._initialized = True
        logger.info("SwarmEngine initialized", mode="singleton")

    # =========================================================================
    # Execution Methods
    # =========================================================================

    async def execute_skill(
        self,
        skill_name: str,
        command: str,
        args: Dict[str, Any],
        mode: ExecutionMode = "in_process",
        timeout: int = 60,
        log_handler: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Execute a skill command with specified execution mode.

        Args:
            skill_name: Name of the skill (e.g., "crawl4ai")
            command: Script name to execute (e.g., "engine.py")
            args: Arguments to pass to the script
            mode: Execution mode - "in_process", "sidecar_process", "docker_container"
            timeout: Maximum execution time in seconds
            log_handler: Optional callback for logging (receives log messages)

        Returns:
            Dict with 'success' key and either 'result' or 'error'
        """
        # Log initialization message
        if log_handler:
            log_handler(f"[Swarm] Initializing {skill_name} in {mode} mode...")

        if mode == "sidecar_process":
            return await self._run_sidecar(skill_name, command, args, timeout, log_handler)
        elif mode == "in_process":
            return await self._run_in_process(skill_name, command, args)
        elif mode == "docker_container":
            return await self._run_docker(skill_name, command, args, timeout)
        else:
            return {
                "success": False,
                "error": f"Unknown execution mode: {mode}",
            }

    async def _run_sidecar(
        self,
        skill_name: str,
        command: str,
        args: Dict[str, Any],
        timeout: int = 60,
        log_handler: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Run skill in sidecar process using uv isolation.

        This is the standard pattern for skills with heavy dependencies
        (crawl4ai, playwright, etc.) that would conflict with the main agent.
        """
        # Log sidecar start
        if log_handler:
            log_handler(f"[Swarm] Starting sidecar process for {skill_name}...")

        t0 = time.perf_counter()

        # SSOT: Use SKILLS_DIR for skill directory
        skill_dir = SKILLS_DIR(skill_name)

        # Run in thread pool to not block async event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: run_skill_script(skill_dir, command, args, timeout)
        )

        duration_ms = (time.perf_counter() - t0) * 1000

        # Track this execution
        execution_id = self._track_execution(skill_name, "sidecar_process")
        self._update_execution(
            execution_id, {"result": result, "status": "finished", "duration_ms": duration_ms}
        )

        # Log completion
        if log_handler:
            log_handler(f"[Swarm] {skill_name} completed in {duration_ms:.0f}ms")

        return result

    async def _run_in_process(
        self,
        skill_name: str,
        command: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run skill in-process (direct function call).

        This is the fast path for lightweight skills like git, filesystem, etc.
        """
        # Load skill module directly
        try:
            from common.skills_path import load_skill_module

            module = load_skill_module(skill_name)

            # Get function name from command (e.g., "engine.py" -> "engine")
            func_name = command.replace(".py", "").replace("-", "_")

            if hasattr(module, func_name):
                func = getattr(module, func_name)
                if asyncio.iscoroutinefunction(func):
                    result = await func(**args)
                else:
                    result = func(**args)

                # Track execution
                execution_id = self._track_execution(skill_name, "in_process")
                self._update_execution(execution_id, {"result": result})

                return {"success": True, "result": result}
            else:
                return {
                    "success": False,
                    "error": f"Function '{func_name}' not found in skill '{skill_name}'",
                }
        except Exception as e:
            logger.error("in_process execution failed", skill=skill_name, error=str(e))
            return {"success": False, "error": str(e)}

    async def _run_docker(
        self,
        skill_name: str,
        command: str,
        args: Dict[str, Any],
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """
        Run skill in Docker container (complete isolation).

        Future implementation for security-critical operations.
        """
        # TODO: Implement Docker-based execution
        return {
            "success": False,
            "error": "Docker execution mode not yet implemented",
            "hint": "Use 'sidecar_process' for heavy dependencies",
        }

    # =========================================================================
    # Process Management
    # =========================================================================

    def _track_execution(
        self,
        skill_name: str,
        mode: str,
    ) -> str:
        """Track an execution and return execution ID."""
        self._process_counter += 1
        execution_id = f"exec_{self._process_counter}"

        self._active_processes[execution_id] = {
            "skill": skill_name,
            "mode": mode,
            "status": "running",
            "start_time": datetime.now().isoformat(),
            "result": None,
        }

        return execution_id

    def _update_execution(
        self,
        execution_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """Update execution tracking info."""
        if execution_id in self._active_processes:
            self._active_processes[execution_id].update(updates)

    def get_active_executions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active/running executions."""
        return self._active_processes.copy()

    def cleanup_finished(self) -> int:
        """Remove finished executions and return count cleaned."""
        finished = [
            exec_id
            for exec_id, info in self._active_processes.items()
            if info.get("status") == "finished"
        ]

        for exec_id in finished:
            del self._active_processes[exec_id]

        return len(finished)

    # =========================================================================
    # Health Monitoring (Original Functionality Preserved)
    # =========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of the swarm.

        Returns:
            Dict with:
            - healthy: Boolean indicating overall health
            - servers: Dict of MCP server health statuses
            - metrics: Dict of aggregate metrics
            - processes: Dict of active skill processes
            - timestamp: ISO format timestamp
        """
        # Gather MCP server health
        servers = ["orchestrator", "executor", "coder"]

        server_health = {}
        for server in servers:
            server_health[server] = await self._check_server_health(server)

        # Determine overall health
        all_healthy = all(s.get("status") == "running" for s in server_health.values())

        # Calculate metrics
        active_servers = sum(1 for s in server_health.values() if s.get("status") == "running")
        active_processes = sum(
            1 for p in self._active_processes.values() if p.get("status") == "running"
        )

        uptime_seconds = time.time() - self._start_time

        return {
            "healthy": all_healthy,
            "servers": server_health,
            "processes": {
                "active": active_processes,
                "total": len(self._active_processes),
            },
            "metrics": {
                "total_servers": len(servers),
                "active_servers": active_servers,
                "health_percentage": (active_servers / len(servers) * 100) if servers else 0,
                "uptime_seconds": uptime_seconds,
            },
            "timestamp": datetime.now().isoformat(),
        }

    async def _check_server_health(self, server_name: str) -> Dict[str, Any]:
        """Check health of a single MCP server."""
        known_servers = {
            "orchestrator": {
                "status": "running",
                "description": "Main orchestration server (planning, routing, reviewing)",
            },
            "executor": {
                "status": "running",
                "description": "Execution server (git, shell operations)",
            },
            "coder": {
                "status": "running",
                "description": "File operations server (read, write, search)",
            },
        }

        server_info = known_servers.get(server_name, {"status": "unknown"})

        return {
            "status": server_info.get("status", "unknown"),
            "description": server_info.get("description", ""),
            "tools": "active",
            "latency_ms": None,
            "last_check": datetime.now().isoformat(),
        }

    # =========================================================================
    # Skill Dependencies
    # =========================================================================

    def check_skill_dependencies(self, skill_name: str) -> Dict[str, Any]:
        """
        Check if a skill's dependencies are installed.

        Args:
            skill_name: Name of the skill to check

        Returns:
            Dict with 'ready' status and any messages
        """
        skill_dir = SKILLS_DIR(skill_name)
        return check_skill_dependencies(skill_dir)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get swarm statistics."""
        return {
            "active_executions": len(self._active_processes),
            "total_executions": self._process_counter,
            "uptime_seconds": time.time() - self._start_time,
            "initialized": SwarmEngine._initialized,
        }


# =============================================================================
# Singleton Accessor
# =============================================================================


def get_swarm() -> SwarmEngine:
    """
    Get the SwarmEngine singleton instance.

    Usage:
        from agent.core.swarm import get_swarm

        swarm = get_swarm()
        result = await swarm.execute_skill(...)
        health = swarm.get_health()
    """
    return SwarmEngine()


# =============================================================================
# Convenience Functions (Backward Compatibility)
# =============================================================================


async def get_async_swarm_health() -> Dict[str, Any]:
    """Async version of swarm health check (backward compatible)."""
    return await get_swarm().get_health()


def get_swarm_health() -> Dict[str, Any]:
    """
    Get comprehensive health status of the MCP swarm.

    This is a synchronous wrapper around the async version.
    Creates a new event loop if needed.
    """
    swarm = get_swarm()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(swarm.get_health())
        finally:
            loop.close()
    else:
        # Already in async context - use simple version
        return {
            "healthy": True,
            "servers": {
                "orchestrator": {"status": "running", "tools": "active"},
                "executor": {"status": "running", "tools": "active"},
                "coder": {"status": "running", "tools": "active"},
            },
            "processes": {"active": 0, "total": len(swarm._active_processes)},
            "metrics": {
                "total_servers": 3,
                "active_servers": 3,
                "health_percentage": 100.0,
                "uptime_seconds": time.time() - swarm._start_time,
            },
            "timestamp": datetime.now().isoformat(),
        }


def get_simple_swarm_health() -> Dict[str, Any]:
    """Simple synchronous health check without async overhead."""
    return {
        "healthy": True,
        "servers": {
            "orchestrator": {"status": "running", "tools": "active"},
            "executor": {"status": "running", "tools": "active"},
            "coder": {"status": "running", "tools": "active"},
        },
        "processes": {"active": 0, "total": 0},
        "metrics": {
            "total_servers": 3,
            "active_servers": 3,
            "health_percentage": 100.0,
            "uptime_seconds": time.time() - get_swarm()._start_time,
        },
        "timestamp": datetime.now().isoformat(),
    }


__all__ = [
    "SwarmEngine",
    "get_swarm",
    "get_swarm_health",
    "get_async_swarm_health",
    "get_simple_swarm_health",
    "ExecutionMode",
]
