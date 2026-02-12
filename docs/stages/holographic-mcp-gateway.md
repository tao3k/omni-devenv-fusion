# Stage 3.4: Holographic MCP Gateway

> **Status:** Implemented
> **Goal:** Integrate HolographicRegistry with MCP Server for dynamic tool discovery

## 1. Problem Statement

Traditional MCP tool registration relies on **Python import** (in-memory):

```python
# Traditional approach - imports all tools at startup
from skills.git import commit, push, pull
# For 500 skills: 30+ seconds startup, high memory
```

This causes:

- **Import Explosion**: Loading 500 `.py` files at startup
- **No Semantic Search**: Only name-based lookup
- **Fragile Reloading**: Python's `reload()` is unreliable

## 2. Solution: Holographic MCP Gateway

Replace in-memory registration with **database-backed dynamic discovery**:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Holographic MCP Gateway                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   MCP Client ──→ list_tools() ──→ HolographicRegistry.search() │
│                                                 │              │
│                                                 ▼              │
│                                        ToolMetadata[] (LanceDB) │
│                                                 │              │
│                                                 ▼              │
│                                        ToolContextBuilder       │
│                                                 │              │
│                                                 ▼              │
│                                        MCP Tool[]               │
│                                                 │              │
│                                                 ▼              │
│                                        LazyTool.load() (on demand)│
└─────────────────────────────────────────────────────────────────┘
```

## 3. Implementation

### 3.1 Core Adapter

**File**: `packages/python/core/src/omni/core/kernel/components/holographic_mcp.py`

```python
class HolographicMCPToolAdapter:
    """MCP Tool Adapter using HolographicRegistry for dynamic tool discovery."""

    def __init__(
        self,
        server: MCPServer,
        registry: HolographicRegistry,
        default_limit: int = 20,
    ) -> None:
        self._server = server
        self._registry = registry
        self._default_limit = default_limit
        self._schema_cache: dict[str, dict] = {}
        self._register_handlers()

    async def list_tools(
        self,
        query: str | None = None,
        limit: int | None = None,
    ) -> list[Tool]:
        """List tools from HolographicRegistry with optional semantic filtering."""
        max_tools = limit or self._default_limit

        if query:
            # Semantic search using hybrid search
            keywords = ToolContextBuilder.extract_keywords(query)
            tools_metadata = await self._registry.search_hybrid(
                query=query,
                keywords=keywords,
                limit=max_tools,
            )
        else:
            # List all tools
            tools_metadata = await self._registry.list_tools(limit=max_tools)

        return self._convert_to_mcp_tools(tools_metadata)

    async def call_tool(self, name: str, args: dict) -> list[dict]:
        """Execute tool with lazy loading."""
        metadata = await self._registry.get_tool(name)
        if metadata is None:
            return [{"type": "text", "text": f"Tool not found: {name}"}]

        # Lazy load the tool implementation
        lazy_tool = LazyTool(metadata=metadata, registry=self._registry)
        func = await lazy_tool.load()

        # Execute and return result
        ...
```

### 3.2 Key Features

| Feature            | Traditional               | Holographic             |
| :----------------- | :------------------------ | :---------------------- |
| **Startup**        | Load all 500 skills       | < 1 second (no imports) |
| **Tool Discovery** | Exact name match          | Semantic search         |
| **Code Loading**   | Eager (all at startup)    | Lazy (on execution)     |
| **Hot Reload**     | Fragile restart needed    | Instant (DB-backed)     |
| **Memory**         | High (all code in memory) | Low (only metadata)     |

### 3.3 Semantic Search Integration

```python
# User says: "undo my last change"
# Traditional: Must know exact tool name "git_revert"
# Holographic: Semantic search finds the right tool

tools = await adapter.list_tools(query="undo my last change")
# Returns: [Tool(name="git_revert"), Tool(name="git_reset")]
```

## 4. Architecture Comparison

### Before (Traditional Agent)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ MCPToolAdapter  │ ──→ │ _tools (dict)    │ ──→ │ MCP Server      │
│ (In-mem reg)    │     │ Memory Usage:    │     │ list_tools      │
│                 │     │ 500MB+           │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │
        │ register_tool()
        ▼
   Python Import
   (Load all code at startup)
```

### After (Agentic OS)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Holographic     │ ──→ │ LanceDB (Disk)   │ ──→ │ MCP Server      │
│ MCP Adapter     │     │ Memory Usage:    │     │ list_tools      │
│                 │     │ <10MB            │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                       ▲
        │                       │
        │ list_tools()          │ Rust Scanner
        │                       │ (File change watch)
        ▼                       │
   LazyTool.load() ─────────────┘
   (Load code on demand)
```

## 5. Factory Function

```python
async def create_holographic_mcp_adapter(
    server: MCPServer,
    vector_store: PyVectorStore,
    embedding_service: EmbeddingService | None = None,
    default_limit: int = 20,
) -> HolographicMCPToolAdapter:
    """Factory to create adapter with HolographicRegistry."""
    registry = HolographicRegistry(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    return HolographicMCPToolAdapter(
        server=server,
        registry=registry,
        default_limit=default_limit,
    )
```

## 6. Integration with Reactive Watcher

```python
# Full integration with file watching
from omni.core.kernel.watcher import ReactiveSkillWatcher
from omni.core.skills.indexer import SkillIndexer

# Create components
indexer = SkillIndexer(vector_store=vector_store, embedder=embedder)
watcher = ReactiveSkillWatcher(
    root_dir="/skills",
    indexer=indexer,
)

# Start watching (auto-indexes on file changes)
await watcher.start()

# Create MCP adapter using the same registry
adapter = HolographicMCPToolAdapter(
    server=mcp_server,
    registry=indexer._registry,  # Share the same registry
)
```

## 7. Performance Characteristics

| Operation               | Traditional        | Holographic        |
| :---------------------- | :----------------- | :----------------- |
| **Server Startup**      | ~30s (500 imports) | < 1s (no imports)  |
| **list_tools()**        | O(1) dict lookup   | O(log n) DB query  |
| **Semantic Search**     | N/A                | O(n) vector + BM25 |
| **Tool Execution**      | O(1) function call | O(1) lazy import   |
| **Memory (1000 tools)** | ~500MB             | ~10MB              |

## 8. File References

| Layer        | File Path                                                                 |
| :----------- | :------------------------------------------------------------------------ |
| **Adapter**  | `packages/python/core/src/omni/core/kernel/components/holographic_mcp.py` |
| **Registry** | `packages/python/core/src/omni/core/skills/registry/holographic.py`       |
| **Indexer**  | `packages/python/core/src/omni/core/skills/indexer.py`                    |
| **Watcher**  | `packages/python/core/src/omni/core/kernel/watcher.py`                    |
| **Tests**    | `packages/python/core/tests/integration/test_reactive_loader.py`          |

## 9. Migration Guide

### From Traditional to Holographic

```python
# OLD: Traditional MCPToolAdapter
from omni.core.kernel.components.mcp_tool import MCPToolAdapter

adapter = MCPToolAdapter(server)
adapter.register_tool("git", "commit", commit_func)
tools = await adapter.list_tools()

# NEW: HolographicMCPToolAdapter
from omni.core.kernel.components.holographic_mcp import HolographicMCPToolAdapter

adapter = HolographicMCPToolAdapter(server, registry)
tools = await adapter.list_tools()  # Dynamic from LanceDB
```

## 10. Future Enhancements

### 10.1 Tool Versioning

```python
# Support multiple versions of the same tool
tools = await adapter.list_tools(query="file read", version="v2")
```

### 10.2 Tool Deprecation

```python
# Mark tools as deprecated with migration paths
tools = await adapter.list_tools(include_deprecated=False)
```

### 10.3 Permission-Aware Listing

```python
# Only show tools the user has permission to use
tools = await adapter.list_tools(permissions=user.permissions)
```

## Related Documentation

- [Holographic Registry](../skills/registry/holographic.md)
- [Schema Singularity](../reference/schema-singularity.md)
- [Reactive Skill Loader](adaptive-loader.md)
- [MCP Server Architecture](../../architecture/mcp-server.md)
