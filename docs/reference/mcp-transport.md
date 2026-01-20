# MCP Transport Interface

Omni Agent supports two transport mechanisms for MCP (Model Context Protocol) connections: **STDIO** for Claude Desktop and **SSE** for Claude Code CLI. This document describes the architecture, endpoints, and usage patterns.

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Omni MCP Server                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────────────────────┐│
│  │   STDIO Mode    │    │         SSE Mode               ││
│  │  (Claude Desktop) │    │    (Claude Code CLI)          ││
│  └────────┬────────┘    └──────────────┬──────────────────┘│
│           │                            │                    │
│  stdin/stdout                   http://host:port           │
│  (blocking)                     /sse + /messages           │
└─────────────────────────────────────────────────────────────┘
```

## STDIO Transport (Claude Desktop)

### Usage

```bash
# Start in STDIO mode (default for Claude Desktop)
uv run omni mcp --transport stdio

# With verbose logging
uv run omni mcp --transport stdio --log-level DEBUG
```

### Architecture

```
┌─────────────────┐
│  Claude Desktop │──stdin──► omni-mcp-server
└─────────────────┘                │
                    stdout ◄──────┘

The server runs directly as a single process:
- Direct stdin/stdout communication (MCP JSON-RPC protocol)
- Signal handling for graceful shutdown
- Background thread for skill file watcher (hot-reload)
- Stderr is isolated for logging (does not interfere with MCP protocol)
```

### Key Behaviors

| Behavior        | Description                                    |
| --------------- | ---------------------------------------------- |
| Auto-reconnect  | Server waits for client connection after EOF   |
| Signal handling | Ctrl+C gracefully shuts down                   |
| Hot-reload      | Background watcher monitors skills/ directory  |
| Clean stderr    | Logging goes to stderr, MCP protocol to stdout |

### Code Structure

```python
# packages/python/agent/src/agent/mcp_server/stdio.py

async def run_stdio() -> None:
    """Run server in stdio mode for Claude Desktop."""
    _setup_signal_handler()  # Signal handlers
    server = get_server()

    async with server_lifespan(enable_watcher=True):  # Lifespan + watcher
        while True:
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, get_init_options())
```

## SSE Transport (Claude Code CLI)

### Usage

```bash
# Start in SSE mode (default)
uv run omni mcp

# Custom host and port
uv run omni mcp --host 0.0.0.0 --port 8080

# With debug logging
uv run omni mcp --log-level DEBUG
```

### Endpoints

| Endpoint    | Method | Description                              |
| ----------- | ------ | ---------------------------------------- |
| `/sse`      | GET    | SSE stream for server-to-client messages |
| `/messages` | POST   | Client-to-server message endpoint        |
| `/health`   | GET    | Health check (returns "OK")              |
| `/ready`    | GET    | Readiness check with loaded skills count |

### Architecture

```
┌─────────────────┐    POST /messages    ┌─────────────────┐
│  Claude Code    │ ──────────────────►  │  Omni MCP       │
│     CLI         │                      │    SSE Server   │
└─────────────────┘                      └────────┬────────┘
                                                  │
                          GET /sse ◄─────────────┘
                          (Server-Sent Events)
```

### Performance Features

- **uvloop**: High-performance event loop (auto-installed if available)
- **orjson**: Fast JSON serialization
- **Async**: Non-blocking request handling

## Lifespan Management

Both transports share the same lifespan pattern:

```python
async with server_lifespan():
    # 1. Preload skills from settings.yaml
    # 2. Register hot-reload observers
    # 3. Start file watcher for skills directory
    # 4. Signal "Server ready"

    await server.run(...)  # Transport-specific run loop

    # On shutdown:
    # 1. Stop file watcher
    # 2. Cleanup resources
```

## Configuration

### Via Command Line

```bash
# STDIO mode
omni mcp --transport stdio

# SSE mode
omni mcp --transport sse --host 127.0.0.1 --port 3000
```

### Via Python API

```python
from agent.mcp_server import run

# STDIO mode
await run(transport="stdio")

# SSE mode
await run(transport="sse", host="0.0.0.0", port=8080)
```

### Settings (settings.yaml)

```yaml
skills:
  preload:
    - git
    - memory
    - filesystem
  on_demand:
    - writer
    - knowledge
```

## Troubleshooting

### STDIO Connection Timeout

**Problem**: Server starts but Claude Desktop shows "Connection timeout after 30000ms"

**Solution**: Check the following:

1. **Stderr interference**: Ensure no output goes to stdout (MCP requires clean stdout)
2. **Working directory**: Configure `--directory` in MCP config to project root
3. **Environment**: Set `PRJ_ROOT` environment variable

Example Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "omniAgent": {
      "command": "/path/to/.local/bin/uv",
      "args": [
        "--directory",
        "/path/to/project",
        "run",
        "omni",
        "mcp",
        "--transport",
        "stdio"
      ],
      "env": { "PRJ_ROOT": "/path/to/project" }
    }
  }
}
```

### STDIO Exits Immediately

**Problem**: Server starts but exits immediately

**Solution**: The server expects a Claude Desktop connection. Run in background or use SSE for testing:

```bash
# Use SSE for testing
uv run omni mcp

# Or keep STDIO running
timeout 60 uv run omni mcp --transport stdio
```

### SSE Connection Refused

**Problem**: Cannot connect to SSE endpoint

**Solution**: Check if server is running and binding to correct interface:

```bash
# Check port
lsof -i :8765

# Verify server is listening
curl http://127.0.0.1:8765/health
```

### Skills Not Loading

**Problem**: No tools available after connection

**Solution**: Check preload configuration:

```bash
# Verify settings.yaml
cat settings.yaml | grep -A 10 "skills:"

# Check logs
uv run omni mcp --log-level DEBUG
```

## File Structure

```
packages/python/agent/src/agent/mcp_server/
├── __init__.py          # Main exports (run, run_stdio, run_sse)
├── server.py            # Server instance, handlers (list_tools, call_tool)
├── stdio.py             # STDIO transport implementation
├── sse.py               # SSE transport implementation (Starlette)
└── lifespan.py          # Lifecycle management
```

## See Also

- [MCP Best Practices](mcp-best-practices.md)
- [MCP Orchestrator](mcp-orchestrator.md)
- [Project Execution Standard](project-execution-standard.md)
