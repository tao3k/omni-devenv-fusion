# mcp-server/executor.py
"""
Executor MCP Server - The "Hands"

Role: Atomic execution engine. Executes specific tasks without planning logic.
Philosophy: Dual-MCP Architecture - Separation of "Brain" (Orchestrator) and "Hands" (Executor).

Responsibilities:
- File operations (writing, reading)
- Git operations (commit, status, log, diff)
- Testing (smart test runner)
- Documentation execution
- Code search (ripgrep, ast-grep)

This module is designed to be imported by an MCP client (e.g., Claude Desktop)
or run as a standalone server.
"""
import sys
from pathlib import Path

# Ensure mcp-server is in path for imports
_mcp_server_path = Path(__file__).parent.resolve()
if str(_mcp_server_path) not in sys.path:
    sys.path.insert(0, str(_mcp_server_path))

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
_register_tools("Writer", __import__('writer', fromlist=['register_writer_tools']).register_writer_tools)

# GitOps tools (Version control)
_register_tools("GitOps", __import__('git_ops', fromlist=['register_git_ops_tools']).register_git_ops_tools)

# Tester tools (Smart test runner)
_register_tools("Tester", __import__('tester', fromlist=['register_tester_tools']).register_tester_tools)

# Docs tools (Documentation execution)
_register_tools("Docs", __import__('docs', fromlist=['register_docs_tools']).register_docs_tools)

# Advanced Search tools (Code search)
_register_tools("AdvancedSearch", __import__('advanced_search', fromlist=['register_advanced_search_tools']).register_advanced_search_tools)


# =============================================================================
# Executor Self-Description
# =============================================================================

@mcp.tool()
async def executor_status() -> str:
    """Check Executor server status and list available tools."""
    return f"""🛠️ Omni Executor Status

Role: The "Hands" - Atomic Execution Engine
Architecture: Dual-MCP (Orchestrator + Executor)

Available Categories:
- Writer: Writing style enforcement
- GitOps: Version control operations
- Tester: Smart test runner
- Docs: Documentation execution
- Search: Code search (ripgrep, ast-grep)

Note: This server handles EXECUTION only.
      Planning and routing are handled by the Orchestrator.
"""


if __name__ == "__main__":
    print("=" * 60, file=sys.stderr)
    print("🛠️  Executor MCP Server Starting...", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Role: The Hands - Atomic execution without planning", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    mcp.run()
