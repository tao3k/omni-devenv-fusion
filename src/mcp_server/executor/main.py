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
import sys
from pathlib import Path

# Ensure project root is in path for imports (DDD structure)
# This allows: from common.mcp_core import ... and mcp_server.executor.* imports
_project_root = Path(__file__).parent.parent.parent.resolve()  # src/mcp_server/executor/ -> src/
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from mcp.server.fastmcp import FastMCP

# Initialize Executor Server
mcp = FastMCP("omni-executor")

# =============================================================================
# Tool Registration - Import from separate modules
# =============================================================================

def _register_tools(module_name: str, register_func):
    """Helper to register tools with error handling."""
    try:
        register_func(mcp)
        print(f"✅ {module_name} tools registered", file=sys.stderr)
        return True
    except Exception as e:
        print(f"⚠️ {module_name} tools import failed: {e}", file=sys.stderr)
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
    print("=" * 60, file=sys.stderr)
    print("🛠️  Executor MCP Server Starting...", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Role: The Hands - Atomic execution without planning", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    mcp.run()
