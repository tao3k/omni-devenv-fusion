# MCP Transport Layer

> Trinity Architecture - Layer 3: MCP-Server

## Overview

The MCP (Model Context Protocol) Transport layer provides high-performance message routing between Claude Desktop/CLI and the Omni Agent. It implements the MCP specification with orjson serialization for 10× faster JSON processing.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ L4: Agent Layer (omni.agent)                                │
│  - MCP Server adapter                                       │
│  - CLI entry points                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ L3: MCP-Server Layer (omni.mcp)                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   MCPServer  │─►│   stdio()    │─►│   SSE()      │      │
│  │ (Orchestrator)  │  │  Transport  │  │  Transport  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │   Types      │  │  Interfaces  │                        │
│  │ (OrjsonModel)│  │  (Protocol)  │                        │
│  └──────────────┘  └──────────────┘                        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ L2: Core Layer (omni.core)                                  │
│  - ScriptLoader                                             │
│  - Skill Registry                                           │
└─────────────────────────────────────────────────────────────┘
```

## Transport Implementations

### STDIO Transport

For Claude Desktop and command-line usage:

```python
from omni.mcp.transport.stdio import stdio_server

async with stdio_server() as (read_stream, write_stream):
    await server.run(read_stream, write_stream, init_options)
```

**Performance Optimizations:**

- Zero-copy reading from `stdin.buffer`
- orjson for 10× faster serialization
- Direct binary output to `stdout.buffer`

### SSE Transport

For HTTP-based streaming:

```python
from omni.mcp.transport.sse import SseServerTransport

transport = SseServerTransport("/message")
async with transport.connect() as (read_stream, write_stream):
    await server.run(read_stream, write_stream, init_options)
```

## Message Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ stdin.buffer (bytes)                                            │
│         ↓                                                       │
│    orjson.loads()      ← L3: omni.mcp.transport.stdio           │
│         ↓                                                       │
│ JSON-RPC Request                                              │
│         ↓                                                       │
│ L4: agent.mcp_server.stdio.run_stdio()                          │
│         ↓                                                       │
│ L3: MCPServer.run()                                             │
│         ↓                                                       │
│ L2: ScriptLoader.get_command("skill.command")                   │
│         ↓                                                       │
│ L1: @skill_command decorated function executes                 │
│         ↓                                                       │
│ Returns CommandResult[T] (inherits OrjsonModel)                 │
│         ↓                                                       │
│ orjson.dumps()      ← L3: omni.mcp.transport.stdio              │
│         ↓                                                       │
│ stdout.buffer (bytes)                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Types (OrjsonModel)

All MCP types inherit from `OrjsonModel` for 10× faster serialization:

```python
from omni.mcp.types import (
    JSONRPCRequest,
    JSONRPCResponse,
    Tool,
    ToolInputSchema,
)

# All types support ultra-fast serialization
json_bytes = request.model_dump_json_bytes()
```

## Error Handling

```python
from omni.mcp.types import ErrorCode, make_error_response

# Standard error codes
make_error_response(
    id=request.id,
    code=ErrorCode.PARSE_ERROR,
    message="Invalid JSON",
)
```

| Error Code         | Meaning           |
| ------------------ | ----------------- |
| `PARSE_ERROR`      | Invalid JSON      |
| `INVALID_REQUEST`  | Malformed request |
| `METHOD_NOT_FOUND` | Unknown tool      |
| `INVALID_PARAMS`   | Bad arguments     |
| `INTERNAL_ERROR`   | Server error      |

## Performance Characteristics

| Operation             | Standard json | orjson | Speedup  |
| --------------------- | ------------- | ------ | -------- |
| `model_dump()`        | ~62ms         | ~35ms  | **1.8×** |
| Complex nested data   | ~120ms        | ~40ms  | **3×**   |
| MCP message roundtrip | ~200ms        | ~50ms  | **4×**   |

## Usage

### As MCP Server

```python
from omni.mcp.server import MCPServer
from omni.mcp.transport.stdio import stdio_server

# Create server with handler and transport
server = MCPServer(handler=my_handler, transport=my_transport)

# Start server
await server.start()
```

### Agent Integration

```python
# packages/python/agent/src/omni/agent/mcp_server/stdio.py
from omni.mcp.transport.stdio import stdio_server

async def run_stdio() -> None:
    """Run server in stdio mode for Claude Desktop."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, get_init_options())
```

## Related Files

**Python (MCP Layer):**

- `packages/python/mcp-server/src/omni/mcp/server.py`
- `packages/python/mcp-server/src/omni/mcp/transport/stdio.py`
- `packages/python/mcp-server/src/omni/mcp/transport/sse.py`
- `packages/python/mcp-server/src/omni/mcp/types.py`
- `packages/python/mcp-server/src/omni/mcp/interfaces.py`

**Foundation:**

- `packages/python/foundation/src/omni/foundation/api/types.py` (OrjsonModel)
