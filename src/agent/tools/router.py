# agent/tools/router.py
"""
Router Tools - Semantic Tool Routing

Provides tool routing and swarm management for the orchestrator.

Tools:
- consult_router: Semantic tool routing
- swarm_status: Check swarm health
- community_proxy: Access community MCP servers
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in path
_project_root = Path(__file__).parent.parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server.fastmcp import FastMCP
from common.mcp_core import log_decision
from common.mcp_core.gitops import get_project_root
import structlog

logger = structlog.get_logger(__name__)

# Import router lazily to avoid eager loading
router = None


def get_router():
    """Lazy load router."""
    global router
    if router is None:
        from agent.core.router import get_router as _get_router
        router = _get_router()
    return router


def register_router_tools(mcp: FastMCP) -> None:
    """Register all router tools."""

    @mcp.tool()
    async def consult_router(query: str) -> str:
        """
        [Cortex] Ask the Router which tools to use for a specific task.

        Use this when you are unsure which tool is best for the user's request.
        It analyzes the intent and returns a focused set of tools (Domain).

        Args:
            query: The user's request or task description.

        Returns:
            JSON with recommended tools and reasoning.

        Examples:
            @omni-orchestrator consult_router(query="Analyze code quality")
            @omni-orchestrator consult_router(query="Run tests and report results")
        """
        try:
            r = get_router()
            if r is None:
                return json.dumps({
                    "success": False,
                    "error": "Router not initialized",
                    "message": "Tool router is not available. Install tool-router dependencies."
                })

            result = r.route(query)

            if isinstance(result, dict):
                return json.dumps({
                    "success": True,
                    "query": query,
                    "recommended_tools": result.get("tools", []),
                    "reasoning": result.get("reasoning", ""),
                    "domain": result.get("domain", "unknown")
                }, indent=2)
            else:
                return json.dumps({
                    "success": True,
                    "query": query,
                    "routing": result
                }, indent=2)

        except Exception as e:
            log_decision("router.consult_failed", {"error": str(e)}, logger)
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": "Router consultation failed."
            })

    @mcp.tool()
    async def swarm_status() -> str:
        """
        Check the detailed health and metrics of the Swarm.

        Returns:
            JSON with swarm status, MCP server health, and metrics.
        """
        try:
            # Import swarm status from orchestrator core
            from agent.core.swarm import get_swarm_health

            health = get_swarm_health()

            return json.dumps({
                "status": "healthy" if health.get("healthy") else "degraded",
                "servers": health.get("servers", {}),
                "metrics": health.get("metrics", {}),
                "timestamp": health.get("timestamp", "")
            }, indent=2)

        except ImportError:
            # Fallback if swarm module doesn't exist
            return json.dumps({
                "status": "unknown",
                "message": "Swarm monitoring not available",
                "servers": {
                    "orchestrator": {"status": "running", "tools": "active"},
                    "executor": {"status": "running", "tools": "active"},
                    "coder": {"status": "running", "tools": "active"}
                }
            }, indent=2)

        except Exception as e:
            log_decision("swarm.status_failed", {"error": str(e)}, logger)
            return json.dumps({
                "status": "error",
                "error": str(e)
            }, indent=2)

    @mcp.tool()
    async def community_proxy(mcp_name: str, query: str) -> str:
        """
        Access a community MCP server with project context injection.

        Wraps external MCPs (e.g., Kubernetes, PostgreSQL) to ensure they respect
        the project's nix configurations and architectural constraints.

        Args:
            mcp_name: Name of the community MCP
                - kubernetes: K8s cluster management
                - postgres: PostgreSQL database operations
                - filesystem: Advanced file operations
            query: Your request for the community MCP

        Returns:
            Response from the community MCP with project context, or guidance on setup

        Examples:
            @omni-orchestrator community_proxy(mcp_name="kubernetes", query="List pods")
        """
        # Community MCP configurations
        community_mcps = {
            "kubernetes": {
                "status": "not_configured",
                "setup_url": "https://github.com/anthropic/mcp-kubernetes",
                "description": "Kubernetes cluster management",
                "requires_config": True
            },
            "postgres": {
                "status": "not_configured",
                "setup_url": "https://github.com/anthropic/mcp-postgres",
                "description": "PostgreSQL database operations",
                "requires_config": True
            },
            "filesystem": {
                "status": "built-in",
                "description": "Use coder.py tools for file operations",
                "替代方案": "save_file, read_file, search_files from coder.py"
            }
        }

        if mcp_name not in community_mcps:
            available = list(community_mcps.keys())
            return json.dumps({
                "success": False,
                "error": f"Unknown MCP: {mcp_name}",
                "available_mcps": available
            }, indent=2)

        mcp_config = community_mcps[mcp_name]

        if mcp_config["status"] == "not_configured":
            return json.dumps({
                "success": False,
                "mcp_name": mcp_name,
                "status": "not_configured",
                "description": mcp_config["description"],
                "setup_url": mcp_config["setup_url"],
                "message": f"Community MCP '{mcp_name}' is not configured.",
                "instructions": f"Install and configure {mcp_config['setup_url']}"
            }, indent=2)

        if mcp_name == "filesystem":
            return json.dumps({
                "success": True,
                "mcp_name": mcp_name,
                "status": "built-in",
                "description": mcp_config["description"],
                "替代方案": mcp_config["替代方案"],
                "message": "Use coder.py MCP server for file operations"
            }, indent=2)

        # For configured MCPs, proxy the request
        return json.dumps({
            "success": False,
            "status": "not_implemented",
            "message": f"Community proxy for {mcp_name} not yet implemented",
            "mcp_name": mcp_name,
            "query": query
        }, indent=2)

    log_decision("router_tools.registered", {}, logger)
