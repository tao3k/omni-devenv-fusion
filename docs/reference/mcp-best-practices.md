# MCP Python SDK Best Practices

> Pure MCP Server Architecture

This document records best practices for developing MCP Servers using the [MCP Python SDK](https://modelcontextprotocol.github.io/python-sdk/api/) with Omni's pure `mcp.server.Server` implementation.

---

## 1. Pure MCP Server vs FastMCP

### Why Pure Server?

Omni uses pure `mcp.server.Server` instead of FastMCP for:

- Direct control over tool listing/execution
- Explicit error handling for TaskGroup
- Optional uvloop (SSE mode) + orjson for performance
- No FastMCP dependency overhead

### Best Practice

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("omni-agent")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Dynamic tool discovery from SkillManager."""
    # Your tool listing logic here
    return []

@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Execute tool via SkillManager."""
    # Your tool execution logic here
    return [TextContent(type="text", text="result")]
```

---

## 2. Async-First

### Why?

MCP Server runs on an async Event Loop. Calling `asyncio.run()` inside the loop causes `RuntimeError: This event loop is already running`.

### Best Practice

```python
# Correct: Native async/await
class SkillManager:
    async def run(self, skill_name: str, command_name: str, args: dict = None) -> str:
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)
        return str(result)

# Wrong: ThreadPoolExecutor (thread overhead + potential deadlock)
async def run(self, ...):
    if asyncio.iscoroutinefunction(func):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, lambda: asyncio.run(func(**args)))
```

### Benefits

- Eliminate event loop conflicts
- No thread switching overhead
- Simpler code

---

## 3. One Tool Pattern

### Why?

Fewer tools for Claude to see is better. A single entry point:

- Keeps context clean
- Simplifies tool registration
- Unifies error handling

### Best Practice

```python
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("omni-agent")

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Expose skill commands as individual tools."""
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    tools = []

    for skill_name in manager.list_loaded():
        for cmd_name in manager.get_commands(skill_name):
            tools.append(Tool(
                name=f"{skill_name}.{cmd_name}",
                description=f"Execute {skill_name}.{cmd_name}",
                inputSchema={"type": "object", "properties": {}, "required": []}
            ))

    return tools

@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Single entry point for all skill commands."""
    from agent.core.skill_manager import get_skill_manager

    args = arguments or {}
    manager = get_skill_manager()

    if "." in name:
        skill_name, command_name = name.split(".", 1)
    else:
        skill_name = name
        command_name = "help"

    result = await manager.run(skill_name, command_name, args)
    return [TextContent(type="text", text=str(result))]
```

### Benefits

- Claude only needs to learn one tool pattern (`skill.command`)
- Avoid tool explosion
- Unified help system

---

## 4. Multimodal Returns (Image Support)

### Why?

MCP protocol natively supports image returns. If your tool generates charts or visualizations, use `Image` type.

### Best Practice

```python
from mcp.types import Image, TextContent

async def generate_chart(data: dict) -> list[TextContent]:
    """Generate a chart image from data."""
    # Generate chart
    chart_bytes = create_chart(data)

    return [
        TextContent(type="text", text="Chart generated successfully"),
        Image(data=chart_bytes, format="png")
    ]
```

### Return Types

| Type            | Use Case      |
| --------------- | ------------- |
| `str`           | Text results  |
| `Image`         | Images/charts |
| `list[Content]` | Mixed content |

---

## 5. Error Handling

### Why?

Tool errors should return user-friendly messages, not internal stack traces.

### Best Practice

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    try:
        result = await perform_operation(name, arguments)
        return [TextContent(type="text", text=str(result))]
    except ValueError as e:
        return [TextContent(type="text", text=f"Invalid input: {e}")]
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]
```

---

## 6. Performance Optimizations

### SSE Mode: uvloop + orjson

```python
async def run_mcp_server(transport: str = "stdio"):
    if transport == "sse" and uvloop:
        uvloop.install()
        logger.info("uvloop enabled for SSE")

    # orjson for fast JSON serialization
    def json_dumps(obj):
        return orjson.dumps(obj).decode("utf-8")
```

---

## 7. Directory Structure Reference

```
src/
└── agent/
    ├── mcp_server.py          # Pure MCP Server entry (mcp.server.Server)
    ├── core/
    │   ├── skill_manager.py   # Command dispatcher (Trinity Architecture)
    │   └── registry/          # Skill registry
    │       ├── core.py
    │       └── loader.py
    └── skills/                # Skill modules
        └── {skill}/
            ├── SKILL.md       # Skill manifest + rules
            └── scripts/       # @skill_script decorated commands
```

---

## 8. Testing Async Tools

### Using pytest-asyncio

```python
import pytest
from agent.core.skill_manager import get_skill_manager

@pytest.mark.asyncio
async def test_skill_command():
    manager = get_skill_manager()
    result = await manager.run("git", "status", {})
    assert "Git Status" in result
```

---

## 9. Common Pitfalls

| Issue                                      | Cause                           | Solution                                             |
| ------------------------------------------ | ------------------------------- | ---------------------------------------------------- |
| `RuntimeError: event loop already running` | Calling `asyncio.run()` in loop | Use native `await`                                   |
| Tool not registered                        | Missing handler decorators      | Use `@server.list_tools()` and `@server.call_tool()` |

---

## 10. Transport Modes

### Stdio Mode (Claude Desktop)

```python
async def _run_stdio():
    async with server_lifespan():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
```

### SSE Mode (Claude Code CLI)

```python
async def _run_sse(host: str, port: int):
    sse = SseServerTransport("/sse")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    app = Starlette(routes=[Route("/sse", handle_sse)])
    uvicorn.run(app, host=host, port=port)
```

---

## References

- [MCP Python SDK Documentation](https://modelcontextprotocol.github.io/python-sdk/api/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/specification)
