# mcp-server/services/coder_service.py
"""
Coder Worker v2
Standardized MCP Worker for File Ops & Search.
"""
import sys
import os

# 1. 路径引导 (Bootstrapping Path)
# 虽然 Swarm v2 已经注入了 PYTHONPATH，但为了可以手动测试 (uv run ...)，保留此逻辑
current_dir = os.path.dirname(os.path.abspath(__file__)) # services/
server_root = os.path.dirname(current_dir) # mcp-server/
if server_root not in sys.path:
    sys.path.insert(0, server_root)

from mcp.server.fastmcp import FastMCP

# 初始化
mcp = FastMCP("omni-coder-worker")

# [CRITICAL] 启动时的日志必须去 stderr
print(f"[Worker] Coder Service starting (PID: {os.getpid()})...", file=sys.stderr)

# 导入业务逻辑
try:
    from coder import (
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

# 注册工具
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
