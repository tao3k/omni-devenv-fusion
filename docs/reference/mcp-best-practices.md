# MCP Best Practices - Omni-Dev-Fusion

> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-21

This document describes best practices for the Omni MCP implementation using the custom `omni.mcp` transport layer.

---

## Architecture Overview

Omni uses a **custom MCP transport layer** (`omni.mcp`) instead of the MCP Python SDK:

```
┌─────────────────────────────────────────────────┐
│              Omni MCP Architecture              │
├─────────────────────────────────────────────────┤
│  Transport (omni.mcp.transport)                 │
│    ├── StdioTransport (Claude Desktop)          │
│    └── SSEServer (Claude Code CLI)              │
├─────────────────────────────────────────────────┤
│  Server (omni.mcp.server.MCPServer)             │
│    └── Pure orchestration, no business logic    │
├─────────────────────────────────────────────────┤
│  Handler (omni.agent.server.AgentMCPHandler)    │
│    └── Delegates to Kernel for all operations   │
└─────────────────────────────────────────────────┘
```

---

## 1. AgentMCPHandler Pattern

### Handler Structure

```python
from omni.agent.server import AgentMCPHandler
from omni.mcp.types import JSONRPCRequest, JSONRPCResponse

class AgentMCPHandler:
    def __init__(self):
        self._kernel = get_kernel()  # Core Layer
        self._initialized = False

    async def handle_request(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """Route JSON-RPC requests to appropriate handlers."""
        if not self._initialized:
            await self.initialize()

        method = request.method
        if method == "initialize":
            return await self._handle_initialize(request)
        elif method == "tools/list":
            return await self._handle_list_tools(request)
        elif method == "tools/call":
            return await self._handle_call_tool(request)
        # ... handle other methods
```

### Tool Listing

```python
async def _handle_list_tools(self, request: JSONRPCRequest) -> JSONRPCResponse:
    """List all skills as MCP tools."""
    context = self._kernel.skill_context
    tools = []

    for skill_name in context.list_skills():
        skill = context.get_skill(skill_name)
        for cmd_name in skill.list_commands():
            cmd = skill.get_command(cmd_name)
            description = getattr(cmd, "description", f"Run {skill_name}.{cmd_name}")
            raw_schema = getattr(cmd, "input_schema", {}) if cmd else {}
            input_schema = raw_schema.copy() if raw_schema else {}
            input_schema.setdefault("type", "object")  # MCP requirement!

            tools.append({
                "name": f"{skill_name}.{cmd_name}",
                "description": description,
                "inputSchema": input_schema,
            })

    return make_success_response(request.id, {"tools": tools})
```

---

## 2. MCP Protocol Compliance

### inputSchema Requirement

**Critical**: Every tool MUST have `inputSchema.type === "object"`:

```python
# Correct ✓
{"type": "object", "properties": {...}}

# Incorrect ✗ (will cause "expected 'object'" error)
{}  # or {"properties": {...}}
```

### Test Protocol Compliance

```bash
uv run pytest packages/python/agent/tests/integration/test_mcp_stdio.py::TestMCPProtocolCompliance -v
```

---

## 3. Async-First Design

### Why?

MCP Server runs on an async Event Loop. Calling `asyncio.run()` inside the loop causes `RuntimeError: This event loop is already running`.

### Best Practice

```python
# Correct: Native async/await
async def execute_command(self, skill_name: str, cmd_name: str, args: dict) -> str:
    skill = self._kernel.skill_context.get_skill(skill_name)
    return await skill.execute(cmd_name, **args)

# Wrong: asyncio.run() in loop (causes RuntimeError)
async def bad_example(self, ...):
    result = asyncio.run(some_async_func())
```

---

## 4. Error Handling

### Best Practice

```python
async def _handle_call_tool(self, request: JSONRPCRequest) -> JSONRPCResponse:
    params = request.params or {}
    name = params.get("name", "")
    arguments = params.get("arguments", {})

    try:
        result = await self._execute_tool(name, arguments)
        return make_success_response(
            request.id,
            {"content": [{"type": "text", "text": str(result)}]}
        )
    except ValueError as e:
        return make_error_response(
            request.id,
            ErrorCode.INVALID_PARAMS,
            str(e)
        )
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        return make_error_response(
            request.id,
            ErrorCode.INTERNAL_ERROR,
            str(e)
        )
```

---

## 5. Notifications vs Requests

### Key Difference

| Type         | Has `id` | Requires Response |
| ------------ | -------- | ----------------- |
| Request      | Yes      | Yes               |
| Notification | No       | No                |

### Handling Notifications

```python
async def handle_notification(self, method: str, params: Any) -> None:
    """Handle notifications - no response needed."""
    if method == "notifications/state":
        logger.info("Client state notification received")
    # Other notifications...
```

**Important**: Don't return a response for notifications in `handle_request()`!

---

## 6. Performance Optimizations

### Stdio Transport (Zero-Copy orjson)

```python
from omni.mcp.transport.stdio import StdioTransport

transport = StdioTransport()
# Features:
# - Reads raw bytes from stdin.buffer
# - orjson.loads() directly on bytes
# - Writes raw bytes to stdout.buffer
```

### SSE Transport (HTTP + SSE)

```python
from omni.mcp.transport.sse import SSEServer

transport = SSEServer(host="127.0.0.1", port=3000)
# Features:
# - uvloop for high-performance async
# - orjson for fast serialization
# - Automatic ping every 25s
```

---

## 7. Directory Structure

```
packages/python/
├── mcp-server/src/omni/mcp/
│   ├── __init__.py              # Exports (MCPServer, StdioTransport, SSEServer)
│   ├── types.py                 # JSON-RPC 2.0 types (OrjsonModel-based)
│   ├── interfaces.py            # Protocol interfaces
│   ├── server.py                # MCPServer orchestration
│   └── transport/
│       ├── stdio.py             # StdioTransport
│       └── sse.py               # SSEServer
│
└── agent/src/omni/agent/
    └── server.py                # AgentMCPHandler (MCP handler)
```

---

## 8. Common Pitfalls

| Issue               | Cause                              | Solution                                      |
| ------------------- | ---------------------------------- | --------------------------------------------- |
| "expected 'object'" | `inputSchema.type` missing         | Add `"type": "object"`                        |
| Empty tools list    | Handler not initialized            | Call `await handler.initialize()` first       |
| Notification errors | Handling notifications as requests | Use `handle_notification()` for notifications |
| Event loop error    | Calling `asyncio.run()` in loop    | Use native `await`                            |

---

## Debugging

> **When MCP issues occur, check Claude Code's debug logs first:**
>
> ```bash
> cat ~/.claude/debug/latest/*.log
> ```

### Debugging Steps

1. **Check Claude Code logs**:

   ```bash
   cat ~/.claude/debug/latest/*.log | grep -i mcp
   ```

2. **Validate tool schema**:

   ```bash
   uv run pytest packages/python/agent/tests/integration/test_mcp_stdio.py::TestMCPProtocolCompliance -v
   ```

3. **Test server startup**:
   ```bash
   uv run omni mcp --transport stdio 2>&1 | head -50
   ```

---

## References

- [MCP Transport Reference](mcp-transport.md)
- [MCP Server Architecture](../architecture/mcp-server.md)
- [MCP Protocol Specification](https://modelcontextprotocol.io/specification)
