# Trinity Architecture (Phase 36)

> **Phase 36: Trinity v2.0 - Swarm Engine + Skills**
> **Core Philosophy**: "Everything is a Skill" - The Executor is no longer a code module, but a logical role played by atomic skills.

## Quick Reference

| Phase | Key Change                                                                                                 |
| ----- | ---------------------------------------------------------------------------------------------------------- |
| 36    | **Trinity v2.0**: Legacy `mcp_core.execution` deleted. Execution now via `skills/terminal` + Swarm Engine. |
| 35.3  | Pure MCP Server (mcp.server.Server, no FastMCP)                                                            |
| 35.2  | Sidecar Execution Pattern (uv isolation for crawl4ai, etc.)                                                |
| 35.1  | Zero-configuration test framework (pytest plugin)                                                          |
| 34    | Cognitive system (CommandResult, StateCheckpointer)                                                        |
| 33    | SKILL.md unified format                                                                                    |

## Trinity v2.0 Overview

The Trinity Architecture unifies three critical concerns through a **Skill-Centric** design. The key insight: **Execution is a Skill, not a module.**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Trinity v2.0 Architecture                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User (Claude Desktop/Code)                                                 │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────┐                                                        │
│  │  MCP Gateway    │  (Pure MCP Server - Protocol Adapter Only)              │
│  │  mcp_server.py  │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────┐                                                        │
│  │ 🧠 Swarm Engine │  (Runtime Orchestrator - Dispatch & Isolation)          │
│  │                 │                                                        │
│  │  • Route calls  │                                                        │
│  │  • Isolate deps │                                                        │
│  │  • Handle errors│                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                  │
│           ▼                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    THE TRINITY ROLES (Cognitive Layer)                 │  │
│  │                                                                       │  │
│  │  🧠 Orchestrator      📝 Coder              🛠️ Executor               │  │
│  │  (Planning &          (Reading &            (Execution &              │  │
│  │   Strategy)            Writing)              Operations)              │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    THE MUSCLE LAYER (Skill Runtime)                    │  │
│  │                                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │  │
│  │  │   Terminal  │  │     Git     │  │  Filesystem │  │  Knowledge  │   │  │
│  │  │   Skill     │  │   Skill     │  │   Skill     │  │   Skill     │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │  │
│  │         │                │                │                │          │  │
│  │         ▼                ▼                ▼                ▼          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │  │
│  │  │subprocess   │  │  git CLI    │  │  safe I/O   │  │  RAG/LLM    │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## The Trinity Roles (v2.0)

### 🧠 Orchestrator (The Brain)

**Purpose**: Planning, routing, and strategy.

**Implementation**:

- `skills/knowledge` - Development context, rules, standards
- `skills/skill` - Skill discovery, management, JIT installation

**Usage**: `@omni("knowledge.get_development_context")` to understand project rules.

### 📝 Coder (The Pen)

**Purpose**: Reading and writing code/files.

**Implementation**:

- `skills/filesystem` - Safe file operations (read, write, search)
- `skills/code_insight` - AST analysis, code structure
- `skills/file_ops` - Advanced file operations, AST refactoring

**Usage**: `@omni("filesystem.read_file", {"path": "README.md"})`

### 🛠️ Executor (The Hands)

**Purpose**: Running commands and operations.

**Implementation**:

- `skills/terminal` - Shell command execution (replaces legacy `SafeExecutor`)
- `skills/git` - Version control operations
- `skills/testing` - Test execution

**Usage**: `@omni("terminal.execute_command", {"command": "ls", "args": ["-la"]})`

> **Key Change**: The Executor is NO LONGER a Python class. It's a logical role fulfilled by `skills/terminal/tools.py`. This skill contains `SafeExecutor` logic directly, enabling hot-reload and sandboxing without core code changes.

## Execution Model Evolution

| Aspect             | Legacy (Phase 29)                              | Current (Phase 36)                                             |
| ------------------ | ---------------------------------------------- | -------------------------------------------------------------- |
| **Execution Path** | MCP → `common.mcp_core.execution` → subprocess | MCP → `Swarm.execute_skill()` → `skills/terminal` → subprocess |
| **Executor Type**  | Python class (`SafeExecutor`)                  | Atomic Skill (`skills/terminal`)                               |
| **Security**       | Code-level checks                              | Skill isolation + checks                                       |
| **Hot-Reload**     | N/A                                            | Yes (skill files are hot-reloadable)                           |
| **Sandboxing**     | Limited                                        | Full isolation via sidecar or Docker                           |

## Migration from Legacy Execution

### Before (Deprecated)

```python
# Old code - DO NOT USE
from common.mcp_core.execution import SafeExecutor

executor = SafeExecutor()
result = await executor.run("ls", ["-la"])
```

### After (Current)

```python
# New approach - Use the terminal skill via MCP
@omni("terminal.execute_command", {"command": "ls", "args": ["-la"]})

# Or directly via Swarm Engine
from agent.core.swarm import get_swarm

result = await get_swarm().execute_skill(
    skill_name="terminal",
    command="execute_command",
    args={"command": "ls", "args": ["-la"]}
)
```

## Why This Change?

1. **Security**: Terminal skill can be sandboxed, disabled, or routed through Docker without changing core code.
2. **Consistency**: Running a command is identical to running a search - everything is a Skill.
3. **Observability**: Swarm Engine provides unified logging, timeout, and error handling.
4. **Hot-Reload**: Modify execution logic without restarting the server.
5. **Testability**: Skills can be mocked at the skill level, not just the function level.

## Key Components

### Swarm Engine (`agent/core/swarm.py`)

```python
class Swarm:
    async def execute_skill(
        self,
        skill_name: str,
        command: str,
        args: dict,
        mode: str = "direct",  # "direct", "sidecar_process", "docker"
        timeout: int = 60,
    ) -> dict:
        """Execute a skill command with optional isolation."""
        ...
```

### Terminal Skill (`assets/skills/terminal/tools.py`)

```python
@skill_command(
    name="execute_command",
    category="workflow",
    description="Execute a shell command with whitelist validation.",
)
async def execute_command(command: str, args: list[str] = None, timeout: int = 60) -> str:
    """Terminal skill - The new 'Executor' implementation."""
    is_safe, error_msg = check_dangerous_patterns(command, args)
    if not is_safe:
        return f"Blocked: {error_msg}"

    result = await SafeExecutor.run(command, args, timeout)
    return SafeExecutor.format_result(result, command, args)
```

## File Structure (Phase 36)

```
packages/python/agent/src/agent/
├── core/
│   ├── swarm.py              # 🧠 Runtime orchestrator (Phase 36)
│   ├── module_loader.py      # Hot-reload mechanism
│   └── skill_manager.py      # Trinity facade
├── mcp_server.py             # Pure MCP Server (Thin Gateway)
└── skills/
    └── decorators.py         # @skill_command decorator

assets/skills/
├── terminal/                 # 🛠️ Executor implementation
│   ├── tools.py              # Command execution interface
│   ├── scripts/              # Atomic implementations
│   └── SKILL.md              # Skill manifest
├── git/                      # Version control
│   └── tools.py              # Git operations
├── filesystem/               # File operations
│   └── tools.py              # Safe I/O operations
└── <other-skills>/           # Additional capabilities

packages/python/common/src/common/
├── mcp_core/                 # Protocol definitions (NO execution)
│   ├── protocols.py          # ISkill, ISkillCommand
│   └── __init__.py           # Shared types
└── config/
    └── settings.py           # Configuration

# LEGACY - DELETED (Phase 36)
# packages/python/common/src/common/mcp_core/execution/  ❌ REMOVED
```

---

# v2.0 Summary

## Trinity v2.0 Key Points

1. **Executor is a Skill, Not a Module**: The legacy `mcp_core.execution` module has been deleted. Execution is now handled by `skills/terminal`.

2. **Swarm Engine**: New runtime orchestrator that dispatches skill commands and handles isolation/sandboxing.

3. **Config-Driven Aliases**: Tool names can be configured in `settings.yaml:skills.overrides` for "Configuration over Convention".

4. **90+ Tools Registered**: All skills follow `skill.command` naming convention.

## Quick Reference

| Component       | Location               | Purpose               |
| --------------- | ---------------------- | --------------------- |
| MCP Gateway     | `mcp_server.py`        | Protocol adapter      |
| Swarm Engine    | `agent/core/swarm.py`  | Runtime orchestration |
| Executor Role   | `skills/terminal`      | Command execution     |
| Skill Decorator | `skills/decorators.py` | `@skill_command`      |

## Next Steps

- See `docs/skills.md` for skill implementation guide
- See `docs/reference/odf-ep-protocol.md` for engineering rules

---

# Legacy Content (Phase 29-35)

> The following content is kept for historical reference. Current implementation is Trinity v2.0 (Phase 36).

## Overview

The Trinity Architecture unifies three critical concerns in a single skill management system, enabling millisecond response times while providing deep context understanding for AI agents.

## The Three Pillars

```
┌─────────────────────────────────────────────────────────────┐
│                    SkillManager (Facade)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    Code     │  │   Context   │  │       State         │  │
│  │ (Hot-Load)  │  │ (Repomix)   │  │     (Registry)      │  │
│  │ ModuleLoader│  │ RepomixCache│  │  Protocol-based     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1. Code (Hot-Reloading)

**Purpose**: Execute skill commands with minimal overhead.

**Mechanism**: `ModuleLoader` + mtime-based lazy reload.

```python
from agent.core.module_loader import ModuleLoader

loader = ModuleLoader(skills_dir)
loader._ensure_parent_packages()
loader._preload_decorators()
module = loader.load_module(module_name, file_path, reload=True)
```

**Performance**: <1ms when files unchanged (no I/O, no import overhead).

**Trigger**: File modification on disk detected via `mtime` comparison.

### 2. Context (RepomixCache)

**Purpose**: Provide deep skill understanding for LLM context.

**Output**: XML-packed skill context including code, docs, and configuration.

**Caching**: Each skill has its own `RepomixCache` instance.

```python
@dataclass(slots=True)
class Skill(ISkill):
    name: str
    manifest: SkillManifest
    commands: dict[str, SkillCommand]
    # Trinity: Context Cache for deep skill understanding
    context_cache: RepomixCache | None = None
```

**Cache Location**: `.cache/<project>/skill_<name>_repomix.xml`

**Example**:

```
.cache/
└── omni-devenv-fusion/
    └── skill_git_repomix.xml  (20KB, includes tools.py, Backlog.md, workflows)
```

**Usage**: `@omni("git.help")` returns XML-packed skill context.

### 3. State (Protocol-based Registry)

**Purpose**: Maintain skill metadata and command registry.

**Structure**: Protocol-based design for testability.

```python
@runtime_checkable
class ISkill(Protocol):
    @property
    @abstractmethod
    def name(self) -> str: ...
    @property
    @abstractmethod
    def commands(self) -> dict[str, ISkillCommand]: ...

@dataclass(slots=True)
class SkillCommand(ISkillCommand):
    name: str
    func: Callable[..., Any]
    description: str = ""
    category: SkillCategory = SkillCategory.GENERAL
```

**Persistence**: In-memory, survives across command calls.

**Discovery**: Auto-scans `assets/skills/*/tools.py` at startup.

## Hot-Reload Flow

```
User: @omni("git.status")
     │
     ▼
get_skill_manager().run("git", "git_status")
     │
     ▼
_ensure_fresh("git") ──→ Check mtime
     │
     ├── Unchanged ──→ Return cached command (<1ms)
     │
     └── Changed ──→ ModuleLoader.reload()
     │               Update Skill.mtime
     │               Update Skill.commands
     │
     ▼
Execute command function
```

## Key Performance Characteristics

| Scenario                    | Time       | Reason                          |
| --------------------------- | ---------- | ------------------------------- |
| First command (cold)        | ~10-50ms   | Module load, command extraction |
| Subsequent (no change)      | <1ms       | Memory direct call              |
| After file modification     | ~10-50ms   | ModuleLoader.reload()           |
| First `@omni("skill.help")` | ~100-500ms | Repomix execution               |
| Subsequent help calls       | <1ms       | Cache read                      |

## File Structure (Phase 35.2)

```
packages/python/agent/src/agent/core/
├── registry/              # Modular skill registry (Phase 29)
│   ├── __init__.py       # Unified exports + get_skill_tools()
│   ├── core.py           # SkillRegistry (singleton, discovery)
│   ├── loader.py         # SkillLoader (spec-based loading)
│   ├── context.py        # ContextBuilder (guide + prompts)
│   ├── installer.py      # RemoteInstaller (Git-based)
│   ├── resolver.py       # VersionResolver (multi-strategy)
│   └── jit.py            # JIT skill acquisition
├── protocols.py           # ISkill, ISkillCommand protocols
├── module_loader.py       # Clean hot-reload (no sys.modules pollution)
└── skill_manager.py       # Trinity facade for @omni routing

packages/python/common/src/common/
├── isolation.py           # Sidecar Execution Pattern (Phase 35.2)
├── lazy_cache.py          # RepomixCache class
└── skills_path.py         # Skills directory resolution

.cache/
└── <project>/
    └── skill_<name>_repomix.xml  # Cached contexts

assets/skills/<skill>/
├── SKILL.md              # Skill manifest + rules (definition file)
├── tools.py              # Skill interface (lightweight)
├── README.md             # Reference docs
├── scripts/              # Atomic implementations (Phase 35.2)
│   └── *.py              # Heavy imports allowed here
├── pyproject.toml        # Skill dependencies (for subprocess mode)
└── repomix.json          # Atomic context config (optional)
```

## Phase 25 → Phase 29 Evolution

| Aspect                 | Phase 25.3                 | Phase 35.3                                            |
| ---------------------- | -------------------------- | ----------------------------------------------------- |
| **Architecture**       | Trinity                    | Trinity + Protocols + Pure MCP Server                 |
| **MCP Server**         | FastMCP                    | `mcp.server.Server` (no FastMCP)                      |
| **Registry**           | Monolithic (887 lines)     | Modular (6 files, ~676 lines)                         |
| **Code Loading**       | `sys.modules` manipulation | `ModuleLoader` context manager                        |
| **State Management**   | Dict-based                 | Protocol-based (ISkill, ISkillCommand)                |
| **Data Classes**       | Standard dataclass         | `@dataclass(slots=True)`                              |
| **Skill Structure**    | `tools.py` only            | `tools.py` + `scripts/` (atomic implementations)      |
| **Heavy Dependencies** | N/A                        | Sidecar Pattern (uv isolation via `common.isolation`) |
| **Performance**        | Standard asyncio           | uvloop (SSE) + orjson                                 |
| **Testing**            | Manual fixtures            | Zero-config pytest plugin (auto-discovers fixtures)   |

## Phase 35.2: Sidecar Execution Pattern

For skills with heavy dependencies (e.g., `crawl4ai`, `playwright`), use the **Sidecar Execution Pattern**:

```
┌─────────────────────────────────────────────────────────────┐
│                    Omni Core (Main Agent)                   │
│                                                             │
│  tools.py (lightweight) ──────┐                             │
│  - imports only from common   │                             │
│  - no heavy dependencies      │                             │
│                              ↓                              │
│                      uv run --directory skill/              │
│                      python scripts/engine.py               │
│                              ↓                              │
│              ┌──────────────────────────────┐               │
│              │    Skill Isolated Env        │               │
│              │    (Independent .venv)       │               │
│              │                              │               │
│              │  scripts/engine.py           │               │
│              │  - crawl4ai                  │               │
│              │  - playwright                 │               │
│              └──────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### Example: crawl4ai Skill

```
assets/skills/crawl4ai/
├── pyproject.toml        # Skill dependencies (crawl4ai, fire, pydantic)
├── tools.py              # Lightweight interface (uses common.isolation)
├── scripts/
│   └── engine.py         # Heavy implementation (imports crawl4ai)
└── SKILL.md              # Skill documentation + rules
```

**tools.py** (lightweight):

```python
from common.isolation import run_skill_script

@skill_command
def crawl_webpage(url: str):
    return run_skill_script(
        skill_dir=Path(__file__).parent,
        script_name="engine.py",
        args={"url": url},
    )
```

**scripts/engine.py** (heavy):

```python
from crawl4ai import AsyncWebCrawler

async def crawl(url: str):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        print(json.dumps({"success": result.success, "markdown": result.markdown}))
```

### Benefits

1. **Zero Pollution**: Main agent doesn't install heavy dependencies
2. **Version Isolation**: Each skill can use different library versions
3. **Hot Swappable**: Add/remove skills without restarting
4. **Security**: Limited blast radius for compromised code

## Integration Points

### With Pure MCP Server (`mcp_server.py`, Phase 35.3)

```python
from mcp.server import Server
from agent.core.skill_manager import get_skill_manager

# Create pure MCP Server (no FastMCP)
server = Server("omni-agent")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Dynamic tool discovery from SkillManager."""
    manager = get_skill_manager()
    tools = []
    for skill_name in manager.list_loaded():
        for cmd_name in manager.get_commands(skill_name):
            tools.append(Tool(
                name=f"{skill_name}.{cmd_name}",
                description=...
            ))
    return tools

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute via SkillManager."""
    manager = get_skill_manager()
    skill_name, cmd_name = name.split(".", 1)
    result = await manager.run(skill_name, cmd_name, arguments)
    return [TextContent(type="text", text=result)]
```

### With Skill Registry (`agent/core/registry/`)

```python
from agent.core.registry import SkillRegistry, get_skill_registry

registry = get_skill_registry()
skills = registry.list_available_skills()
manifest = registry.get_skill_manifest("git")
```

### With Repomix

Each skill can optionally define `repomix.json` for atomic context:

```json
{
  "output": { "style": "xml", "fileSummary": true },
  "include": ["SKILL.md", "tools.py", "README.md", "*.md"],
  "ignore": { "patterns": ["**/__pycache__/**"], "characters": [] }
}
```

Without `repomix.json`, dynamic config is generated with defaults.

## Best Practices

1. **Hot-Reload is Transparent**: Don't worry about reloads; they're automatic.

2. **Use `@omni("skill.help")`** for deep understanding of a skill's capabilities.

3. **Keep `tools.py` Focused**: Smaller files load faster on modification.

4. **Add `repomix.json`** for precise control over context inclusion.

5. **Use Protocols for Testing**: Mock skills with `ISkill` protocol for unit tests.

## Troubleshooting

| Issue                        | Solution                                                         |
| ---------------------------- | ---------------------------------------------------------------- |
| Command not found after edit | Wait for reload or call `manager.reload(skill_name)`             |
| Help returns old context     | Delete `.cache/<project>/*.xml` or call `context_cache.reload()` |
| Slow first command           | Normal - cold start requires module load                         |

---

## Production Validation (Phase 29)

The Trinity architecture has been validated under extreme stress conditions.

### Stress Test Results

| Metric              | Result    | Target                            |
| ------------------- | --------- | --------------------------------- |
| Duration            | ~5s       | 5s                                |
| Skill Modifications | 31+       | Chaos Monkey (50-200ms intervals) |
| Skill Invocations   | 966+      | Concurrent requests               |
| Failed Requests     | **0**     | 0                                 |
| Race Conditions     | 0         | <5 acceptable                     |
| Avg Context Time    | 109ms     | <500ms                            |
| Throughput          | 190 req/s | -                                 |

### Test Scenarios Covered

1. **Chaos Monkey**: Rapid file modifications (50-200ms intervals) simulating active IDE editing
2. **Spammer**: High concurrency requests (1-5 batch, 10ms intervals) during file writes
3. **Context Loader**: Repomix performance under load (10 consecutive help calls)

### Key Findings

- **Hot-Reload is Rock Solid**: 31+ file modifications during test, zero crashes
- **No Race Conditions**: 966+ concurrent requests during file writes, all returned valid responses
- **Repomix Performance**: 109ms average context generation (well under 500ms threshold)
- **Memory Efficient**: `slots=True` reduces memory footprint by ~3x

### Conclusion

> **The Trinity Architecture is SOLID (Phase 29).**

Production-ready for high-concurrency environments with:

- Modular, maintainable code (6 files vs 1 monolithic file)
- Protocol-based design for testability
- Zero crashes under extreme conditions

### Running the Tests

```bash
# Run all agent tests (including stress tests)
uv run pytest packages/python/agent/src/agent/tests/ -n 3 -v

# Run stress tests only
uv run pytest packages/python/agent/src/agent/tests/stress_tests/ -v
```

Expected output:

```
======================== 610 passed, 2 skipped in 25.0s ========================
```
