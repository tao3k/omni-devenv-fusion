# MCP Tool Schema - Developer Guide

> Trinity Architecture - Agent Layer (L3 Transport)
> Last Updated: 2026-01-23

This document describes the MCP Tool schema system, including `inputSchema`, `annotations`, and how to use the `@skill_command` decorator effectively.

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
      "description": "文件路径"
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

| JSON Schema Type | Python Type | Example |
|-----------------|-------------|---------|
| `string` | `str` | `"hello"` |
| `integer` | `int` | `42` |
| `number` | `float` | `3.14` |
| `boolean` | `bool` | `true` / `false` |
| `array` | `list` | `["a", "b"]` |
| `object` | `dict` | `{"key": "value"}` |
| `enum` | `Literal` | `["a", "b", "c"]` |

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
    read_only=True,      # 只读操作
    idempotent=True,     # 幂等调用
)
def search_code(
    query: str,                          # 必需参数
    file_pattern: str = "*.py",          # 有默认值
    case_sensitive: bool = False,        # 布尔类型
    max_results: int = 100,              # 整数
    encoding: Literal["utf-8", "gbk"] = "utf-8",  # 枚举
    exclude_patterns: list[str] | None = None,    # 可选列表
) -> str:
    """搜索代码中的模式"""
    ...
```

### Generated inputSchema

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "搜索查询字符串"
    },
    "file_pattern": {
      "type": "string",
      "description": "文件匹配模式",
      "default": "*.py"
    },
    "case_sensitive": {
      "type": "boolean",
      "description": "是否区分大小写",
      "default": false
    },
    "max_results": {
      "type": "integer",
      "description": "最大结果数",
      "default": 100
    },
    "encoding": {
      "type": "string",
      "enum": ["utf-8", "gbk"],
      "description": "文件编码"
    },
    "exclude_patterns": {
      "type": "array",
      "items": {"type": "string"},
      "description": "排除模式列表"
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
  "name": "filesystem.search_code",
  "description": "Search for patterns in code files",
  "annotations": {
    "title": "Code Search",
    "readOnlyHint": true,
    "destructiveHint": false,
    "idempotentHint": true,
    "openWorldHint": false
  },
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "搜索查询字符串"
      }
    },
    "required": ["query"]
  }
}
```

---

## 5. @skill_command Parameters Reference

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `name` | `str \| None` | Function name | Tool name |
| `description` | `str \| None` | Docstring first line | Tool description |
| `category` | `str` | `"general"` | Tool category |
| `title` | `str \| None` | `None` | MCP title annotation |
| `read_only` | `bool` | `False` | MCP readOnlyHint (true = safe) |
| `destructive` | `bool` | `False` | MCP destructiveHint (may modify data) |
| `idempotent` | `bool` | `False` | MCP idempotentHint (safe to retry) |
| `open_world` | `bool` | `False` | MCP openWorldHint (accesses external) |
| `inject_root` | `bool` | `False` | Auto-inject project root |
| `inject_settings` | `list[str] \| None` | `None` | Settings to inject |
| `autowire` | `bool` | `True` | Enable DI auto-wiring |
| `retry_on` | `tuple[type[Exception], ...] \| None` | `None` | Exceptions to retry |
| `max_attempts` | `int` | `1` | Max retry attempts |
| `cache_ttl` | `float` | `0.0` | Result cache TTL (seconds) |

---

## 6. MCP Annotations Guide

MCP annotations help the LLM understand tool characteristics:

| Annotation | Values | Meaning |
|------------|--------|---------|
| `title` | `str \| None` | Human-readable tool title |
| `readOnlyHint` | `bool` | `true` = read-only, safe to call |
| `destructiveHint` | `bool` | `true` = modifies data, confirm first |
| `idempotentHint` | `bool` | `true` = safe to retry |
| `openWorldHint` | `bool` | `true` = accesses external network |

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
    "required_param": {"type": "string"},
    "optional_param": {"type": "string", "default": "default"},
    "optional_list": {"type": "array", "items": {"type": "string"}}
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
