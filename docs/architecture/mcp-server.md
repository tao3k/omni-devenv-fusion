# MCP-Server Architecture - Omni-Dev-Fusion

> Model Context Protocol Server Implementation
> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-26

---

## Overview

The **MCP-Server** (L3 - Transport) provides the Model Context Protocol implementation:

- **MCP SDK** integration for JSON-RPC 2.0 protocol handling
- **Transport implementations** (stdio, SSE)
- **Agent integration** via Kernel

### MCP Protocol

```
┌─────────────────────────────────────────────────────────┐
│                      MCP Client                          │
│              (Claude Code, Claude Desktop)              │
└─────────────────────┬───────────────────────────────────┘
                      │ JSON-RPC 2.0
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   omni-agent-mcp-server                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   stdio/    │──│  MCP SDK    │──│  AgentMCPHandler│  │
│  │    SSE      │  │   Server    │  │  (Kernel)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Architecture

**Location**: `packages/python/agent/src/omni/agent/mcp_server/`

```
omni/agent/mcp_server/
├── __init__.py              # Exports
├── server.py                # AgentMCPServer (main server)
├── lifespan.py              # Lifespan context manager
├── sse.py                   # SSE transport
└── stdio.py                 # stdio_server context manager
```

### Layer Responsibilities

| Layer         | Responsibility                | Location                          |
| ------------- | ----------------------------- | --------------------------------- |
| **Transport** | Network I/O (stdio, SSE)      | `omni.agent.mcp_server.stdio/sse` |
| **Server**    | MCP protocol, handlers        | `omni.agent.mcp_server.server`    |
| **Kernel**    | Tool execution, skill context | `omni.core.kernel`                |

---

## AgentMCPServer

**Location**: `packages/python/agent/src/omni/agent/mcp_server/server.py`

Main MCP server class using MCP SDK for protocol handling.

### Quick Start

```python
from omni.agent.mcp_server.server import AgentMCPServer

# Run in stdio mode (default)
server = AgentMCPServer()
await server.run_stdio(verbose=False)

# Run in SSE mode
await server.run_sse_server(port=8080, verbose=False)
```

### Core Handlers

| Handler            | MCP Method       | Description                     |
| ------------------ | ---------------- | ------------------------------- |
| `list_tools()`     | `tools/list`     | Returns tools via Rust Registry |
| `call_tool()`      | `tools/call`     | Executes tool via Kernel        |
| `list_resources()` | `resources/list` | Returns project context, memory |
| `read_resource()`  | `resources/read` | Reads resource data             |
| `list_prompts()`   | `prompts/list`   | Returns available prompts       |
| `get_prompt()`     | `prompts/get`    | Returns prompt content          |

---

## Transport

### STDIO Mode

Uses MCP SDK's `stdio_server()` context manager for proper stream handling:

```python
from omni.agent.mcp_server.server import AgentMCPServer

async def run_stdio_server():
    server = AgentMCPServer()
    await server.run_stdio(verbose=True)
```

**Key features**:

- Proper stdin/stdout stream handling via MCP SDK
- Graceful shutdown on SIGINT
- Kernel initialization and shutdown

### SSE Mode

HTTP-based transport for remote connections:

```python
async def run_sse_server(port=8080):
    server = AgentMCPServer()
    await server.run_sse_server(port=port)
```

---

## Signal Handling

In stdio mode, signal handling is managed via `asyncio.add_signal_handler()`:

```python
async def main_async():
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        shutdown_event.set()

    loop.add_signal_handler(signal.SIGINT, signal_handler)
```

---

## Resource URIs

| URI                      | Description                           |
| ------------------------ | ------------------------------------- |
| `omni://project/context` | Active frameworks/languages (Sniffer) |
| `omni://memory/latest`   | Agent short-term memory (Checkpoint)  |
| `omni://system/stats`    | Runtime statistics                    |

---

## Testing

### Stdio Server Tests

**Location**: `packages/python/agent/tests/integration/test_mcp_stdio.py`

```bash
uv run pytest packages/python/agent/tests/integration/test_mcp_stdio.py -v
```

### MCP Server Unit Tests

**Location**: `packages/python/mcp-server/tests/`

```bash
uv run pytest packages/python/mcp-server/tests/ -v
```

---

## Debugging

> When MCP issues occur, check Claude Code's debug logs first:
>
> ```
> cat ~/.claude/debug/latest/*.log
> ```

### Common Issues

| Issue              | Cause                          | Solution                      |
| ------------------ | ------------------------------ | ----------------------------- |
| Empty tools list   | Kernel not ready               | Check kernel initialization   |
| Connection timeout | Stderr interfering with stdout | Ensure logging goes to stderr |
| SIGINT not handled | Missing signal handler         | Use `add_signal_handler()`    |

---

## Related Documentation

- [MCP Transport Reference](../reference/mcp-transport.md)
- [MCP Best Practices](../reference/mcp-best-practices.md)
- [Kernel Architecture](kernel.md)
- [Router Architecture](router.md)
