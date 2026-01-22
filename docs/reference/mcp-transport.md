# MCP Transport Interface

> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-21

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
│  Claude Desktop │──stdin──► omni-mcp-server
└─────────────────┘                │
                    stdout ◄──────┘
```

- Direct stdin/stdout communication (MCP JSON-RPC protocol)
- Signal handling for graceful shutdown
- Background watcher for hot-reload
- **Logging goes to stderr** (does not interfere with MCP protocol)

### Key Behaviors

| Behavior        | Description                                   |
| --------------- | --------------------------------------------- |
| Auto-reconnect  | Server waits for client connection after EOF  |
| Signal handling | Ctrl+C gracefully shuts down                  |
| Hot-reload      | Background watcher monitors skills/ directory |
| Clean stderr    | Logging to stderr, MCP protocol to stdout     |

---

## SSE Transport (Claude Code CLI)

### Usage

```bash
# Default (port 3000)
uv run omni mcp

# Custom host and port
uv run omni mcp --host 0.0.0.0 --port 8080
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

---

## Code Structure

**Location**: `packages/python/mcp-server/src/omni/mcp/`

```
omni/mcp/
├── __init__.py              # Exports (MCPServer, StdioTransport, SSEServer)
├── types.py                 # JSON-RPC 2.0 types (OrjsonModel-based)
├── interfaces.py            # Protocol interfaces
├── server.py                # MCPServer orchestration
└── transport/
    ├── __init__.py
    ├── stdio.py             # StdioTransport (zero-copy orjson)
    └── sse.py               # SSEServer (HTTP/SSE)
```

**Agent Handler**: `packages/python/agent/src/omni/agent/server.py`

```
AgentMCPHandler
    │
    ├── _kernel: Kernel      # Core Layer (skill context, routing)
    ├── _handle_initialize() # MCP handshake
    ├── _handle_list_tools() # List skills as MCP tools
    └── _handle_call_tool()  # Execute skill commands
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

1. **Check Claude Code debug logs**:

   ```bash
   cat ~/.claude/debug/latest/*.log | grep -i mcp
   ```

2. **Verify server starts correctly**:

   ```bash
   uv run omni mcp --transport stdio 2>&1 | head -50
   ```

3. **Validate tool schema**:
   ```bash
   uv run pytest packages/python/agent/tests/integration/test_mcp_stdio.py::TestMCPProtocolCompliance -v
   ```

### STDIO Connection Timeout

**Problem**: Server starts but Claude Desktop shows "Connection timeout".

**Solutions**:

1. Check stderr interference (logging must go to stderr, not stdout)
2. Verify working directory in MCP config
3. Check environment variables

### Skills Not Loading

**Problem**: Server starts but tools list is empty.

**Solutions**:

1. Run validation test:

   ```bash
   uv run pytest packages/python/agent/tests/integration/test_mcp_stdio.py::TestMCPProtocolCompliance -v
   ```

2. Check kernel initialization logs:
   ```bash
   uv run omni mcp 2>&1 | grep -E "(Kernel|Skills|Error)"
   ```

---

## Related Documentation

- [MCP Best Practices](mcp-best-practices.md)
- [MCP Server Architecture](../architecture/mcp-server.md)
- [Kernel Architecture](../architecture/kernel.md)
