# MCP-Server Architecture - Omni-Dev-Fusion

> Model Context Protocol Server Implementation
> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-27

---

## Overview

The **MCP-Server** (L3 - Transport) provides the Model Context Protocol implementation:

- **MCP SDK** integration for JSON-RPC 2.0 protocol handling
- **Transport implementations** (stdio, SSE)
- **Agent integration** via Kernel
- **Unified logging** via Foundation layer (no stderr pollution)

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

### Key Features (v2.0)

| Feature             | Description                                                               |
| ------------------- | ------------------------------------------------------------------------- |
| **Async Cortex**    | Kernel starts immediately, semantic index builds in background            |
| **Smart Indexing**  | Hash-based skipping of unchanged skills (zero Embedding calls on restart) |
| **Unified Logging** | All logs via Foundation layer (stderr only, no stdout interference)       |
| **Zero-Copy Tools** | Tools served directly from Rust Registry                                  |

### Two Execution Modes

| Mode           | Entry                                 | Per-request work                                                                                                              | Use case                                                   |
| -------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| **Via MCP**    | Client → MCP transport → `call_tool`  | Protocol decode → validate (2s timeout) → `kernel.execute_tool`. **No kernel init**; kernel is already up in the MCP process. | Cursor/Claude Desktop, any MCP client. Optimized hot path. |
| **Standalone** | `omni run`, CLI, or skill without MCP | Full kernel init, skill context, then execute. Different code path (e.g. `runner.run_skill`).                                 | One-off commands, scripts, CI.                             |

MCP-path optimizations: validation runs in a thread with a 2s timeout (skip on slow Rust scanner); schema cache is warmed at lifespan so validation is usually fast.

### Future: Pure Rust MCP Server

For an audit of moving the MCP server to pure Rust (impact on architecture, Python’s role, and migration options), see **[Pure Rust MCP Server Audit](../../plans/pure-rust-mcp-server-audit.md)**.

---

## Architecture

**Location**: `packages/python/agent/src/omni/agent/mcp_server/`

```
omni/agent/mcp_server/
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

### Tool execution timeout (progress-aware)

Tool runs use a **unified timeout framework** so long-running work is only cancelled when there is no progress, not on a fixed wall clock. See [MCP Timeout Spec](../reference/mcp-timeout-spec.md) for the formal specification.

- **Config** (`settings.yaml`): `mcp.timeout` (wall-clock cap, default 1800s/30min; 0 = no cap), `mcp.idle_timeout` (cancel when no heartbeat for this many seconds; default 120; 0 = no idle check).
- **Runner**: `omni.foundation.api.tool_context.run_with_idle_timeout(coro, total_timeout_s, idle_timeout_s)` sets tool context, runs the coroutine, and enforces both limits; it clears context in `finally`.
- **Skills**: During long work (e.g. repomix, LLM wait), call `heartbeat()` from `omni.foundation.api.tool_context` so the runner does not treat the tool as idle.

All MCP tool invocations (kernel path) go through this single entry point; heartbeat setup and idle/total checks live in one place.

---

## Kernel Startup (Critical for MCP)

The Kernel uses **async Cortex building** to ensure fast MCP connection:

### Startup Flow (v2.0)

```
1. Load Skills (2s)
   └─ All skills loaded into context

2. Build Cortex (BACKGROUND)
   └─ Semantic index builds asynchronously
   └─ Kernel ready immediately!

3. Initialize Sniffer
   └─ Context detection ready

4. Kernel Ready (IMMEDIATE!)
   └─ MCP connection can complete
   └─ Tools available
   └─ Cortex building in background...
```

### Async Cortex Building

```python
# engine.py:668-671
# Step 4: Build Semantic Cortex (The Cortex)
# Run in background to prevent blocking kernel startup
logger.info("Building Semantic Cortex (Background)...")
asyncio.create_task(self._safe_build_cortex())
```

**Benefits**:

- MCP connection completes in ~2-3 seconds
- No 30-second timeout issues
- Tools immediately available
- Semantic routing activates when Cortex ready

### Smart Indexing

The Cortex uses hash-based detection to skip unchanged skills:

```python
# indexer.py:197-227
# Calculate hash of skills configuration
current_hash = hashlib.md5(json.dumps(current_state).encode())

# Check if already indexed
if saved_meta.get("hash") == current_hash:
    logger.info(f"Cortex index up-to-date, skipping build")
    return self._indexed_count  # Skip ALL embedding calls!
```

**Performance**:
| Scenario | Before | After |
|----------|--------|-------|
| First run | ~200s | ~2s |
| Restart (no changes) | ~200s | **~0.5s** |
| Restart (changes) | ~200s | ~2s |

---

## Logging (v2.0)

All MCP logging uses Foundation layer to prevent stdout interference:

```python
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.agent.mcp_server")
```

**Key rules**:

- Logs go to stderr (via Foundation layer)
- MCP protocol messages go to stdout
- No DEBUG logs without `--verbose` flag

### Verbose Mode

```bash
# Enable debug logging
uv run omni mcp --transport stdio --verbose
```

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
- Logging to stderr (via Foundation)

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

## Troubleshooting

### Connection Timeout (30s)

**Problem**: MCP client times out during connection.

**Solutions**:

1. **Enable verbose mode to see progress**:

   ```bash
   uv run omni mcp --verbose 2>&1 | head -50
   ```

2. **Check for stderr pollution**:

   ```bash
   # Ensure no print() statements going to stdout
   uv run omni mcp --transport stdio 2>/dev/null
   ```

3. **Verify async Cortex is working**:
   ```bash
   uv run omni mcp 2>&1 | grep -E "(Ready|Background|Cortex)"
   # Should see: "Kernel ready" within ~3 seconds
   ```

### Empty Tools List

**Problem**: Connected but no tools available.

**Solutions**:

1. Check kernel initialization:

   ```bash
   uv run omni mcp 2>&1 | grep -E "(Kernel|Ready|Skills)"
   ```

2. Verify skills loaded:
   ```bash
   uv run omni mcp 2>&1 | grep -E "commands|skills"
   ```

### Slow First Connection

**Problem**: First connection takes >30 seconds.

**Cause**: Embedding API call during Cortex build.

**Solution**: Smart Indexing now skips unchanged skills:

```bash
# First run creates .meta.json
uv run omni mcp

# Subsequent runs skip embedding (if skills unchanged)
uv run omni mcp
# Should be ~0.5s
```

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

## Related Documentation

- [MCP Transport Reference](../reference/mcp-transport.md)
- [MCP Best Practices](../reference/mcp-best-practices.md)
- [Kernel Architecture](kernel.md)
- [Router Architecture](router.md)
- [Smart Indexing (indexer.py)](../reference/indexer.md)
