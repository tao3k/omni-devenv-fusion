# MCP Python SDK Best Practices

> Based on Omni-DevEnv Fusion Phase 25+

This document records best practices for developing MCP Servers using the [MCP Python SDK](https://modelcontextprotocol.github.io/python-sdk/api/).

---

## 1. Async-First

### Why?

MCP Server (FastMCP) runs on an async Event Loop. Calling `asyncio.run()` inside the loop causes `RuntimeError: This event loop is already running`.

### Best Practice

```python
# ✅ Correct: Native async/await
class SkillManager:
    async def run(self, skill_name: str, command_name: str, args: dict = None) -> str:
        if asyncio.iscoroutinefunction(func):
            result = await func(**args)  # Direct await
        else:
            result = func(**args)  # Sync functions are safe too
        return str(result)

# ❌ Wrong: ThreadPoolExecutor (thread overhead + potential deadlock)
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

## 2. Context Injection

### Why?

FastMCP supports automatic `Context` injection for sending logs and progress updates to Claude, improving UX.

### Best Practice

```python
from mcp.server.fastmcp import FastMCP, Context

mcp = FastMCP("my-server")

@mcp.tool()
async def my_tool(input: str, ctx: Context = None) -> str:
    # Send log
    if ctx:
        ctx.info(f"Processing: {input}")

    # Report progress
    if ctx:
        await ctx.report_progress(0, 100)

    # Do work...
    result = await do_work(input)

    if ctx:
        await ctx.report_progress(100, 100)

    return result
```

### Benefits

- Claude sees real-time logs during long operations
- Progress bar provides visual feedback
- Avoid "dry waiting" UX issues

---

## 3. Multimodal Returns (Image Support)

### Why?

MCP protocol natively supports image returns. If your tool generates charts or visualizations, use `Image` type.

### Best Practice

```python
from mcp.server.fastmcp import FastMCP, Image

@mcp.tool()
def generate_chart(data: dict) -> Image:
    """Generate a chart image from data."""
    # Generate chart
    chart_bytes = create_chart(data)
    return Image(data=chart_bytes, format="png")
```

### Return Types

| Type            | Use Case      |
| --------------- | ------------- |
| `str`           | Text results  |
| `Image`         | Images/charts |
| `list[Content]` | Mixed content |

---

## 4. One Tool Pattern

### Why?

Fewer tools for Claude to see is better. A single entry point:

- Keeps context clean
- Simplifies tool registration
- Unifies error handling

### Best Practice

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("omni-agentic-os")

# Single tool entry point
@mcp.tool(name="omni")
async def omni(input: str, args: dict = None, ctx: Context = None) -> str:
    """
    Execute any skill command or get help.

    All operations go through this single gate.
    """
    # Route to specific command
    return await dispatch(input, args)
```

### Benefits

- Claude only needs to learn one tool
- Avoid tool explosion
- Unified help system

---

## 5. Prompt Templates

### Why?

FastMCP supports `@mcp.prompt()` decorator for providing predefined prompt templates to Claude.

### Best Practice

```python
@mcp.prompt()
def help_prompt() -> str:
    """Returns usage instructions for this server."""
    return """
    # Available Commands

    - `analyze`: Analyze the input data
    - `visualize`: Generate a chart

    Use: @omni("command_name")
    """
```

### Benefits

- Immediate context guidance for Claude
- Lower learning curve

---

## 6. Error Handling

### Why?

Tool errors should return user-friendly messages, not internal stack traces.

### Best Practice

```python
@mcp.tool()
async def risky_operation(input: str, ctx: Context = None) -> str:
    try:
        result = await perform_operation(input)
        return result
    except ValueError as e:
        return f"Invalid input: {e}"
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return f"Error: {e}"
```

---

## 7. Tool Registration Check

### Development Debugging

```python
def main():
    mcp.run(transport="stdio")

    # Or check tools list during debugging
    tools = list(mcp._tool_manager._tools.values())
    print(f"Registered tools: {[t.name for t in tools]}")
```

---

## 8. Directory Structure Reference

```
src/
└── agent/
    ├── mcp_server.py          # FastMCP entry, defines tools
    ├── core/
    │   └── skill_manager.py   # Command dispatcher
    └── skills/                # Skill modules
        └── {skill}/
            ├── prompts.md     # Skill rules
            ├── tools.py       # Exposes EXPOSED_COMMANDS
            └── guide.md       # Usage guide
```

---

## 9. Testing Async Tools

### Using pytest-asyncio

```python
import pytest
from agent.mcp_server import omni

@pytest.mark.asyncio
async def test_omni_git_status():
    result = await omni("git.status")
    assert "Git Status" in result
```

---

## 10. Common Pitfalls

| Issue                                      | Cause                           | Solution                                     |
| ------------------------------------------ | ------------------------------- | -------------------------------------------- |
| `RuntimeError: event loop already running` | Calling `asyncio.run()` in loop | Use native `await`                           |
| Context is None                            | Not passed                      | Check `ctx: Context = None` parameter        |
| Tool not registered                        | Decorator order issue           | Ensure `@mcp.tool()` is right above function |

---

## References

- [MCP Python SDK Documentation](https://modelcontextprotocol.github.io/python-sdk/api/)
- [FastMCP GitHub](https://github.com/modelcontextprotocol/python-sdk)
