# System Layering Architecture (Trinity System Layers)

> **Status**: Active | **Version**: v4.0
> **Philosophy**: "Thin Agent, Fat Kernel, Rust Foundation"
> **Current Agent Persona**: [Omega Architecture](../human/architecture/omega-architecture.md)

The system is organized into **four strict software layers**, referred to as the **Trinity System Layers**. This structure ensures high performance, clear separation of concerns, and massive scalability.

## 🏗️ Layer 1: Foundation (The Bedrock)

**Responsibility**: I/O, Performance, Macros, Type System.

- **Implementation**: `packages/python/foundation/`
- **Key Features**: Orjson-powered serialization, `@skill_command` decorators, Pydantic V2 schemas.

## 🧠 Layer 2: Core (The Kernel)

**Responsibility**: Business Logic, State Management, Skill Loading.

- **Implementation**: `packages/python/core/`
- **Key Features**: `Kernel` singleton, `ScriptLoader`, `Router & Sniffer`.

## 🔌 Layer 3: MCP-Server (The Transport)

**Responsibility**: Protocol Implementation, Transport Layer.

- **Implementation**: `packages/python/mcp-server/`
- **Key Features**: JSON-RPC over STDIO/SSE, high-performance serialization.

## 🎯 Layer 4: Agent (The Interface)

**Responsibility**: Protocol Adaptation, User Interaction, CLI Entry Points.

- **Implementation**: `packages/python/agent/`
- **Key Features**: `OmniLoop`, `OmegaRunner`, CLI commands.

---

## Architecture Evolution: Roles vs Layers

It is important to distinguish between **Agent Roles** (How the agent thinks) and **System Layers** (How the code is structured).

| Concept           | Previous (v1.0)                               | Current (v3.0+)                                          |
| :---------------- | :-------------------------------------------- | :------------------------------------------------------- |
| **Agent Roles**   | Trinity Roles (Orchestrator, Coder, Executor) | **Omega Architecture** (Cortex, Cerebellum, Hippocampus) |
| **System Layers** | Flat structure                                | **Trinity System Layers** (Foundation, Core, MCP, Agent) |

The **Omega Architecture** sits on top of the **Trinity System Layers** to provide an autonomous, self-evolving agent experience.

### Script Loader Integration

```python
from omni.core.skills.script_loader import ScriptLoader
from omni.foundation.api.decorators import get_script_config

loader = ScriptLoader(scripts_path="assets/skills/git/scripts", skill_name="git")
loader.load_all()

# Commands are automatically registered from @skill_command decorators
for cmd in loader.commands.values():
    config = get_script_config(cmd)  # Reads V2 config
    print(f"{cmd.__name__}: {config['category']}")
```

### Event Reactor (v5.0 - The Grand Integration)

The Kernel integrates with the Rust Event Bus for reactive architecture:

```python
# In Kernel._on_ready()
from omni.core.kernel.reactor import get_reactor, EventTopic

# Initialize reactor
self._reactor = get_reactor()

# Wire Cortex to file events (auto-increment indexing)
self._reactor.register_handler(
    EventTopic.FILE_CHANGED,
    self._on_file_changed_cortex,
    priority=10
)

# Wire Sniffer to file events (reactive context detection)
self.sniffer.register_to_reactor()

# Start consumer loop
await self._reactor.start()
```

---

## 🔌 Layer 3: MCP-Server (The Transport)

**Responsibility:** Protocol Implementation, Transport Layer.

### Key Components

| Component          | Purpose                                  |
| ------------------ | ---------------------------------------- |
| **JSON-RPC Types** | Inherit from Foundation `OrjsonModel`    |
| **StdioTransport** | orjson-powered stdin/stdout (zero-copy)  |
| **SSEServer**      | orjson-powered HTTP streaming            |
| **stdio_server()** | MCP SDK-compatible async context manager |

### MCP Types (Inherit from Foundation)

```python
from omni.mcp.types import JSONRPCRequest, JSONRPCResponse
from omni.foundation.api.types import OrjsonModel

# All types inherit OrjsonModel for 10x faster serialization
assert issubclass(JSONRPCRequest, OrjsonModel)
assert issubclass(JSONRPCResponse, OrjsonModel)

# Direct orjson output
request = JSONRPCRequest(method="tools/list", params={})
json_bytes = request.model_dump_json_bytes()  # Ultra-fast!
```

### STDIO Transport (MCP SDK Compatible)

```python
from omni.mcp.transport.stdio import stdio_server

# MCP SDK-compatible API
async with stdio_server() as (read_stream, write_stream):
    await server.run(read_stream, write_stream, init_options)
```

---

## 🎯 Layer 4: Agent (The Interface)

**Responsibility:** Protocol Adaptation (MCP), User Interaction, CLI Entry Points.

### Key Components

| Component            | Purpose                                          |
| -------------------- | ------------------------------------------------ |
| **mcp_server.stdio** | Uses `omni.mcp.transport.stdio.stdio_server`     |
| **mcp_server.sse**   | Uses `omni.mcp.transport.sse.SseServerTransport` |
| **CLI**              | Command-line entry points                        |

### Agent Integration

```python
# packages/python/agent/src/omni/agent/mcp_server/stdio.py
from omni.mcp.transport.stdio import stdio_server

async def run_stdio() -> None:
    """Run server in stdio mode for Claude Desktop."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, get_init_options())
```

---

## 📁 Directory Structure

```
omni-dev-fusion/
├── packages/
│   ├── python/
│   │   ├── foundation/          # Layer 1: Foundation (I/O, protocols, macros)
│   │   │   └── omni/foundation/
│   │   │       ├── api/
│   │   │       │   ├── decorators.py    # @skill_command macro
│   │   │       │   └── types.py         # OrjsonModel, CommandResult[T]
│   │   │       └── config/              # Settings, logging, paths
│   │   │
│   │   ├── core/                # Layer 2: Core (Kernel, Skills)
│   │   │   └── omni/core/
│   │   │       ├── kernel/      # Kernel singleton, lifecycle
│   │   │       ├── skills/      # ScriptLoader, extensions
│   │   │       └── router/      # Router & Sniffer
│   │   │
│   │   ├── mcp-server/          # Layer 3: MCP Transport
│   │   │   └── omni/mcp/
│   │   │       ├── types.py     # JSON-RPC types (inherits OrjsonModel)
│   │   │       ├── server.py    # MCPServer orchestration
│   │   │       └── transport/   # StdioTransport, SSEServer, stdio_server()
│   │   │
│   │   └── agent/               # Layer 4: Agent (Thin adapter)
│   │       └── omni/agent/
│   │           ├── mcp_server/  # Uses omni.mcp.transport
│   │           ├── cli/         # CLI entry points
│   │           └── core/        # Layer 5: Context Optimization (Token Diet)
│   │               └── context/ # ContextPruner, ContextManager, Turn
│   │
│   └── rust/
│       └── crates/
│           ├── omni-core-rs/    # Rust core (bindings)
│           └── omni-scanner/    # Rust index generator
│
├── assets/
│   └── skills/                  # Skill definitions
│       ├── git/
│       │   ├── SKILL.md
│       │   ├── rules.toml       # Declarative sniffer rules
│       │   ├── scripts/         # @skill_command decorated functions
│       │   └── extensions/      # Skill extensions
│       └── ...
│
├── skill_index.json             # Single Source of Truth (generated by Rust)
└── pyproject.toml               # Project config
```

---

## 🚀 Performance Characteristics

### Serialization Benchmarks

| Operation             | Standard json | orjson | Speedup  |
| --------------------- | ------------- | ------ | -------- |
| `model_dump()`        | ~62ms         | ~35ms  | **1.8x** |
| Complex nested data   | ~120ms        | ~40ms  | **3x**   |
| MCP message roundtrip | ~200ms        | ~50ms  | **4x**   |

### Memory Efficiency

- **Zero-copy reading**: StdioTransport reads directly from `stdin.buffer`
- **Binary output**: orjson.dumps returns `bytes` (no encoding overhead)
- **Compact serialization**: orjson produces smaller JSON output

---

## 🔄 Data Flow: The Complete Stack

### Build Time

```
Rust Scanner → assets/skills/ → skill_index.json
```

### Boot Time

```
1. Agent starts → Boots Kernel
2. Kernel initializes DiscoveryService → Reads skill_index.json (O(1))
3. Kernel initializes IntentSniffer → Loads rules from Index
4. Kernel loads ScriptLoader for each skill
   └── ScriptLoader reads _skill_config from @skill_command decorators
```

### Run Time (Complete Stack)

```
┌─────────────────────────────────────────────────────────────────┐
│ L4: Agent (Claude Desktop / Claude Code CLI)                    │
│  stdin/stdout ◄────── JSON-RPC Messages ──────►                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ L3: MCP-Server (omni.mcp.transport)                             │
│  stdio_server() [orjson.loads/dumps]                            │
│  SSEServer [orjson-powered streaming]                           │
│  JSON-RPC Types (OrjsonModel)                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ L2: Core (omni.core)                                            │
│  ScriptLoader reads _skill_config from @skill_command           │
│  Kernel orchestrates skill execution                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  | KernelReactor (Event-Driven Architecture v5.0)             |  │
│  |                                                            |  │
│  |  Rust GLOBAL_BUS ──► KernelReactor ──► Handlers            |  │
│  |  (tokio broadcast)    (async loop)     Cortex/Sniffer      |  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ L1: Foundation (omni.foundation)                                │
│  @skill_command generates input_schema (Pydantic V2)            │
│  CommandResult[T] with @computed_field                          │
│  OrjsonModel for 10x fast serialization                         │
└─────────────────────────────────────────────────────────────────┘

### Event Flow (v5.0 - The Grand Integration)

```

File Watcher (Rust) Agent Loop (Python) Sniffer (Python)
│ │ │
▼ ▼ │
GLOBAL_BUS.publish GLOBAL_BUS.publish KernelReactor
(file/changed) (agent/step_complete) (FILE_CREATED)
│ │ │
└───────────────────────────┼─────────────────────────────┘
│
▼
┌────────────────────┐
│ KernelReactor │
│ (async consumer) │
└─────────┬──────────┘
│
┌────────────────────────┼────────────────────────┐
│ │ │
▼ ▼ ▼
\_on_file_changed_cortex AsyncPersistenceService \_on_file_changed
│ │ │
▼ ▼ ▼
Indexer.index_file() Queue → Worker → Store sniff(parent_dir)

```

### MCP Message Flow (STDIO)

```

stdin.buffer (bytes)
↓
orjson.loads() ← L3: omni.mcp.transport.stdio.stdio_server
↓
JSON-RPC Request
↓
L4: agent.mcp_server.stdio.run_stdio()
↓
L3: MCPServer.run()
↓
L2: ScriptLoader.get_command("git.status")
↓
L1: @skill_command decorated function executes
↓
Returns CommandResult[T] (inherits OrjsonModel)
↓
orjson.dumps() ← L3: omni.mcp.transport.stdio
↓
stdout.buffer (bytes)

````

---

## 🎯 Key Components

### Foundation Decorators

```python
from omni.foundation.api import skill_command, get_script_config

@skill_command(
    name="git_status",
    category="read",
    inject_root=True,
    cache_ttl=60.0
)
def status(project_root: Path) -> CommandResult[dict]:
    """Get git status."""
    ...

# Config is auto-generated at decoration time
config = get_script_config(status)
# {
#     "name": "git_status",
#     "category": "read",
#     "input_schema": {...},  # Pydantic V2 generated
#     "execution": {...}
# }
````

### Kernel (`omni.core.kernel`)

```python
from omni.core.kernel import get_kernel

kernel = get_kernel()
await kernel.initialize()
await kernel.start()

context = kernel.skill_context
skills = context.list_skills()
```

### ScriptLoader

```python
from omni.core.skills.script_loader import ScriptLoader

loader = ScriptLoader(
    scripts_path="assets/skills/git/scripts",
    skill_name="git"
)
loader.load_all()

# Commands are auto-registered from @skill_command decorators
cmd = loader.commands["git.status"]
```

### Intent Sniffer (`omni.core.router.sniffer`)

```python
from omni.core.router.sniffer import IntentSniffer

sniffer = IntentSniffer()
sniffer.load_from_index()  # Load rules from skill_index.json
skills = sniffer.sniff("/project")  # Returns matching skill names
```

---

## 📜 Sniffer Rules (rules.toml)

Skills define activation rules in `extensions/sniffer/rules.toml`:

```toml
[[rule]]
skill = "python"
type = "file_exists"
pattern = "pyproject.toml"

[[rule]]
skill = "python"
type = "file_pattern"
pattern = "*.py"

[[rule]]
skill = "git"
type = "file_exists"
pattern = ".git"
```

---

## 🔥 Hot Reload Workflow

1. **Watcher:** Kernel watches `skill_index.json` and `scripts/*.py`
2. **Update:** Developer modifies skill script
3. **Signal:** Kernel detects file change → reloads ScriptLoader
4. **Notification:** Agent sends `notifications/tools/list_changed`
5. **Refresh:** Client re-fetches tools list

---

## Migration Checklist (v2.0 → v4.0)

| Old Pattern                | New Pattern                                          |
| -------------------------- | ---------------------------------------------------- |
| Manual `input_schema` dict | Auto-generated by `@skill_command`                   |
| `json.dumps()`             | `OrjsonModel.model_dump_json_bytes()`                |
| `mcp.server.stdio`         | `omni.mcp.transport.stdio.stdio_server`              |
| `mcp.server.sse`           | `omni.mcp.transport.sse.SseServerTransport`          |
| Pydantic V1                | Pydantic V2 (`model_json_schema`, `@computed_field`) |
| Dataclass                  | `OrjsonModel` base class                             |
| `agent.skills.*`           | `omni.core.skills.script_loader`                     |
| Raw message list           | `ContextManager` with smart pruning                  |

---

## 🎯 Context Optimization (The Token Diet)

**Philosophy**: "Keep what matters, prune what doesn't."

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ L4: Agent (omni_loop.py)                                        │
│  ContextManager.get_active_context(strategy="pruned")          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ L5: Context Optimization (NEW - Token Diet)                     │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐ │
│  │ ContextPruner  │    │ ContextManager │    │ Turn Tracking  │ │
│  │ - System Keep  │    │ - add_turn()   │    │ - Snapshot     │ │
│  │ - Recent Keep  │    │ - get_context()│    │ - Stats        │ │
│  │ - Overflow     │    │ - prune()      │    │ - Serialization│ │
│  │ - Segment      │    │ - compress()   │    │ - Summary      │ │
│  └────────────────┘    └────────────────┘    └────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ L3: MCP-Server (omni.mcp.transport)                             │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

```python
# packages/python/agent/src/omni/agent/core/context/

from .pruner import ContextPruner, PruningConfig
from .manager import ContextManager

# Initialize with token budget
config = PruningConfig(max_tokens=128000, retained_turns=10)
ctx = ContextManager(pruner=ContextPruner(config))

# Add conversation turns
ctx.add_turn("User message", "Assistant response")

# Get pruned context for LLM
messages = ctx.get_active_context(strategy="pruned")

# Stats
stats = ctx.stats()
# {'turn_count': 1, 'total_messages': 3, 'estimated_tokens': ~150, ...}
```

### Pruning Strategy (The "Token Diet")

| Layer        | Priority | Action                             |
| ------------ | -------- | ---------------------------------- |
| **System**   | CRITICAL | Always preserved (identity, tools) |
| **Recent**   | HIGH     | Last N turns kept intact           |
| **Summary**  | MEDIUM   | Optional insertion point           |
| **Overflow** | LOW      | Truncated from oldest              |

### Smart Context Compression

When conversation history exceeds limits, instead of discarding old messages, the system can semantically compress them:

```python
from omni.agent.core.context import ContextManager

ctx = ContextManager()

# Segment messages into 3 parts
system, to_summarize, recent = ctx.segment()

# Async compression with NoteTaker integration
await ctx.compress()  # Returns True if compression occurred

# Summary is stored and reused
print(ctx.summary)  # Persisted summary text

# Summary is included in context
messages = ctx.get_active_context(strategy="pruned")
# System messages + [Context Summary] + Recent messages
```

**Compression Flow:**

1. `segment()` splits messages into (system, to_summarize, recent)
2. `compress()` formats old messages into trajectory structure
3. Calls NoteTaker `summarize()` to generate markdown summary
4. Extracts key content and stores in `self.summary`
5. Old messages replaced with summary in system prompts

**Fallback:** If NoteTaker unavailable, uses simple extractive summarization.

### Related Files

**Python (Context Layer):**

- `packages/python/agent/src/omni/agent/core/context/pruner.py`
- `packages/python/agent/src/omni/agent/core/context/manager.py`
- `packages/python/agent/src/omni/agent/core/omni.py`
- `packages/python/agent/tests/unit/test_context/`

---

## 📚 Related Documentation

### Architecture Guides

- [Zero-Code Skill Architecture](./zero-code-skill-architecture.md)
- [MCP Core Architecture](../developer/mcp-core-architecture.md)
- [Hippocampus](../human/architecture/hippocampus.md) - Memory Interface (long-term memory)

### Feature Guides

- [MCP Transport Layer](./mcp-transport.md)
- [Script Loader](./script-loader.md)
- [Context Optimization (Token Diet)](./context-optimization.md)
- [Vector Index Optimization](./vector-index.md)
- [Rust-Python Bridge](./rust-python-bridge.md)
- [Permission Gatekeeper (Zero Trust)](./permission-gatekeeper.md)
- [Immune System](./immune-system.md)

### Reference

- [ODF-EP Protocol](../reference/odf-ep-protocol.md)
- [Extension System](../reference/extension-system.md)
