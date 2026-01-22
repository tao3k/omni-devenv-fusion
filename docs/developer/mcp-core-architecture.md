# MCP Core Architecture

> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-21

This document details the implementation of the Model Context Protocol (MCP) within the Trinity Architecture.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Trinity Architecture                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Layer 3: Agent (Thin)                        │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │              omni.agent.server (AgentMCPHandler)             │   │   │
│  │   │  ┌─────────────────┐    ┌─────────────────┐                  │   │   │
│  │   │  │  AgentMCPHandler│    │   StdioTransport│                  │   │   │
│  │   │  │  (Thin Client)  │───►│   (orjson)      │                  │   │   │
│  │   │  └────────┬────────┘    └────────┬────────┘                  │   │   │
│  │   └───────────┼──────────────────────┼───────────────────────────┘   │   │
│  │               │                      │                               │   │
│  └───────────────┼──────────────────────┼───────────────────────────────┘   │
│                  │                      │                                   │
│  ┌───────────────┼──────────────────────┼───────────────────────────────┐   │
│  │               ▼                      ▼                               │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │                    Layer 2: Core (Fat)                       │   │   │
│  │   │   ┌─────────────────────────────────────────────────────┐   │   │   │
│  │   │   │              omni.core.kernel                         │   │   │   │
│  │   │   │   ┌─────────────┐  ┌─────────────┐  ┌───────────┐   │   │   │   │
│  │   │   │   │ SkillContext│  │DiscoverySvc │  │Sniffer    │   │   │   │   │
│  │   │   │   └─────────────┘  └─────────────┘  └───────────┘   │   │   │   │
│  │   │   └─────────────────────────────────────────────────────┘   │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                         │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. omni.mcp (The Framework)

**Location**: `packages/python/mcp-server/src/omni/mcp/`

A generic, reusable MCP implementation.

```
omni/mcp/
├── __init__.py              # Exports (MCPServer, StdioTransport, SSEServer)
├── server.py                # MCPServer orchestration
├── interfaces.py            # Protocol definitions
├── types.py                 # JSON-RPC types (OrjsonModel-based)
└── transport/
    ├── stdio.py             # StdioTransport (zero-copy orjson)
    └── sse.py               # SSEServer (HTTP-based)
```

### 2. StdioTransport (High-Performance)

Optimized stdin/stdout transport using orjson for 10-50x faster serialization.

**Performance Optimizations:**

| Optimization         | Description                                        |
| -------------------- | -------------------------------------------------- |
| Zero-copy Reading    | Direct bytes from `stdin.buffer` (no UTF-8 decode) |
| orjson Serialization | Rust-powered JSON processing                       |
| Binary Writing       | Direct to `stdout.buffer` (bypass TextIOWrapper)   |

**Usage:**

```python
from omni.mcp.transport.stdio import StdioTransport
from omni.mcp.server import MCPServer
from omni.agent.server import create_agent_handler

transport = StdioTransport()
handler = create_agent_handler()
server = MCPServer(handler, transport)

await server.start()
await transport.run_loop(server)
```

### 3. SSEServer (HTTP-Based)

Server-Sent Events transport for Claude Code CLI.

**Endpoints:**

| Method | Path       | Purpose                                  |
| ------ | ---------- | ---------------------------------------- |
| POST   | `/message` | Send JSON-RPC requests                   |
| GET    | `/sse`     | SSE stream for responses & notifications |
| GET    | `/health`  | Health check                             |
| GET    | `/ready`   | Readiness check                          |

### 4. AgentMCPHandler (The Adapter)

**Location**: `packages/python/agent/src/omni/agent/server.py`

**Responsibilities:**

- Implements `MCPRequestHandler` protocol
- Boots the Kernel on first `initialize` request
- Delegates `tools/list` and `tools/call` to Kernel's skill context

```python
class AgentMCPHandler(MCPRequestHandler):
    def __init__(self):
        self._initialized = False
        self._kernel = get_kernel()

    async def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Route requests to appropriate handlers."""
        if not self._initialized:
            await self.initialize()

        if request.method == "tools/list":
            return await self._handle_list_tools(request)
        elif request.method == "tools/call":
            return await self._handle_call_tool(request)
        # ... other methods
```

### 5. CLI Entry Point

**Location**: `packages/python/agent/src/omni/agent/cli/commands/mcp.py`

**Usage:**

```bash
# STDIO mode (for Claude Desktop)
uv run omni mcp --transport stdio

# SSE mode (default for Claude Code CLI)
uv run omni mcp

# SSE with custom port
uv run omni mcp --port 8080
```

---

## Data Flow

### Tool List Request

```
Claude Desktop/Code CLI
     │
     ▼ JSON-RPC: {"method": "tools/list", "id": 1}
     │
StdioTransport.readline() → orjson.loads()
     │
     ▼
MCPServer._route_message() → handler.handle_request()
     │
     ▼
AgentMCPHandler._handle_list_tools()
     │
     ├─► Kernel.skill_context.list_skills()
     │        │
     │        ▼
     │   UniversalScriptSkill.list_commands()
     │
     ▼ JSON-RPC Response: {"result": {"tools": [...]}}
     │
StdioTransport._write_response() → orjson.dumps()
     │
     ▼
stdout.buffer.write()
```

### Tool Call Request

```
Claude Desktop/Code CLI
     │
     ▼ JSON-RPC: {"method": "tools/call", "params": {"name": "git.status"}}
     │
     ▼
AgentMCPHandler._handle_call_tool()
     │
     ├─► Parse skill.command format: "git" + "status"
     │
     ├─► Kernel.skill_context.get_skill("git")
     │
     ├─► skill.execute("status", arguments={})
     │        │
     │        ▼
     │   Load scripts/commands.py
     │   Execute git_status()
     │
     ▼ JSON-RPC Response: {"result": {"content": [{"type": "text", "text": "..."}]}}
```

---

## Debugging

> **When MCP issues occur, check Claude Code's debug logs first:**
>
> ```bash
> cat ~/.claude/debug/latest/*.log
> ```

### Quick Debug Commands

```bash
# Validate tool schema compliance
uv run pytest packages/python/agent/tests/integration/test_mcp_stdio.py::TestMCPProtocolCompliance -v

# Test server startup
uv run omni mcp --transport stdio 2>&1 | head -50

# Check kernel initialization
uv run omni mcp 2>&1 | grep -E "(Kernel|Skills|Error)"
```

---

## Related Files

| File                                                         | Purpose            |
| ------------------------------------------------------------ | ------------------ |
| `packages/python/mcp-server/src/omni/mcp/server.py`          | Generic MCP server |
| `packages/python/mcp-server/src/omni/mcp/transport/stdio.py` | STDIO transport    |
| `packages/python/mcp-server/src/omni/mcp/transport/sse.py`   | SSE transport      |
| `packages/python/agent/src/omni/agent/server.py`             | Agent MCP handler  |
| `packages/python/agent/src/omni/agent/cli/commands/mcp.py`   | CLI entry point    |
| `packages/python/core/src/omni/core/kernel/engine.py`        | Kernel lifecycle   |

---

## Testing

```bash
# Run MCP protocol compliance tests
uv run pytest packages/python/agent/tests/integration/test_mcp_stdio.py::TestMCPProtocolCompliance -v

# Run all MCP tests
uv run pytest packages/python/agent/tests/integration/test_mcp_stdio.py -v
```
