# MCP-Server Architecture - Omni-Dev-Fusion

> Model Context Protocol Server Implementation
> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-21

---

## Overview

The **MCP-Server** (L3 - Transport) provides the Model Context Protocol implementation:

- **JSON-RPC 2.0** message handling
- **Protocol interfaces** for request/response routing
- **Transport implementations** (stdio, SSE)
- **Pure orchestration** - no business logic

### MCP Protocol

```
┌─────────────────────────────────────────────────────────┐
│                      MCP Client                          │
│              (Claude Code, Claude Desktop)              │
└─────────────────────┬───────────────────────────────────┘
                      │ JSON-RPC 2.0
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   omni-mcp-server                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  Transport  │──│   Server    │──│   Handler       │  │
│  │ (stdio/SSE) │  │ (Orchestration)│ (Agent/Kernel) │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## Architecture

**Location**: `packages/python/mcp-server/src/omni/mcp/`

```
omni/mcp/
├── __init__.py              # Exports
├── types.py                 # JSON-RPC 2.0 types (OrjsonModel-based)
├── interfaces.py            # Protocol interfaces
├── server.py                # MCPServer orchestration
└── transport/
    ├── __init__.py
    ├── stdio.py             # StdioTransport (zero-copy orjson)
    └── sse.py               # SSEServer (HTTP/SSE)
```

### Layer Responsibilities

| Layer         | Responsibility             | Location                            |
| ------------- | -------------------------- | ----------------------------------- |
| **Transport** | Network I/O (stdio, SSE)   | `omni.mcp.transport.stdio/sse`      |
| **Server**    | Message routing, lifecycle | `omni.mcp.server.MCPServer`         |
| **Handler**   | Business logic (Kernel)    | `omni.agent.server.AgentMCPHandler` |

---

## MCPServer

**Location**: `packages/python/mcp-server/src/omni/mcp/server.py`

Pure orchestration - routes messages between transport and handler.

```python
from omni.mcp.server import MCPServer
from omni.mcp.transport.stdio import StdioTransport

# Create server
server = MCPServer(handler=my_handler, transport=transport)

# Start server
await server.start()

# Run until stopped
await server.run_forever()

# Stop server
await server.stop()
```

### Properties

| Property     | Type                | Description          |
| ------------ | ------------------- | -------------------- |
| `is_running` | `bool`              | Server running state |
| `handler`    | `MCPRequestHandler` | Request handler      |
| `transport`  | `MCPTransport`      | Transport layer      |

---

## AgentMCPHandler

**Location**: `packages/python/agent/src/omni/agent/server.py`

Thin MCP adapter that delegates to Core Kernel.

```python
from omni.agent.server import AgentMCPHandler, create_agent_handler

handler = create_agent_handler()
await handler.initialize()  # Boots the kernel
```

### Request Flow

```
tools/list → _handle_list_tools() → skill_context.list_commands()
tools/call → _handle_call_tool() → skill.execute()
```

---

## Types

**Location**: `packages/python/mcp-server/src/omni/mcp/types.py`

JSON-RPC 2.0 type definitions. **All types inherit from Foundation's `OrjsonModel`** for 10x faster serialization.

### Core Types

```python
from omni.mcp.types import JSONRPCRequest, JSONRPCResponse

# Request (inherits OrjsonModel)
request = JSONRPCRequest(method="tools/list", params={}, id=1)

# Response
response = JSONRPCResponse(result={"tools": []}, id=1)
```

### Helper Functions

```python
from omni.mcp.types import (
    make_success_response,
    make_error_response,
)

# Create success response
response = make_success_response(id=1, result={"tools": []})

# Create error response
response = make_error_response(
    id=1,
    code=ErrorCode.INVALID_PARAMS,
    message="Invalid parameter"
)
```

---

## Transport

### StdioTransport

For command-line integration with **zero-copy** orjson serialization:

```python
from omni.mcp.transport.stdio import StdioTransport

transport = StdioTransport()
await transport.start()
```

**Features**:

- Reads raw bytes from stdin.buffer (no UTF-8 decode overhead)
- Uses orjson.loads() directly on bytes
- Writes raw bytes to stdout.buffer (bypass TextIOWrapper)

### SSEServer

For HTTP-based integration with **orjson-powered** streaming:

```python
from omni.mcp.transport.sse import SSEServer

transport = SSEServer(host="127.0.0.1", port=8080)
await transport.start()
```

**Features**:

- orjson.dumps() for all SSE events
- Efficient notification queue per session
- Automatic ping every 25s to keep connection alive

---

## Debugging

> When MCP issues occur, check Claude Code's debug logs first:
>
> ```
> cat ~/.claude/debug/latest/*.log
> ```

### Common Issues

| Issue               | Cause                                 | Solution                              |
| ------------------- | ------------------------------------- | ------------------------------------- |
| Empty tools list    | `inputSchema.type` missing `"object"` | Run `TestMCPProtocolCompliance` test  |
| Connection timeout  | Stderr interfering with stdout        | Ensure logging goes to stderr         |
| Notification errors | Handling notifications as requests    | Use `handle_notification()` correctly |

---

## Related Documentation

- [MCP Transport Reference](../reference/mcp-transport.md)
- [MCP Best Practices](../reference/mcp-best-practices.md)
- [Kernel Architecture](kernel.md)
- [Router Architecture](router.md)
