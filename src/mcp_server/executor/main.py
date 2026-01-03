# src/mcp_server/executor/main.py
"""
Executor MCP Server - The "Hands"

Role: Atomic execution engine. Executes specific tasks without planning logic.
Philosophy: Tri-MCP Architecture - Separation of "Brain" (Orchestrator), "Hands" (Executor), and "Pen" (Coder).

Responsibilities:
- Git operations (commit, status, log, diff)
- Testing (smart test runner)
- Documentation execution
- Code search (ripgrep, ast-grep)

This module is designed to be imported by an MCP client (e.g., Claude Desktop)
or run as a standalone server.
"""
from mcp.server.fastmcp import FastMCP

# Rich utilities for beautiful terminal output
from common.mcp_core.rich_utils import banner, section, tool_registered, tool_failed

# Initialize Executor Server
mcp = FastMCP("omni-executor")

# =============================================================================
# Tool Registration - Import from separate modules
# =============================================================================

def _register_tools(module_name: str, register_func):
    """Helper to register tools with error handling."""
    try:
        register_func(mcp)
        tool_registered(module_name, 0)
        return True
    except Exception as e:
        tool_failed(module_name, str(e))
        return False

# Writer tools (Writing style enforcement)
_register_tools("Writer", __import__('mcp_server.executor.writer', fromlist=['register_writer_tools']).register_writer_tools)

# GitOps tools (Version control)
_register_tools("GitOps", __import__('mcp_server.executor.git_ops', fromlist=['register_git_ops_tools']).register_git_ops_tools)

# Tester tools (Smart test runner)
_register_tools("Tester", __import__('mcp_server.executor.tester', fromlist=['register_tester_tools']).register_tester_tools)

# Docs tools (Documentation execution)
_register_tools("Docs", __import__('mcp_server.executor.docs', fromlist=['register_docs_tools']).register_docs_tools)


# =============================================================================
# Executor Self-Description
# =============================================================================

@mcp.tool()
async def executor_status() -> str:
    """Check Executor server status and list available tools."""
    return f"""🛠️ Omni Executor Status

Role: The "Hands" - Atomic Execution Engine
Architecture: Tri-MCP (Orchestrator + Executor + Coder)

Available Categories:
- Writer: Writing style enforcement
- GitOps: Version control operations
- Tester: Smart test runner
- Docs: Documentation execution

Note: This server handles EXECUTION only.
      Planning and routing are handled by the Orchestrator.
      File operations are handled by the Coder.
"""


if __name__ == "__main__":
    # Print Rich-styled startup banner
    from rich.console import Console
    console = Console(stderr=True)
    console.print(banner(
        "Executor MCP Server",
        "The Hands - Atomic execution without planning",
        "🛠️"
    ))
    section("Initializing Tools...")
    mcp.run()
