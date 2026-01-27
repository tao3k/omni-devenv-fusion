# MCP Transport Interface

> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-26

Omni Agent supports two transport mechanisms for MCP (Model Context Protocol) connections: **STDIO** for Claude Desktop and **SSE** for Claude Code CLI.

## Quick Start

```bash
# Claude Desktop (STDIO)
uv run omni mcp --transport stdio

# Claude Code CLI (SSE - default)
uv run omni mcp
```

## Architecture

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

---

## STDIO Transport (Claude Desktop)

### Usage

```bash
uv run omni mcp --transport stdio
```

### Architecture

```
┌─────────────────┐
│  Claude Desktop │──stdin──► omni-agent-mcp-server
└─────────────────┘                │
                    stdout ◄──────┘
```

- Direct stdin/stdout communication using MCP SDK's `stdio_server()`
- Signal handling via `asyncio.add_signal_handler()` for graceful shutdown
- **Logging goes to stderr** (does not interfere with MCP protocol)

### Implementation

```python
from omni.agent.mcp_server.server import AgentMCPServer
from omni.mcp.transport.stdio import stdio_server

async def run_stdio():
    server = AgentMCPServer()
    await server.run_stdio(verbose=True)
```

Uses MCP SDK's context manager for proper stream handling:

```python
async with stdio_server() as (read_stream, write_stream):
    await server.run(read_stream, write_stream, init_options)
```

### Key Behaviors

| Behavior        | Description                                         |
| --------------- | --------------------------------------------------- |
| Signal handling | Ctrl+C gracefully shuts down via add_signal_handler |
| Clean stderr    | Logging to stderr, MCP protocol to stdout           |

---

## SSE Transport (Claude Code CLI)

### Usage

```bash
# Default (port 8080)
uv run omni mcp

# Custom port
uv run omni mcp --port 9000
```

### Endpoints

| Endpoint    | Method | Description                              |
| ----------- | ------ | ---------------------------------------- |
| `/sse`      | GET    | SSE stream for server-to-client messages |
| `/messages` | POST   | Client-to-server message endpoint        |
| `/health`   | GET    | Health check                             |

### Architecture

```
┌─────────────────┐    POST /messages    ┌─────────────────┐
│  Claude Code    │ ──────────────────►  │  Omni Agent     │
│     CLI         │                      │    MCP Server   │
└─────────────────┘                      └────────┬────────┘
                                                  │
                          GET /sse ◄─────────────┘
                          (Server-Sent Events)
```

---

## Code Structure

**Location**: `packages/python/agent/src/omni/agent/mcp_server/`

```
omni/agent/mcp_server/
├── __init__.py              # Exports
├── server.py                # AgentMCPServer (main server)
├── lifespan.py              # Lifespan context manager
├── sse.py                   # SSE transport
└── stdio.py                 # stdio_server context manager
```

### Signal Handling

In stdio mode, SIGINT is handled via `asyncio.add_signal_handler()`:

```python
async def main_async():
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        shutdown_event.set()

    loop.add_signal_handler(signal.SIGINT, signal_handler)
```

---

## Troubleshooting

> **Important**: When MCP issues occur, check Claude Code's debug logs first:
>
> ```
> cat ~/.claude/debug/latest/*.log
> ```

### Tools Not Loading

**Problem**: Claude Code shows no tools available after connection.

**Debugging Steps**:

1. **Check server logs**:

   ```bash
   uv run omni mcp 2>&1 | grep -E "(Kernel|Tools|Error)"
   ```

2. **Verify server starts correctly**:

   ```bash
   uv run omni mcp --transport stdio 2>&1
   ```

### STDIO Connection Timeout

**Problem**: Server starts but connection times out.

**Solutions**:

1. Check stderr interference (logging must go to stderr, not stdout)
2. Verify working directory in MCP config

### SIGINT Not Handled

**Problem**: Ctrl+C doesn't gracefully shutdown.

**Solution**: Ensure `add_signal_handler()` is used in `main_async()`:

```python
loop.add_signal_handler(signal.SIGINT, signal_handler)
```

---

## Related Documentation

- [MCP Best Practices](mcp-best-practices.md)
- [MCP Server Architecture](../architecture/mcp-server.md)
- [Kernel Architecture](../architecture/kernel.md)
