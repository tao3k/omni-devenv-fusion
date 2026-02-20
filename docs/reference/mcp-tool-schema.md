# MCP Tool Schema - Developer Guide

> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-02-19

This document describes the MCP Tool schema system, including `inputSchema`, **tools/call result contract**, **agent server info**, and how to use the `@skill_command` decorator effectively.

---

## 0a. Agent server info (GET /sse, /mcp)

**Shared schema (SSOT):** `packages/shared/schemas/omni.agent.server_info.v1.schema.json`  
**API:** `omni.foundation.api.agent_schema` — `get_schema_path()`, `get_validator()`, `validate(payload)`, `build_server_info(name, version, protocol_version, message)`.

When a client sends GET to `/sse` or `/mcp` (no body), the server returns a JSON object conforming to this schema: `name`, `version`, `protocolVersion`, and optional `message`. The SSE handler uses `build_server_info()` so responses are validated against the shared schema.

---

## 0b. tools/list payload + observability (Rust DB-first)

`tools/list` now uses the Rust registry DB as the only source of truth (no in-memory fallback path). Runtime behavior:

- Registry read path: `store.list_all_tools(table_name, None)` must succeed, otherwise request fails fast.
- Payload compaction:
  - Tool `description` is normalized and capped (`140` chars by default, configurable via `mcp.tools_list.description_max_chars`).
  - `inputSchema` recursively drops non-essential metadata keys (`description`, `examples`, `example`, `title`, `default`, `$comment`, `markdownDescription`).
  - Request concurrency gate: handler-side `tools/list` in-flight cap is configurable via `mcp.tools_list.max_in_flight` (default `90`).
- Hot polling controls:
  - short TTL cache + singleflight rebuild (`_tools_cache_ttl_secs`).
  - Rust agent-side `tools/list` snapshot cache TTL is configurable via `mcp.agent_list_tools_cache_ttl_ms` (or `OMNI_AGENT_MCP_LIST_TOOLS_CACHE_TTL_MS` override).
  - Rust gateway `GET /health` exposes MCP cache summary (`cache_hits`, `cache_misses`, `cache_refreshes`, `hit_rate_pct`) when MCP is enabled.
  - Dynamic Loader info log throttling (`_tools_log_interval_secs`).
  - SSE runtime auto-selects fastest available uvicorn backend (`uvloop`/`httptools`).
  - Fast runtime dependencies are declared in `omni-agent` / `omni-mcp`; run `uv sync` after pulling updates.
  - If optional fast modules are missing at runtime, startup logs an explicit warning and falls back to `asyncio`/`h11`.
  - SSE request pressure observability is enabled:
    - Periodic pressure log: endpoint-level request count, errors, in-flight/max-in-flight, `p95/p99`.
    - `/health` includes a lightweight `observability` summary (`total_requests`, `total_errors`, in-flight, top endpoints).

### Periodic stats log

The handler emits aggregated observability logs for `tools/list` at a fixed interval (`_tools_stats_log_interval_secs`, default `60s`):

```text
[MCP] tools/list stats requests=<n> hit_rate=<pct> cache_hits=<n> cache_misses=<n> build_count=<n> build_failures=<n> build_avg_ms=<ms> build_max_ms=<ms>
```

Use this line as the primary signal for cache effectiveness and registry build stability during load tests.

### One-shot probe command

Use the channel script to run health, payload size, embed dimension, sequential latency, concurrent latency, and optional log scanning in one command:

```bash
scripts/channel/test-omni-agent-mcp-tools-list-observability.sh \
  --base-url http://127.0.0.1:3002 \
  --log-file .run/logs/omni-mcp-sse-3002.log \
  --json-out .run/reports/mcp-tools-list-observability.json
```

### Concurrency sweep + SLO recommendation

Use this sweep command to benchmark multiple concurrency points and output a recommended cap based on `p95/p99` SLO targets:

```bash
scripts/channel/test-omni-agent-mcp-tools-list-concurrency-sweep.sh \
  --base-url http://127.0.0.1:3002 \
  --total 1000 \
  --concurrency-values 40,80,120,160,200 \
  --p95-slo-ms 400 \
  --p99-slo-ms 800
```

The sweep client now auto-tunes HTTP connection-pool limits from the tested max concurrency to avoid client-side queue bottlenecks biasing benchmark results.

Reports are written to:

- `.run/reports/mcp-tools-list-observability-<host>-<port>-concurrency-sweep.json`
- `.run/reports/mcp-tools-list-observability-<host>-<port>-concurrency-sweep.md`

The JSON includes:

- per-point throughput and tail latency
- estimated knee concurrency
- `recommended_concurrency` and feasible set under the SLO

---

## 0. tools/call result contract (response shape)

**Shared schema (SSOT):** `packages/shared/schemas/omni.mcp.tool_result.v1.schema.json`  
**API:** `omni.foundation.api.mcp_schema` — `get_schema_path()`, `get_validator()`, `validate(payload)`, `build_result(text, is_error)`, `is_canonical(value)`.

All skill tool results are normalized so MCP clients (e.g. Cursor) never receive `result: null` or unrecognized keys, avoiding `invalid_union` schema errors.

- **Success**: The JSON-RPC response has `result` set to an **object** with:
  - `content`: array of `{ "type": "text", "text": "<string>" }` (never null; empty string if no output).
  - `isError`: `false`.
- **Error**: The server sends a JSON-RPC **error** response (`error` object, no `result`). The stdio transport turns handler error responses into raised exceptions so the MCP layer always emits either a valid `result` object or an `error` object.

**Where normalization happens:**

- **In `@skill_command`** (Foundation): Every decorated function’s return value is wrapped by `normalize_mcp_tool_result()` so the callable always yields a payload that conforms to the shared schema. Constant `MCP_TOOL_RESULT_SCHEMA_V1` refers to the schema file.
- **In the agent handler**: If `skill.execute()` already returns this shape, the handler uses it as-is; otherwise it falls back to `_tool_result_content()` for backward compatibility.

CI validates normalized results against the shared schema (`test_mcp_tool_result_validates_against_shared_schema`).

---

## 1. inputSchema Overview

`inputSchema` is a **JSON Schema standard** format used to define tool parameter structures. MCP protocol uses it to:

1. Tell the LLM what parameters the tool requires
2. Validate parameter formats
3. Generate UI forms for parameter input

### Standard JSON Schema Structure

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "File path"
    },
    "encoding": {
      "type": "string",
      "enum": ["utf-8", "gbk", "ascii"],
      "default": "utf-8"
    }
  },
  "required": ["path"]
}
```

---

## 2. Type System Mapping

| JSON Schema Type | Python Type | Example            |
| ---------------- | ----------- | ------------------ |
| `string`         | `str`       | `"hello"`          |
| `integer`        | `int`       | `42`               |
| `number`         | `float`     | `3.14`             |
| `boolean`        | `bool`      | `true` / `false`   |
| `array`          | `list`      | `["a", "b"]`       |
| `object`         | `dict`      | `{"key": "value"}` |
| `enum`           | `Literal`   | `["a", "b", "c"]`  |

### Python Type Hints to JSON Schema

```python
from typing import Literal

def example(
    name: str,                           # → {"type": "string"}
    count: int,                          # → {"type": "integer"}
    price: float,                        # → {"type": "number"}
    enabled: bool,                       # → {"type": "boolean"}
    tags: list[str],                     # → {"type": "array", "items": {"type": "string"}}
    metadata: dict[str, str],            # → {"type": "object"}
    status: Literal["pending", "done"],  # → {"type": "string", "enum": ["pending", "done"]}
    optional: str | None = None,         # → omitted from required
) -> str:
    ...
```

---

## 3. Complete Example

### Python Definition

```python
from typing import Literal
from omni.foundation.api.decorators import skill_command

@skill_command(
    name="search_code",
    description="Search for patterns in code files",
    # MCP Annotations
    read_only=True,      # Read-only operation
    idempotent=True,     # Idempotent call
)
def search_code(
    query: str,                          # Required parameter
    file_pattern: str = "*.py",          # Has default value
    case_sensitive: bool = False,        # Boolean type
    max_results: int = 100,              # Integer
    encoding: Literal["utf-8", "gbk"] = "utf-8",  # Enum
    exclude_patterns: list[str] | None = None,    # Optional list
) -> str:
    """Search for patterns in code"""
    ...
```

### Generated inputSchema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search query string"
    },
    "file_pattern": {
      "type": "string",
      "description": "File match pattern",
      "default": "*.py"
    },
    "case_sensitive": {
      "type": "boolean",
      "description": "Whether to be case-sensitive",
      "default": false
    },
    "max_results": {
      "type": "integer",
      "description": "Maximum number of results",
      "default": 100
    },
    "encoding": {
      "type": "string",
      "enum": ["utf-8", "gbk"],
      "description": "File encoding"
    },
    "exclude_patterns": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of exclude patterns"
    }
  },
  "required": ["query"]
}
```

---

## 4. Complete MCP Tool Definition

This is how the tool appears in the MCP protocol:

```json
{
  "name": "omnicell.run_command",
  "description": "Execute Nushell command, returns structured JSON",
  "annotations": {
    "title": "OmniCell Command",
    "readOnlyHint": true,
    "destructiveHint": false,
    "idempotentHint": true,
    "openWorldHint": false
  },
  "inputSchema": {
    "type": "object",
    "properties": {
      "cmd": {
        "type": "string",
        "description": "Nushell command to execute"
      },
      "ensure_structured": {
        "type": "boolean",
        "description": "Force JSON output for observation commands"
      }
    },
    "required": ["cmd"]
  }
}
```

---

## 5. @skill_command Parameters Reference

| Parameter         | Type                                  | Default              | Purpose                               |
| ----------------- | ------------------------------------- | -------------------- | ------------------------------------- |
| `name`            | `str \| None`                         | Function name        | Tool name                             |
| `description`     | `str \| None`                         | Docstring first line | Tool description                      |
| `category`        | `str`                                 | `"general"`          | Tool category                         |
| `title`           | `str \| None`                         | `None`               | MCP title annotation                  |
| `read_only`       | `bool`                                | `False`              | MCP readOnlyHint (true = safe)        |
| `destructive`     | `bool`                                | `False`              | MCP destructiveHint (may modify data) |
| `idempotent`      | `bool`                                | `False`              | MCP idempotentHint (safe to retry)    |
| `open_world`      | `bool`                                | `False`              | MCP openWorldHint (accesses external) |
| `inject_root`     | `bool`                                | `False`              | Auto-inject project root              |
| `inject_settings` | `list[str] \| None`                   | `None`               | Settings to inject                    |
| `autowire`        | `bool`                                | `True`               | Enable DI auto-wiring                 |
| `retry_on`        | `tuple[type[Exception], ...] \| None` | `None`               | Exceptions to retry                   |
| `max_attempts`    | `int`                                 | `1`                  | Max retry attempts                    |
| `cache_ttl`       | `float`                               | `0.0`                | Result cache TTL (seconds)            |

---

## 6. MCP Annotations Guide

MCP annotations help the LLM understand tool characteristics:

| Annotation        | Values        | Meaning                               |
| ----------------- | ------------- | ------------------------------------- |
| `title`           | `str \| None` | Human-readable tool title             |
| `readOnlyHint`    | `bool`        | `true` = read-only, safe to call      |
| `destructiveHint` | `bool`        | `true` = modifies data, confirm first |
| `idempotentHint`  | `bool`        | `true` = safe to retry                |
| `openWorldHint`   | `bool`        | `true` = accesses external network    |

### How LLM Uses Annotations

```
┌────────────────────────────────────────────────────────────┐
│  LLM sees annotations and makes better decisions:          │
│                                                            │
│  • readOnlyHint=true   → "This tool is safe, read-only"   │
│  • destructiveHint=true → "Confirm before, may have side effects" │
│  • openWorldHint=true   → "May access external/untrusted" │
│  • idempotentHint=true  → "Safe to retry"                  │
└────────────────────────────────────────────────────────────┘
```

### Annotation Examples

```python
# Safe read-only tool
@skill_command(
    name="read_file",
    description="Read file contents",
    read_only=True,
    idempotent=True,
)
def read_file(path: str) -> str: ...

# Destructive tool (requires confirmation)
@skill_command(
    name="delete_file",
    description="Delete a file",
    destructive=True,
)
def delete_file(path: str) -> str: ...

# External network tool (untrusted)
@skill_command(
    name="fetch_url",
    description="Fetch URL content",
    open_world=True,
)
def fetch_url(url: str) -> str: ...
```

---

## 7. Dependency Injection

The `@skill_command` decorator supports automatic dependency injection:

```python
from omni.foundation.config.settings import Settings
from omni.foundation.config.paths import ConfigPaths
from omni.foundation.api.decorators import skill_command

@skill_command(
    name="my_command",
    autowire=True,  # Enable auto-injection
)
async def my_command(
    message: str,
    settings: Settings,    # Auto-injected
    paths: ConfigPaths,    # Auto-injected
) -> str:
    # No need to pass settings/paths - they're injected
    api_key = settings.get("api.key")
    log_dir = paths.get_log_dir()
    return f"{message} with {api_key} in {log_dir}"
```

### How It Works

1. `autowire=True` enables `@inject_resources` decorator
2. Decorator inspects function signature for `Settings`/`ConfigPaths` type hints
3. Dependencies are automatically resolved from the DI container
4. Injected parameters are excluded from `inputSchema`

---

## 8. Auto-Generated Schema

The `@skill_command` decorator automatically generates `inputSchema`:

```python
@skill_command(name="example")
def example(
    required_param: str,                    # In required list
    optional_param: str = "default",        # Has default, optional
    optional_list: list[str] | None = None, # Union with None, optional
) -> str: ...
```

Generated schema:

```json
{
  "type": "object",
  "properties": {
    "required_param": { "type": "string" },
    "optional_param": { "type": "string", "default": "default" },
    "optional_list": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["required_param"]
}
```

### Parameters Excluded from Schema

The following are automatically excluded:

- `Settings` type parameters (injected)
- `ConfigPaths` type parameters (injected)
- `project_root` (when `inject_root=True`)
- `*args` and `**kwargs`
- Parameters with `None` default (Optional types)

---

## 9. Testing Your Tool Schema

### Validate Schema Generation

```python
from omni.foundation.api.decorators import skill_command, get_script_config

@skill_command(name="my_tool")
def my_tool(param: str) -> str: ...

config = get_script_config(my_tool)
print(config["input_schema"])
```

### Run Protocol Compliance Tests

```bash
uv run pytest packages/python/core/tests/units/skills/test_skill_script.py -v
```

---

## 10. Related Documentation

- [MCP Best Practices](mcp-best-practices.md) - MCP protocol implementation
- [MCP Transport](mcp-transport.md) - Transport layer details
- [MCP Server Architecture](../architecture/mcp-server.md) - Server design
- [MCP Protocol Specification](https://modelcontextprotocol.io/specification)
