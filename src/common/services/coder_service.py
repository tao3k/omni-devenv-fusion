# mcp-server/services/coder_service.py
"""
Coder Worker v2
Standardized MCP Worker for File Ops & Search.

This worker is spawned by the swarm and receives PYTHONPATH injection.
Standard imports work via uv workspace configuration.
"""
import sys
import os

from mcp.server.fastmcp import FastMCP

# Initialize
mcp = FastMCP("omni-coder-worker")

# [CRITICAL] Startup logs must go to stderr
print(f"[Worker] Coder Service starting (PID: {os.getpid()})...", file=sys.stderr)

# Import business logic
try:
    from mcp_server.coder.main import (
        read_file as _read,
        search_files as _search,
        save_file as _save,
        ast_search as _ast_search,
        ast_rewrite as _ast_rewrite
    )
except ImportError as e:
    sys.stderr.write(f"[Worker] Critical Import Error: {e}\n")
    sys.stderr.write(f"   PYTHONPATH: {os.environ.get('PYTHONPATH')}\n")
    sys.exit(1)

# Register tools
@mcp.tool()
async def read_file(path: str) -> str:
    return await _read(path)

@mcp.tool()
async def search_files(pattern: str, path: str = ".", use_regex: bool = False) -> str:
    return await _search(pattern, path, use_regex)

@mcp.tool()
async def save_file(path: str, content: str) -> str:
    return await _save(path, content)

@mcp.tool()
async def ast_search(pattern: str, lang: str = "py", path: str = ".") -> str:
    return await _ast_search(pattern, lang, path)

@mcp.tool()
async def ast_rewrite(pattern: str, replacement: str, lang: str = "py", path: str = ".") -> str:
    return await _ast_rewrite(pattern, replacement, lang, path)

@mcp.tool()
async def ping() -> str:
    """Health check."""
    return "pong"

if __name__ == "__main__":
    mcp.run()
