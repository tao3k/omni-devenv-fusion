# Stage 3.5: Holographic MCP Gateway Integration

> **Status:** Implemented
> **Goal:** Integrate HolographicRegistry with AgentMCPServer for dynamic tool discovery

## 1. Problem Statement

Traditional MCP server tool listing relies on kernel's skill context:

```python
# Traditional approach - loads all tools at startup
commands = context.get_core_commands()
for cmd_name in commands:
    cmd = context.get_command(cmd_name)
    # Build Tool from command metadata...
```

This causes:

- **No Semantic Search**: LLM can only search by exact tool name
- **Static Discovery**: New tools require server restart
- **Import Overhead**: All tool code must be importable at startup

## 2. Solution: Holographic MCP Integration

Integrate `HolographicRegistry` directly into `AgentMCPServer` for dynamic tool discovery:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AgentMCPServer v2.1                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   MCP Client ──→ list_tools(query?) ──→ HolographicRegistry.search()    │
│                                                    │                    │
│                                                    ▼                    │
│                                           ToolMetadata[] (LanceDB)      │
│                                                    │                    │
│                                                    ▼                    │
│                                           _list_holographic_tools()      │
│                                                    │                    │
│                                                    ▼                    │
│                                           MCP Tool[]                     │
│                                                                         │
│   MCP Client ──→ call_tool(name, args) ──→ LazyTool.load()              │
│                                                    │                    │
│                                                    ▼                    │
│                                           Execute and return result      │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. Implementation

### 3.1 Server Initialization

**File**: `packages/python/agent/src/omni/agent/mcp_server/server.py`

```python
class AgentMCPServer:
    """High-Performance MCP Server (v2.1) with Holographic Mode support."""

    def __init__(self, use_holographic: bool = False):
        """Initialize the MCP Server.

        Args:
            use_holographic: If True, use HolographicRegistry for dynamic tool discovery.
        """
        self._kernel = None
        self._app = Server("omni-agent-os-v2")
        self._start_time = time.time()

        # [v2.1] Holographic Mode flag
        self._use_holographic = use_holographic
        self._holographic_adapter = None
        self._holographic_registry: HolographicRegistry | None = None

        # Routing Tables for Alias Resolution
        self._alias_to_real: dict[str, str] = {}
        self._real_to_display: dict[str, dict] = {}

        self._build_routing_table()
        self._register_handlers()
```

### 3.2 Holographic Registry Initialization

```python
def _init_holographic_mode(self) -> None:
    """Initialize Holographic Registry from router's semantic indexer."""
    if not self._use_holographic:
        return

    if not self._kernel or not self._kernel.is_ready:
        logger.warning("Kernel not ready, cannot initialize holographic mode")
        return

    try:
        # Get the registry from the router's semantic indexer
        router = getattr(self._kernel, "router", None)
        if router and hasattr(router, "_semantic"):
            semantic = router._semantic
            if hasattr(semantic, "_indexer"):
                indexer = semantic._indexer
                if hasattr(indexer, "_registry"):
                    self._holographic_registry = indexer._registry
                    logger.info("✅ Holographic Registry initialized from router's indexer")
                    return

        logger.info("ℹ️  Holographic mode enabled but no registry found")

    except Exception as e:
        logger.error(f"Failed to initialize holographic mode: {e}")
```

### 3.3 Dynamic Tool Listing with Semantic Search

```python
async def _list_holographic_tools(
    self,
    query: str | None = None,
    limit: int | None = None,
) -> list[Tool]:
    """List tools from HolographicRegistry with optional semantic filtering."""
    if not self._holographic_registry:
        return []

    max_tools = limit or 20

    if query:
        # Semantic search using hybrid search
        keywords = ToolContextBuilder.extract_keywords(query)
        tools_metadata = await self._holographic_registry.search_hybrid(
            query=query,
            keywords=keywords,
            limit=max_tools,
        )
    else:
        # List all tools
        tools_metadata = await self._holographic_registry.list_tools(limit=max_tools)

    return self._convert_holographic_to_mcp_tools(tools_metadata)
```

### 3.4 Handler Integration

```python
@self._app.list_tools()
async def list_tools(limit: int | None = None, query: str | None = None) -> list[Tool]:
    """List tools using Zero-Copy Rust Registry with Alias Resolution."""
    # [v2.1] Holographic Mode: Use dynamic tool discovery
    if self._use_holographic and self._holographic_registry:
        return await self._list_holographic_tools(query=query, limit=limit)

    # Fall back to traditional kernel-based listing
    ...
```

### 3.5 CLI Support

```bash
# Standard mode (default)
python -m omni.agent.mcp_server.server

# Holographic mode with semantic search
python -m omni.agent.mcp_server.server --holographic

# SSE mode with holographic
python -m omni.agent.mcp_server.server --sse --holographic --port 8080
```

## 4. Architecture Comparison

### Before (v2.0 - Traditional)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ list_tools()    │ ──→ │ skill_context    │ ──→ │ get_core_cmds() │
│ (static)        │     │ (in-memory)      │     │  O(n) iteration │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### After (v2.1 - Holographic)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ list_tools()    │ ──→ │ Holographic      │ ──→ │ LanceDB Query   │
│ (query optional)│     │ Registry         │     │  O(log n)       │
└─────────────────┘     │ (disk-backed)    │     └─────────────────┘
                        └──────────────────┘            │
                                │                       │
                                │ semantic_search()     │ list_tools()
                                ▼                       ▼
                       ┌─────────────────┐     ┌─────────────────┐
                       │ Hybrid Search   │     │ Vector Search   │
                       │ (Vector + BM25) │     │ (RRF Scoring)   │
                       └─────────────────┘     └─────────────────┘
```

## 5. Key Features

| Feature            | v2.0 (Traditional) | v2.1 (Holographic)  |
| :----------------- | :----------------- | :------------------ |
| **Tool Discovery** | Exact name match   | Semantic search     |
| **Startup Time**   | ~1s                | < 1s (lazy)         |
| **Memory Usage**   | All tools loaded   | Metadata only       |
| **Hot Reload**     | Requires restart   | Instant (DB-backed) |
| **Search Query**   | Not supported      | Natural language    |

## 6. Usage Examples

### 6.1 List All Tools

```python
# MCP Client request
{"method": "tools/list", "params": {}}

# Returns all tools from HolographicRegistry
[{"name": "git.commit", "description": "...", ...}, ...]
```

### 6.2 Semantic Search

```python
# MCP Client request with query
{"method": "tools/list", "params": {"query": "undo my last change"}}

# Holographic mode finds relevant tools
[{"name": "git.revert", "description": "Revert commits...", ...}]
```

### 6.3 Execute with Lazy Loading

```python
# MCP Client request
{"method": "tools/call", "params": {"name": "git.revert", "arguments": {"commit": "abc123"}}}

# Server uses LazyTool to load and execute
result = await lazy_tool.load()
result = await result(commit="abc123")
```

## 7. System Status

The `system_status` tool now includes holographic mode information:

```json
{
  "kernel_ready": true,
  "cortex_ready": true,
  "cortex_indexed": 150,
  "router_status": "ready",
  "tool_count": 42,
  "holographic_mode": "active",
  "uptime_seconds": 123.45,
  "version": "2.1.0"
}
```

## 8. Performance Characteristics

| Operation               | Traditional | Holographic        |
| :---------------------- | :---------- | :----------------- |
| **list_tools()**        | O(n)        | O(log n) + O(k)    |
| **Semantic Search**     | N/A         | O(n) vector + BM25 |
| **Memory (1000 tools)** | ~500MB      | ~10MB              |
| **Tool Discovery**      | Exact match | Fuzzy/Semantic     |

## 9. File References

| Layer           | File Path                                                                 | Purpose                   |
| :-------------- | :------------------------------------------------------------------------ | :------------------------ |
| **Server**      | `packages/python/agent/src/omni/agent/mcp_server/server.py`               | Main MCP Server v2.1      |
| **Registry**    | `packages/python/core/src/omni/core/skills/registry/holographic.py`       | HolographicRegistry       |
| **Adapter**     | `packages/python/core/src/omni/core/kernel/components/holographic_mcp.py` | HolographicMCPToolAdapter |
| **Tests**       | `packages/python/agent/tests/integration/test_mcp_holographic.py`         | Stage 3.5 Tests           |
| **Integration** | `packages/python/agent/tests/integration/test_mcp_stdio.py`               | Existing MCP Tests        |

## 10. Migration Guide

### From v2.0 to v2.1

```python
# OLD: Standard mode (default)
from omni.agent.mcp_server.server import run_stdio_server

await run_stdio_server()

# NEW: Holographic mode (optional)
from omni.agent.mcp_server.server import run_sse_server

await run_sse_server(use_holographic=True)
```

### Programmatic Usage

```python
# Standard mode
server = AgentMCPServer(use_holographic=False)

# Holographic mode
server = AgentMCPServer(use_holographic=True)
await server.run_stdio()
```

## 11. Future Enhancements

### 11.1 Adaptive Mode Switching

```python
# Automatically switch based on query complexity
if query and requires_semantic_search(query):
    return await self._list_holographic_tools(query=query)
else:
    return await self._list_traditional_tools()
```

### 11.2 Caching Layer

```python
# Cache holographic search results for common queries
cache_key = hash(query)
if cache_key in self._search_cache:
    return self._search_cache[cache_key]
```

### 11.3 Multi-Registry Support

```python
# Support multiple registries for different tool categories
self._registries = {
    "core": core_registry,
    "custom": custom_registry,
    "experimental": experimental_registry,
}
```

## Related Documentation

- [Stage 3.4: Holographic MCP Gateway](stage-3-4-holographic-mcp-gateway.md)
- [Holographic Registry](../skills/registry/holographic.md)
- [Schema Singularity](../reference/schema-singularity.md)
- [MCP Server Architecture](../../architecture/mcp-server.md)
