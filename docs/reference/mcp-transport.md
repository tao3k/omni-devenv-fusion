# MCP Transport Interface

> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-27

Omni Agent supports two transport mechanisms for MCP (Model Context Protocol) connections: **STDIO** for Claude Desktop and **SSE** for Claude Code CLI.

## Quick Start

```bash
# Claude Desktop (STDIO)
uv run omni mcp --transport stdio

# Claude Code CLI (SSE - default)
uv run omni mcp

# With verbose logging
uv run omni mcp --verbose
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

### Key Improvements (v2.0)

| Feature             | Description                                      |
| ------------------- | ------------------------------------------------ |
| **Async Startup**   | Kernel ready in ~2s, Cortex builds in background |
| **Smart Indexing**  | Skips unchanged skills (no Embedding API calls)  |
| **Unified Logging** | Foundation layer prevents stderr pollution       |

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
- **Logging goes to stderr** via Foundation layer (does not interfere with MCP protocol)

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
| Clean stdout    | MCP protocol to stdout, logging to stderr           |
| Fast startup    | Kernel ready in ~2s (Cortex in background)          |

---

## SSE Transport (Claude Code CLI)

### Usage

```bash
# Default (port 8080)
uv run omni mcp

# Custom port
uv run omni mcp --port 9000

# With verbose logging
uv run omni mcp --verbose
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
├── server.py                # AgentMCPServer (main server)
├── lifespan.py              # Lifespan context manager
├── sse.py                   # SSE transport
└── stdio.py                 # stdio_server context manager
```

### Logging (v2.0)

All modules use Foundation layer logging:

```python
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.agent.stdio")  # or "omni.agent.lifecycle"
```

**No more structlog in transport layer** - prevents stderr pollution.

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

## Performance (v2.0)

### Startup Time

| Scenario            | Before | After     |
| ------------------- | ------ | --------- |
| First connection    | ~200s  | **~2s**   |
| Restart (unchanged) | ~200s  | **~0.5s** |
| Restart (changed)   | ~200s  | ~2s       |

### Why So Fast?

1. **Async Cortex**: Kernel ready immediately, index builds in background
2. **Smart Indexing**: Hash-based detection skips unchanged skills
3. **Unified Logging**: No stderr pollution means cleaner stream handling

---

## Troubleshooting

> **Important**: When MCP issues occur, check Claude Code's debug logs first:
>
> ```
> cat ~/.claude/debug/latest/*.log
> ```

### Connection Timeout (30s)

**Problem**: MCP client times out during connection.

**Diagnosis**:

```bash
# Enable verbose mode
uv run omni mcp --verbose 2>&1 | head -100
```

**Solutions**:

1. **Check async Cortex is working**:

   ```bash
   uv run omni mcp 2>&1 | grep -E "(Ready|Background|Cortex)"
   # Should see "Kernel ready" within ~3 seconds
   ```

2. **Verify no stderr pollution**:

   ```bash
   uv run omni mcp --transport stdio 2>/dev/null
   # If this hangs, something is writing to stdout
   ```

3. **Check embedding service**:
   ```bash
   uv run omni mcp 2>&1 | grep -E "(Embedding|timeout|hash)"
   ```

### Tools Not Loading

**Problem**: Claude Code shows no tools available after connection.

**Debugging Steps**:

1. **Check server logs**:

   ```bash
   uv run omni mcp 2>&1 | grep -E "(Kernel|Tools|Ready|Skills)"
   ```

2. **Verify skills loaded**:

   ```bash
   uv run omni mcp 2>&1 | grep -E "commands|skills"
   ```

3. **Check Cortex status**:
   ```bash
   uv run omni mcp 2>&1 | grep -E "(Cortex|index|hash)"
   ```

### STDIO Connection Timeout

**Problem**: Server starts but connection times out.

**Solutions**:

1. **Verify logging goes to stderr**:

   ```python
   # Use Foundation layer
   from omni.foundation.config.logging import get_logger
   logger = get_logger("omni.agent.stdio")
   logger.info("message")  # Goes to stderr
   ```

2. **Check working directory** in MCP config

3. **Enable verbose for more info**:
   ```bash
   uv run omni mcp --transport stdio --verbose
   ```

### SIGINT Not Handled

**Problem**: Ctrl+C doesn't gracefully shutdown.

**Solution**: Ensure `add_signal_handler()` is used:

```python
loop.add_signal_handler(signal.SIGINT, signal_handler)
```

---

## Related Documentation

- [MCP Best Practices](mcp-best-practices.md)
- [MCP Server Architecture](../architecture/mcp-server.md)
- [Kernel Architecture](../architecture/kernel.md)
- [Smart Indexing (indexer.py)](../reference/indexer.md)
