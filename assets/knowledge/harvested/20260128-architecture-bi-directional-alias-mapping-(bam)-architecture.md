# Bi-directional Alias Mapping (BAM) Architecture

> **Category**: ARCHITECTURE | **Date**: 2026-01-28

# Bi-directional Alias Mapping (BAM) Architecture

## Overview

The Bi-directional Alias Mapping (BAM) mechanism is a core component of the Trinity Architecture's Agent Layer. It acts as an **API Gateway** between the LLM interface (MCP) and the Kernel's internal command registry, enabling **configuration-driven tool naming** without code changes.

## Problem Statement

In a large Agentic OS with 100+ tools, naming conventions can cause issues:

1. **Token Efficiency**: `save_memory` (12 tokens) vs `memory.remember_insight` (26 tokens)
2. **Semantic Weight**: LLMs prefer verb-first names (`save_`, `search_`, `commit_`)
3. **Namespace Complexity**: Internal structure (`code_tools.replace_in_file`) may not match user mental models
4. **Static Conventions**: Code-based naming requires PRs to change

## Solution: Bi-directional Alias Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Bi-directional Alias Mapping                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Layer 1: LLM/MCP Interface              Layer 2: Kernel/Registry          │
│   ──────────────────────────────           ────────────────────────────      │
│                                                                              │
│   Tools exposed to LLM                     Internal command names            │
│   (Short, verb-first, friendly)            (Structured, namespaced)         │
│                                                                              │
│   ┌─────────────────────┐                  ┌─────────────────────┐          │
│   │  "save_memory"      │ ─── list_tools ──►│ memory.remember_    │          │
│   │  "commit"           │      OUTGOING     │ insight"            │          │
│   │  "search_files"     │                  │ "git.smart_commit"  │          │
│   └─────────────────────┘                  └─────────────────────┘          │
│                                                                              │
│   ┌─────────────────────┐                  ┌─────────────────────┐          │
│   │  "save_memory"      │ ◄─ call_tool ─── │ memory.remember_    │          │
│   │  (LLM calls this)   │      INCOMING    │ insight" (executed) │          │
│   └─────────────────────┘                  └─────────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Architecture Components

### 1. Configuration Layer (`assets/settings.yaml`)

```yaml
skills:
  overrides:
    # Case 1: Verb Simplification (High attention weight)
    memory.remember_insight:
      alias: "save_memory"
      append_doc: "\n\nCRITICAL: Use this to persist user preferences."

    # Case 2: Namespace Rename (Semantic correction)
    code_tools.replace_in_file:
      alias: "code.smart_edit"
      append_doc: "\n\nPreferred method for precise code modifications."

    # Case 3: Documentation-only (No alias)
    git.status:
      append_doc: "\n\nUse this for structured git status output."
```

### 2. Config Models (`omni/core/config/loader.py`)

```python
class CommandOverride(BaseModel):
    """Configuration for a specific command override."""
    alias: str | None = None      # Exposed name (LLM sees this)
    append_doc: str | None = None # Additional docs (injected into description)

class OverridesConfig(BaseModel):
    """Collection of command overrides."""
    commands: dict[str, CommandOverride] = {}

    @property
    def aliases(self) -> dict[str, str]:
        """Reverse lookup: alias -> canonical_name for incoming calls."""
        return {
            config.alias: cmd_name
            for cmd_name, config in self.commands.items()
            if config.alias
        }
```

### 3. Routing Tables (`omni/agent/mcp_server/server.py`)

```python
class AgentMCPServer:
    def __init__(self):
        # Alias -> Real Name (resolve incoming call_tool)
        self._alias_to_real: dict[str, str] = {}
        # Real Name -> Display Config (for outgoing list_tools)
        self._real_to_display: dict[str, dict] = {}

    def _build_routing_table(self):
        """Pre-compute routing tables from overrides config."""
        overrides = load_command_overrides()

        for real_name, config in overrides.commands.items():
            if config.alias:
                # Map 'save_memory' -> 'memory.remember_insight'
                self._alias_to_real[config.alias] = real_name

                # Store display metadata
                self._real_to_display[real_name] = {
                    "name": config.alias,
                    "append_doc": config.append_doc
                }
```

## Routing Logic

### Outgoing: `list_tools` (LLM sees tools)

```python
for cmd_name in commands:
    # 1. Check Filter
    if is_filtered(cmd_name):
        continue

    # 2. Apply Alias/Rename
    override = self._real_to_display.get(cmd_name, {})
    exposed_name = override.get("name", cmd_name)

    # 3. Inject append_doc
    base_desc = getattr(cmd, "description", "")
    if override.get("append_doc"):
        base_desc += override.get("append_doc")

    mcp_tools.append(Tool(name=exposed_name, description=base_desc, ...))
```

### Incoming: `call_tool` (Execute command)

```python
async def call_tool(name: str, arguments: dict) -> list[Any]:
    # 1. Resolve Alias: 'save_memory' -> 'memory.remember_insight'
    real_command = self._alias_to_real.get(name, name)

    if name != real_command:
        logger.debug(f"🔀 Route Alias: '{name}' -> '{real_command}'")

    # 2. Execute with canonical name
    result = await self._kernel.execute_tool(real_command, arguments, caller=None)
    return [TextContent(type="text", text=str(result))]
```

## Use Cases

### Use Case 1: Verb Simplification

**Goal**: Make tool names shorter and more verb-centric for LLM attention.

```yaml
# settings.yaml
skills:
  overrides:
    memory.remember_insight:
      alias: "save_memory"
      append_doc: "\n\nUse this to persist important context."
    memory.recall:
      alias: "search_memory"
      append_doc: "\n\nSemantic search across your project's memory."
```

**Result**:

- LLM sees: `save_memory`, `search_memory`
- Kernel executes: `memory.remember_insight`, `memory.recall`

### Use Case 2: Namespace Normalization

**Goal**: Align internal tool names with user mental models.

```yaml
# settings.yaml
skills:
  overrides:
    code_tools.replace_in_file:
      alias: "code.edit"
      append_doc: "\n\nAtomic file editing with backup."
    code_tools.ast_search:
      alias: "code.search"
      append_doc: "\n\nSearch code using AST patterns."
```

### Use Case 3: Command Grouping

**Goal**: Create logical groupings without code changes.

```yaml
# settings.yaml
skills:
  overrides:
    filesystem.read_files:
      alias: "read"
      append_doc: "\n\nSafe file reading with line numbering."
    filesystem.write_file:
      alias: "write"
      append_doc: "\n\nAtomic file writing."
```

## Configuration Options

### `alias`

The **exposed name** that LLM sees and calls.

| Value           | Effect                                                            |
| --------------- | ----------------------------------------------------------------- |
| `"save_memory"` | LLM sees `save_memory`, Kernel executes `memory.remember_insight` |
| `null`          | No alias, original name used                                      |

### `append_doc`

Additional documentation injected into the tool description.

| Feature                   | Behavior                     |
| ------------------------- | ---------------------------- |
| `"\\n\\nUse this for..."` | Appended to base description |
| `null`                    | No change to description     |

## Integration with Filtering

BAM works seamlessly with `filter_commands` for complete tool visibility control:

```yaml
skills:
  # Hide internal plumbing commands
  filter_commands:
    - "git.raw_*" # Hide all raw git commands
    - "!git.commit" # Exception: Keep smart commit

  overrides:
    git.smart_commit:
      alias: "commit" # Expose as simple verb
```

## Performance Considerations

1. **Pre-computed Routing Tables**: Routing tables are built once at server startup
2. **O(1) Lookups**: Alias resolution uses dictionary lookups, not iteration
3. **Singleton Pattern**: Configs are cached as singletons for repeated access

## Best Practices

1. **Naming Conventions**:
   - Use verb-first for aliases: `save_`, `search_`, `commit_`
   - Keep aliases under 20 characters for token efficiency

2. **Documentation**:
   - Always include `append_doc` for complex tools
   - Use `[CRITICAL]` prefix for frequently-needed tools

3. **Testing**:
   - Test both `list_tools` output and `call_tool` execution
   - Verify alias resolution for all overridden commands

## Example Walkthrough

### Configuration

```yaml
skills:
  preload: [git, memory, code_tools]
  overrides:
    memory.remember_insight:
      alias: "save_memory"
      append_doc: "\n\nCRITICAL: Persist user preferences."
```

### MCP Server Startup

```
1. load_command_overrides() reads config
2. _build_routing_table() creates:
   - _alias_to_real = {"save_memory": "memory.remember_insight"}
   - _real_to_display = {"memory.remember_insight": {"name": "save_memory", "append_doc": "..."}}
```

### LLM Interaction

**1. list_tools()** - LLM receives tool list:

```json
{
  "name": "save_memory",
  "description": "Execute memory.remember_insight\n\nCRITICAL: Persist user preferences.",
  "inputSchema": {...}
}
```

**2. LLM calls**:

```
@omni("save_memory", {"content": "User prefers Python over JavaScript"})
```

**3. call_tool()** - Alias resolution:

```python
real_command = _alias_to_real.get("save_memory")  # "memory.remember_insight"
result = await kernel.execute_tool("memory.remember_insight", {...})
```

## Files Reference

| File                              | Purpose                                                          |
| --------------------------------- | ---------------------------------------------------------------- |
| `omni/core/config/loader.py`      | Config models (`CommandOverride`, `OverridesConfig`) and loaders |
| `omni/agent/mcp_server/server.py` | MCP Server with routing tables and alias resolution              |
| `assets/settings.yaml`            | Runtime configuration for aliases and overrides                  |
| `test_config_loader.py`           | Unit tests for BAM functionality                                 |

## Related Patterns

- **Configuration over Convention**: All naming changes via YAML, no code required
- **Gateway Pattern**: MCP Server acts as gateway between LLM and Kernel
- **Bi-directional Mapping**: Outgoing (display) and incoming (execution) routing
