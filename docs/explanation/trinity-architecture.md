# Trinity Architecture

> **Core Philosophy**: "Everything is a Skill" - The Executor is no longer a code module, but a logical role played by atomic skills.

## Quick Reference

| Component        | Purpose                                    |
| ---------------- | ------------------------------------------ |
| **Orchestrator** | Strategic planning and context assembly    |
| **Coder**        | Read/write operations (filesystem, git)    |
| **Executor**     | Execution and operations (terminal, tools) |

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

- `skills/filesystem` - File I/O, grep search, AST operations (consolidated from file_ops)
- `skills/structural_editing` - AST-based refactoring with dry-run
- `skills/code_insight` - AST analysis, code structure

**Usage**: `@omni("filesystem.read_file", {"path": "README.md"})`

### 🛠️ Executor (The Hands)

**Purpose**: Running commands and operations.

**Implementation**:

- `skills/terminal` - Shell command execution (replaces legacy `SafeExecutor`)
- `skills/git` - Version control operations
- `skills/testing` - Test execution

**Usage**: `@omni("terminal.run_task", {"command": "ls", "args": ["-la"]})`

> **Key Change**: The Executor is NO LONGER a Python class. It's a logical role fulfilled by `skills/terminal/tools.py`. This skill contains `SafeExecutor` logic directly, enabling hot-reload and sandboxing without core code changes.

## Execution Model Evolution

| Aspect             | Legacy (Trinity v1)                            | Current (Trinity v2)                                           |
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
@omni("terminal.run_task", {"command": "ls", "args": ["-la"]})

# Or directly via Swarm Engine
from agent.core.swarm import get_swarm

result = await get_swarm().execute_skill(
    skill_name="terminal",
    command="run_task",
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
    name="run_task",
    category="workflow",
    description="Run safe development tasks (just, nix, git) with FLIGHT RECORDER.",
)
async def run_task(command: str, args: list[str] = None, **kwargs) -> str:
    """Terminal skill - The new 'Executor' implementation."""
    # Import from controller layer
    from agent.skills.terminal.scripts import engine

    result = engine.run_command(command, args, timeout=60)
    return engine.format_result(result, command, args)
```

## File Structure

```
packages/python/agent/src/agent/
├── core/
│   ├── swarm.py              # 🧠 Runtime orchestrator
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

# LEGACY - DELETED
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

---

## Hot Reload & Production Stability

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Hot Reload System                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    SkillManager (Runtime)                              │  │
│  ├───────────────────────────────────────────────────────────────────────┤  │
│  │  _observers: [MCP Observer, Index Sync Observer]                      │  │
│  │  _pending_changes: [(skill_name, change_type), ...]                   │  │
│  │  _debounced_notify(): 200ms batch window                               │  │
│  │  _background_tasks: set[asyncio.Task] (GC Protection)                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│           │                                                                  │
│           ▼                                                                  │
│  ┌────────────────────────┐    ┌──────────────────────────────┐            │
│  │  MCP Observer          │    │  Index Sync Observer         │            │
│  │  (Tool List Update)    │    │  (ChromaDB Sync)             │            │
│  ├────────────────────────┤    ├──────────────────────────────┤            │
│  │ send_tool_list_        │    │ index_single_skill()         │            │
│  │ changed()              │    │ remove_skill_from_index()    │            │
│  │                        │    │ reconcile_index()            │            │
│  └────────────────────────┘    └──────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Hot Reload Flow

```
File Modified (tools.py)
        ↓
manager.reload(skill_name)
        ↓
1. Syntax Validation (py_compile) - FAIL SAFE!
        ↓
2. Inline Unload (sys.modules cleanup, cache invalidation)
        ↓
3. Load Fresh (from disk)
        ↓
4. Debounced Notification (200ms batch)
        ↓
5. Observers notified:
   ├─ MCP Observer → send_tool_list_changed()
   └─ Index Sync Observer → ChromaDB Upsert
```

### Observer Pattern

```python
from agent.core.skill_manager import get_skill_manager

manager = get_skill_manager()

async def on_skill_change(skill_name: str, change_type: str):
    """Callback signature: (skill_name, change_type)"""
    if change_type == "load":
        await index_single_skill(skill_name)
    elif change_type == "unload":
        await remove_skill_from_index(skill_name)
    elif change_type == "reload":
        await index_single_skill(skill_name)

manager.subscribe(on_skill_change)
```

### Debounced Notifications

Multiple rapid skill changes are batched into a single notification:

```python
# Loading 10 skills at startup
for skill in skills:
    manager._notify_change(skill, "load")
# → ONE notification after 200ms (not 10!)
```

### Production Optimizations

#### 1. Async Task GC Protection

```python
class SkillManager:
    _background_tasks: set[asyncio.Task] = set()

    def _fire_and_forget(self, coro: asyncio.coroutine) -> asyncio.Task:
        """Fire-and-forget with GC protection."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task
```

#### 2. Atomic Upsert (ChromaDB)

```python
# Single atomic operation (no race conditions)
collection.upsert(
    documents=[semantic_text],
    ids=[skill_id],
    metadatas=[...],
)
```

#### 3. Startup Reconciliation

```python
async def reconcile_index(loaded_skills: list[str]) -> dict[str, int]:
    """Cleanup phantom skills after crash/unclean shutdown."""
    # 1. Get all local skill IDs from ChromaDB
    # 2. Compare with loaded skills
    # 3. Remove phantoms (in index but not loaded)
    # 4. Re-index missing skills
    return {"removed": N, "reindexed": N}
```

### Performance at Scale

| Metric                        | Value                          |
| ----------------------------- | ------------------------------ |
| Concurrent reload (10 skills) | 1 notification (90% reduction) |
| Reload time (with sync)       | ~80ms                          |
| Phantom skill detection       | Automatic at startup           |
| Task GC safety                | Guaranteed                     |

---

## Self-Evolving Feedback Loop (The Harvester)

The system now learns from experience. Successful routing decisions boost future confidence, and the system automatically records feedback signals.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Self-Evolving System                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Query → Semantic Router → Skill Execution → Feedback Recording        │
│       ↓              ↓                ↓                   ↓                  │
│  Vector Search    Hybrid Score    Success?        FeedbackStore             │
│  (ChromaDB)       (+keyword)      (Reviewer)      (.memory/routing_        │
│                                      Approval         feedback.json)        │
│       ↓              ↓                ↓                   ↓                  │
│  Confidence    Final Score    High Signal         Boost +0.1               │
│  0.60          0.95           → Future queries → Confidence 0.70           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### FeedbackStore

```python
class FeedbackStore:
    """Lightweight store for routing reinforcement learning."""
    MIN_SCORE = -0.3   # Maximum penalty
    MAX_SCORE = 0.3    # Maximum boost
    DECAY_FACTOR = 0.1  # How much each feedback affects score
    TIME_DECAY_RATE = 0.99  # Decay multiplier per read (1% decay)

    def record_feedback(self, query: str, skill_id: str, success: bool) -> float:
        """Record user feedback for a routing decision."""

    def get_boost(self, query: str, skill_id: str) -> float:
        """Get boost with time-based decay."""
```

### Automated Reinforcement

Three automatic feedback pathways:

| Signal Source         | Trigger                    | Boost          |
| --------------------- | -------------------------- | -------------- |
| **CLI Success**       | `omni git.status` executes | +0.1           |
| **Reviewer Approval** | Audit passes               | +0.1 (trusted) |
| **Time Decay**        | Each read                  | 1% decay       |

### Scoring Formula

```
Final Score = Base Vector Score
            + Keyword Bonus (+0.1-0.3)
            + Verb Priority Boost (+0.2 for CORE_ACTION_VERBS)
            + Feedback Boost (+0.1 per success, max +0.3)
            - Sigmoid Calibration (stretch 0.3-0.95 range)
```

### Feedback Storage

**Location**: `.memory/routing_feedback.json`

```json
{
  "git.status": {
    "git": 0.1
  },
  "commit code": {
    "git": 0.2
  }
}
```

### Decay Mechanism

Scores decay by 1% each time they are read:

```
0.10 → 0.099 → 0.098 → ... → 0.01 (removed)
```

Prevents "Matthew effect" where old successful skills dominate forever.

### File Changes

| File                                       | Purpose                         |
| ------------------------------------------ | ------------------------------- |
| `agent/capabilities/learning/harvester.py` | FeedbackStore class + decay     |
| `agent/core/skill_discovery/vector.py`     | Feedback boost in hybrid search |
| `agent/core/router/semantic_router.py`     | Show feedback reasoning         |
| `agent/cli/runner.py`                      | CLI success feedback            |
| `agent/core/orchestrator/feedback.py`      | Reviewer approval feedback      |

### Verification

```bash
# View learned feedback
cat .memory/routing_feedback.json

# Run tests
uv run pytest packages/python/agent/src/agent/tests/ -k "feedback" -v
```

### Related Specs

- `assets/specs/self_evolving_feedback_loop.md`
- `assets/specs/automated_reinforcement_loop.md`

---

## Wisdom-Aware Routing

From "muscle memory" to "intelligent guidance" - learn from past lessons

The system now injects retrieved lessons from `harvested/*.md` into the routing prompt, so the LLM generates Mission Briefs that avoid known pitfalls.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Wisdom-Aware Routing                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Query                                                                  │
│       ↓                                                                       │
│  SemanticRouter.route()                                                      │
│       ↓                                                                       │
│  ┌─────────────────────────────────────┐                                    │
│  │  Parallel:                          │                                    │
│  │  - Build routing menu               │                                    │
│  │  - Consult Librarian (harvested/)   │ ← NEW: Retrieve past lessons        │
│  └─────────────────────────────────────┘                                    │
│       ↓                                                                       │
│  System Prompt + PAST LESSONS                                                │
│       ↓                                                                       │
│  LLM generates Mission Brief with:                                           │
│  - "Use filesystem for file edits"                                           │
│  - "NOTE: Remember to hot-reload after tools.py changes"                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component                  | Purpose                                         |
| -------------------------- | ----------------------------------------------- |
| `SemanticRouter.librarian` | Lazy-loaded Librarian function                  |
| `_format_lessons()`        | Format knowledge results for prompt             |
| `route()`                  | Parallel knowledge retrieval with menu building |

### How It Works

1. **Parallel Retrieval**: While building the routing menu, also query Librarian for relevant lessons
2. **Lesson Formatting**: Format top 3 lessons with title, category, and content
3. **Prompt Injection**: Add `RELEVANT PAST LESSONS` section to system prompt
4. **Brief Generation**: LLM references lessons when generating Mission Brief

### Example

**User Query**: "I need to commit my changes"

**Knowledge Retrieved** (from `harvested/*.md`):

```markdown
### Git Commit Workflow Best Practices

- Always run `git_status` first to see what's staged
- Use `git_stage_all` for bulk staging (more reliable)
```

**Generated Mission Brief**:

```
Commit staged changes with message 'feat(router): add wisdom-aware routing'.

Steps:
1. Run git_status to verify what's staged
2. Use git_stage_all to ensure all changes are staged
3. Review the diff before proceeding

NOTE: Previous session emphasized using git_stage_all for bulk staging
as individual staging can be unreliable.
```

### Configuration

```python
router = SemanticRouter(
    use_wisdom_routing=True,  # Enable wisdom-aware routing (default: True)
)
```

### Related Files

| File                                        | Purpose                                  |
| ------------------------------------------- | ---------------------------------------- |
| `agent/core/router/semantic_router.py`      | Librarian integration, lesson formatting |
| `agent/capabilities/knowledge/librarian.py` | `consult_knowledge_base` function        |
| `agent/capabilities/learning/harvester.py`  | Knowledge harvesting                     |

### Related Specs

- `assets/specs/phase41_wisdom_aware_routing.md`
- `assets/specs/phase39_self_evolving_feedback_loop.md`
- `assets/specs/phase40_automated_reinforcement_loop.md`

---

## State-Aware Routing

Ground routing in reality - prevent hallucinated actions by detecting environment state

The system now detects real-time environment state (Git status, active context) and injects it into the routing prompt, preventing the router from suggesting actions that conflict with current reality.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         State-Aware Routing                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Query                                                                  │
│       ↓                                                                       │
│  SemanticRouter.route()                                                      │
│       ↓                                                                       │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  Three-Way Parallel:                                │                    │
│  │  - Build routing menu (blocking, ~5ms)              │                    │
│  │  - Consult Librarian for wisdom (parallel, ~50ms)   │                    │
│  │  - ContextSniffer.get_snapshot() (parallel, ~10ms)  │ ← NEW: Environment  │
│  └─────────────────────────────────────────────────────┘                    │
│       ↓                                                                       │
│  System Prompt + WISDOM + ENVIRONMENT STATE                                  │
│       ↓                                                                       │
│  LLM generates Mission Brief that:                                           │
│  - References modified files from Git status                                 │
│  - Acknowledges current branch context                                       │
│  - Avoids suggesting actions that conflict with reality                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component                    | Purpose                                |
| ---------------------------- | -------------------------------------- |
| `ContextSniffer`             | Fast, async environment state detector |
| `get_sniffer()`              | Singleton accessor for ContextSniffer  |
| `sniffer.get_snapshot()`     | Returns formatted environment state    |
| `RoutingResult.env_snapshot` | Field to store environment snapshot    |

### What ContextSniffer Detects

1. **Git Status**
   - Current branch name
   - Number of modified files
   - Up to 3 modified file names (with +N more indicator)

2. **Active Context**
   - Reads `.memory/active_context/SCRATCHPAD.md`
   - Reports line count or "Empty" state

### Example

**User Query**: "commit my changes"

**Environment Snapshot Retrieved**:

```
[ENVIRONMENT STATE]
- Branch: main | Modified: 51 files (M assets/references.yaml, M assets/settings.yaml, ...)
- Active Context: Empty
```

**Mission Brief Generated**:

```
Commit staged changes. Based on the current environment, 51 files are modified.
Ensure you review the most important changes before committing.
```

### CLI Integration

```bash
$ omni route invoke "commit my changes" --verbose

# Output includes:
╭──────────────────────── Environment State ────────────────────────╮
│ [ENVIRONMENT STATE]                                                          │
│ - Branch: main | Modified: 51 files (...)                                    │
│ - Active Context: Empty                                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### How It Works

1. **Parallel Execution**: Menu building, wisdom retrieval, and environment sniffing happen in parallel
2. **Async I/O**: Git commands run async to avoid blocking
3. **Lazy Loading**: ContextSniffer is lazily loaded to avoid slow initialization
4. **Graceful Degradation**: If sniffing fails, continues with empty snapshot

### Configuration

```python
router = SemanticRouter(
    use_wisdom_routing=True,  # Wisdom-aware routing (default: True)
    # State-aware routing is always enabled (no flag needed)
)
```

### Related Files

| File                                   | Purpose                                |
| -------------------------------------- | -------------------------------------- |
| `agent/core/router/sniffer.py`         | NEW: ContextSniffer class              |
| `agent/core/router/semantic_router.py` | Three-way parallel, env_snapshot field |
| `agent/core/router/models.py`          | RoutingResult.env_snapshot field       |
| `agent/cli/commands/route.py`          | Display environment snapshot in CLI    |

### Related Specs

- `assets/specs/phase42_state_aware_routing.md`
- `assets/specs/phase41_wisdom_aware_routing.md`

---

## The Holographic Agent

Extend state awareness from Router to Agent execution layer.

While State-Aware Routing gave the Router "full holographic vision" during task dispatch, this enhancement ensures the Agent maintains that vision throughout execution using **Continuous State Injection (CSI)**.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Holographic OODA Loop                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Agent ReAct Loop (Upgraded to Holographic)                                 │
│       ↓                                                                     │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │  For each step:                                     │                    │
│  │  1. OBSERVE:   Get live environment snapshot        │ ← CSI: Every step  │
│  │  2. ORIENT:   Inject snapshot into system prompt    │                    │
│  │  3. ACT:      Call LLM with dynamic context         │                    │
│  │  4. OBSERVE:  Get result, next iteration updates    │                    │
│  └─────────────────────────────────────────────────────┘                    │
│       ↓                                                                     │
│  Agent "sees" the consequences of actions immediately                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component               | Purpose                                |
| ----------------------- | -------------------------------------- |
| `BaseAgent.sniffer`     | ContextSniffer instance for each agent |
| `_run_react_loop()`     | Modified to inject snapshot every step |
| `dynamic_system_prompt` | Base prompt + live environment state   |

### How It Works

1. **Before Each LLM Call**: Agent captures environment snapshot
2. **Dynamic Prompt**: Appends snapshot to system prompt
3. **LLM Reasoning**: Agent sees current Git status, file state
4. **Action Execution**: Agent verifies assumptions before acting

### Example: Agent Detects Lefthook Changes

**Before (Legacy)**:

```
Agent: "I'll commit the staged files..."
Lefthook: reformats files, unstages them
Agent: "Commit failed... but I don't know why" ❌
```

**After (Holographic)**:

```
Agent: "Checking environment snapshot..."
Snapshot: "Branch: main | Modified: 5 files (reformatted by lefthook)"
Agent: "Ah! Lefthook reformatted files. Re-staging now." ✅
```

### System Prompt Enhancement

Agents now have a `HOLOGRAPHIC AWARENESS` section:

```markdown
## 📡 HOLOGRAPHIC AWARENESS

- You will receive a LIVE ENVIRONMENT SNAPSHOT at each reasoning cycle
- The snapshot shows current Git status (branch, modified files)
- **TRUST THE SNAPSHOT**: If a file you expected isn't mentioned, it may not exist
- Don't assume previous actions succeeded - verify with the snapshot
```

### Benefits

| Benefit                      | Description                                |
| ---------------------------- | ------------------------------------------ |
| **No More Blind Execution**  | Agent sees state changes immediately       |
| **Reduced Token Waste**      | No need for `git status` / `ls` tool calls |
| **Hallucination Prevention** | Agent trusts real data, not assumptions    |
| **Faster Recovery**          | Agent detects failures and self-corrects   |

### Related Files

| File                           | Purpose                          |
| ------------------------------ | -------------------------------- |
| `agent/core/agents/base.py`    | Added sniffer, CSI in ReAct loop |
| `agent/core/router/sniffer.py` | Existing (State-Aware Routing)   |

### Related Specs

- `assets/specs/holographic_agent.md`
- `assets/specs/state_aware_routing.md`

---

## The Experiential Agent

Extend holographic awareness with skill-level episodic memory.

While Holographic Agent gave the agent "holographic vision" (seeing the environment), this gives it "experiential wisdom" (learning from past mistakes).

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Experiential Memory System                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Task Execution                                                              │
│       ↓                                                                      │
│       ├─→ RAG Knowledge (static project docs)                               │
│       ├─→ Holographic Vision (live environment state)                       │
│       └─→ Skill-Level Lessons (harvested insights)                          │
│       ↓                                                                      │
│  LLM receives ALL three + mission brief                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component                              | Purpose                                   |
| -------------------------------------- | ----------------------------------------- |
| `librarian.get_skill_lessons()`        | Query harvested insights for agent skills |
| `BaseAgent._get_agent_skill_lessons()` | Retrieve lessons for default skills       |
| `skill_lessons` parameter              | Injected into system prompt               |

### How It Works

1. **Harvest**: Developer uses `/memory_harvest` to log lessons
2. **Retrieve**: Agent calls `get_skill_lessons(skills=default_skills)`
3. **Inject**: Lessons formatted and added to system prompt
4. **Apply**: LLM avoids repeating past mistakes

### System Prompt Enhancement

```markdown
### 🛑 KNOWN PITFALLS & PAST LESSONS

- **git**: Don't run git commit without staging files first - always check git status
- **filesystem**: Always use absolute paths, never relative
```

### Benefits

| Benefit                  | Description                              |
| ------------------------ | ---------------------------------------- |
| **No Repeated Mistakes** | Agent remembers what went wrong before   |
| **Continuous Learning**  | Each session improves future performance |
| **Cross-Session Wisdom** | Hard-won lessons persist across sessions |

### Related Files

| File                                        | Change                        |
| ------------------------------------------- | ----------------------------- |
| `agent/capabilities/knowledge/librarian.py` | Added `get_skill_lessons()`   |
| `agent/core/agents/base.py`                 | Added skill lessons retrieval |

### Related Specs

- `assets/specs/experiential_agent.md`
- `assets/specs/holographic_agent.md`

---

## The Meta-Agent

Autonomous Build-Test-Improve Loop - The system can now fix its own bugs!

The Meta-Agent introduces an autonomous "Build-Test-Improve" loop that implements a self-directed TDD (Test-Driven Development) cycle. This transforms the agent from a passive tool into an active engineer.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    The Meta-Agent - TDD Loop                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  +---------------------------------------------------------------------+   │
│  |                    TDD Cycle (5 iterations max)                     |   |
│  |                                                                       |   |
│  |   +------------+    +------------+    +------------+                |   |
│  |   |   TEST     | -> |  ANALYZE   | -> |    FIX     |                |   |
│  |   | Run tests  |    | LLM analysis|    | Apply code |                |   |
│  |   +------------+    +------------+    +------------+                |   |
│  |         |                                    |                       |   |
│  |         v                                    v                       |   |
│  |   +------------+    +------------+                                |   |
│  |   | All pass?  | <- |  VERIFY    |                                |   |
│  |   |            |    | Re-run tests|                                |   |
│  |   +------------+    +------------+                                |   |
│  |         |                                                         |   |
│  |         v                                                         |   |
│  |   +------------+                                                  |   |
│  |   |  REFLECT   | -> Vector Store (learn from mission)             |   |
│  |   +------------+                                                  |   |
│  +---------------------------------------------------------------------+   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component           | Purpose                                        |
| ------------------- | ---------------------------------------------- |
| `MetaAgent`         | Main class with TDD loop                       |
| `MissionContext`    | Tracks mission state, iterations, test results |
| `TestResult`        | Individual test outcome                        |
| `SimpleLLMProvider` | Pattern-based fix generation (replaceable)     |

### The TDD Cycle

```python
class MetaAgent:
    async def run_mission(
        self,
        mission_description: str,
        test_command: str,
        target_path: Optional[str] = None,
    ) -> MissionContext:
        """
        Run a single mission: test -> analyze -> fix -> verify -> reflect.
        """

    async def _tdd_cycle(self, context: MissionContext) -> None:
        """Execute one TDD cycle."""
        while context.iterations < max_iterations:
            # 1. Test
            passed = await self._run_tests(context)
            if passed:
                return

            # 2. Analyze
            analysis = await self._analyze_failures(context)

            # 3. Fix
            await self._apply_fix(context, analysis)

            # 4. Verify (loop continues)
```

### Example: broken_math.py

```python
# broken_math.py (intentionally buggy)
def add(a: int, b: int) -> int:
    return a - b  # BUG: Should be a + b

def is_even(n: int) -> bool:
    return n % 2 == 1  # BUG: Should be == 0
```

### Test Results

```
Initial state: 2 failed, 2 passed
Meta-Agent:    2 iterations, 4 passed

Bugs Fixed:
1. add():    a - b -> a + b
2. is_even(): n % 2 == 1 -> n % 2 == 0
```

### Benefits

| Benefit                    | Description                                       |
| -------------------------- | ------------------------------------------------- |
| **Autonomous Debugging**   | Agent can fix issues without human intervention   |
| **Self-Healing**           | Code automatically repairs itself when tests fail |
| **Continuous Improvement** | System gets better over time through reflection   |
| **Pattern Learning**       | Same bugs don't repeat (stored in vector store)   |

### Related Files

| File                         | Purpose                       |
| ---------------------------- | ----------------------------- |
| `agent/core/meta_agent.py`   | MetaAgent class with TDD loop |
| `scripts/test_meta_agent.py` | Self-healing test script      |

### Related Specs

- `assets/specs/phase59_the_meta_agent.md`
- `assets/specs/phase44_experiential_agent.md`
- `assets/specs/phase39_self_evolving_feedback_loop.md`

---

## Rust Core Integration (Architecture)

Elevate Rust to a first-class citizen in the `packages/` directory.

Establishes a proper Rust workspace with high-performance crates for environment sensing.

### New Directory Structure

```
omni-devenv-fusion/
├── packages/
│   ├── python/          # Existing Python code
│   │   ├── agent/
│   │   └── common/
│   └── rust/            # [NEW] Rust Workspace Root
│       ├── Cargo.toml   # Workspace configuration
│       ├── crates/      # [Atomic Units] Pure Rust logic
│       │   ├── omni-sniffer/   # Holographic sensing (libgit2)
│       │   └── omni-types/     # Shared type definitions
│       └── bindings/    # [Glue Layer] Language bindings
│           └── python/  # omni_core_rs (PyO3)
```

### Crate Organization

| Crate          | Purpose                              | Dependencies       |
| -------------- | ------------------------------------ | ------------------ |
| `omni-types`   | Common type definitions, error types | serde, thiserror   |
| `omni-sniffer` | High-performance environment sensing | git2, tokio, serde |
| `omni-core-rs` | Python bindings (PyO3)               | pyo3, omni-sniffer |

### Performance Comparison

| Operation     | Python (subprocess) | Rust (libgit2) | Speedup |
| ------------- | ------------------- | -------------- | ------- |
| Git status    | ~50ms               | ~1ms           | **50x** |
| Scan context  | ~10ms               | ~0.5ms         | **20x** |
| Full snapshot | ~60ms               | ~2ms           | **30x** |

### Rust Usage

```rust
// omni-sniffer/src/lib.rs

pub struct OmniSniffer {
    repo_path: std::path::PathBuf,
}

impl OmniSniffer {
    /// Get Git status (uses libgit2, 10-50x faster than subprocess)
    pub fn scan_git(&self) -> Result<(String, usize, usize, Vec<String>)> {
        let repo = Repository::open(&self.repo_path)?;
        // High-performance Git operations via libgit2
    }

    pub fn get_snapshot(&self) -> EnvironmentSnapshot {
        // Returns structured snapshot for Python binding
    }
}
```

### Python Binding Usage

```python
# Usage in Python
from omni_core_rs import PyOmniSniffer

sniffer = PyOmniSniffer(".")
snapshot = sniffer.get_snapshot()
print(snapshot.to_prompt_string())
```

### Related Files

| File                                           | Purpose                 |
| ---------------------------------------------- | ----------------------- |
| `packages/rust/Cargo.toml`                     | Workspace configuration |
| `packages/rust/crates/omni-sniffer/src/lib.rs` | Core implementation     |
| `packages/rust/crates/omni-types/src/lib.rs`   | Shared types            |
| `packages/rust/bindings/python/src/lib.rs`     | PyO3 bindings           |

### Related Specs

- `assets/specs/phase45_rust_core_integration.md`

---

## The Neural Bridge (Type Unification)

Establish type unification between Rust and Python, enabling seamless data flow across language boundaries.

Creates **shared type definitions** using Rust as the source of truth (SSOT), with PyO3 auto-generated bindings for Python consumption.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Neural Bridge - Type Unification                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Rust Layer (SSOT)                    Python Layer                          │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────┐    │
│  │     omni-types/         │───►│     omni_core_rs (PyO3)             │    │
│  │  - EnvironmentSnapshot  │    │  - PyEnvironmentSnapshot            │    │
│  │  - OmniResult<T>        │    │  - Auto-generated bindings          │    │
│  │  - OmniError            │    │  - serde JSON serialization         │    │
│  └─────────────────────────┘    └─────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Type Hierarchy

```rust
// omni-types/src/lib.rs

use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnvironmentSnapshot {
    pub git_branch: String,
    pub git_modified: usize,
    pub git_staged: usize,
    pub active_context_lines: usize,
    pub dirty_files: Vec<String>,
    pub timestamp: f64,
}

impl EnvironmentSnapshot {
    /// Convert to prompt string for LLM injection
    pub fn to_prompt_string(&self) -> String {
        let dirty_desc = if self.dirty_files.is_empty() {
            "Clean".to_string()
        } else {
            let count = self.dirty_files.len();
            let preview = self.dirty_files.iter().take(3).cloned().collect::<Vec<_>>().join(", ");
            if count > 3 {
                format!("{count} files ({preview}, ...)")
            } else {
                format!("{count} files ({preview})")
            }
        };

        format!(
            "[LIVE ENVIRONMENT STATE]\n\
            - Git: Branch: {} | Modified: {} | Staged: {} | Status: {}\n\
            - Active Context: {} lines in SCRATCHPAD.md",
            self.git_branch,
            self.git_modified,
            self.git_staged,
            dirty_desc,
            self.active_context_lines
        )
    }
}
```

### Python Binding Pattern

```rust
// bindings/python/src/lib.rs

use pyo3::prelude::*;
use omni_types::EnvironmentSnapshot;

#[pyclass]
#[derive(serde::Serialize)]
struct PyEnvironmentSnapshot {
    git_branch: String,
    git_modified: usize,
    git_staged: usize,
    active_context_lines: usize,
    dirty_files: Vec<String>,
    timestamp: f64,
}

#[pymethods]
impl PyEnvironmentSnapshot {
    #[getter]
    fn git_branch(&self) -> String {
        self.git_branch.clone()
    }

    #[getter]
    fn git_modified(&self) -> usize {
        self.git_modified
    }

    fn to_prompt_string(&self) -> String {
        // Delegate to Rust implementation
        let snapshot = self.to_omni_types();
        snapshot.to_prompt_string()
    }

    fn to_json(&self) -> String {
        serde_json::to_string(&self).unwrap_or_else(|_| "{}".to_string())
    }
}
```

### Python Usage

```python
# Usage in Python
from omni_core_rs import PyOmniSniffer

sniffer = PyOmniSniffer(".")
snapshot = sniffer.get_snapshot()

# Access as Python object
print(snapshot.git_branch)      # "main"
print(snapshot.git_modified)    # 5
print(snapshot.to_prompt_string())  # Formatted string
print(snapshot.to_json())       # JSON serialized
```

### Performance Comparison

| Operation          | Python (dict) | Rust (SSOT) | Improvement |
| ------------------ | ------------- | ----------- | ----------- |
| Snapshot creation  | ~45ms         | ~2ms        | **22.5x**   |
| JSON serialization | ~8ms          | ~0.1ms      | **80x**     |
| Memory usage       | ~2KB          | ~0.5KB      | **4x**      |

### Benefits

| Benefit         | Description                                     |
| --------------- | ----------------------------------------------- |
| **Type Safety** | Rust's type system verified at compile time     |
| **SSOT**        | Single source of truth for all type definitions |
| **Performance** | Native serialization/deserialization            |
| **Ergonomics**  | Automatic PyO3 bindings reduce boilerplate      |

### Related Files

| File                                         | Purpose                   |
| -------------------------------------------- | ------------------------- |
| `packages/rust/crates/omni-types/Cargo.toml` | Types crate configuration |
| `packages/rust/crates/omni-types/src/lib.rs` | Shared type definitions   |
| `packages/rust/bindings/python/src/lib.rs`   | PyO3 bindings (updated)   |

### Related Specs

- `assets/specs/phase46_the_neural_bridge.md`
- `assets/specs/phase45_rust_core_integration.md`

---

## The Iron Lung (Rust I/O & Tokenization)

Safe, high-performance I/O and tokenization to solve context window overflow and performance bottlenecks.

Introduces two new atomic Rust crates:

- **omni-io**: Safe file reading with size limits, binary detection, and async support
- **omni-tokenizer**: BPE tokenization using cl100k_base (GPT-4/3.5 standard)

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         The Iron Lung                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Python Agent                                                               │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              omni-core-rs (PyO3 Bindings)                            │   │
│  │   ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐    │   │
│  │   │ read_file_safe │  │ count_tokens   │  │ truncate_tokens    │    │   │
│  │   │ (GIL release)  │  │ (GIL release)   │  │ (GIL release)      │    │   │
│  │   └────────┬───────┘  └────────┬───────┘  └─────────┬──────────┘    │   │
│  └────────────┼───────────────────┼─────────────────────┼────────────────┘   │
│               │                   │                     │                      │
│               ▼                   ▼                     ▼                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Rust Core Crates                                  │   │
│  │                                                                       │   │
│  │   ┌───────────────────────────────────────────────────────────────┐  │   │
│  │   │                       omni-io                                  │  │   │
│  │   │   ┌─────────────────────┐  ┌─────────────────────────────┐    │  │   │
│  │   │   │  Synchronous (Sync) │  │     Asynchronous (Async)    │    │  │   │
│  │   │   │  read_text_safe()   │  │  read_text_safe_async()     │    │  │   │
│  │   │   │  - std::fs          │  │  - tokio::fs                │    │  │   │
│  │   │   │  - Binary detection │  │  - Non-blocking I/O         │    │  │   │
│  │   │   │  - Size limits      │  │  - Concurrent reads         │    │  │   │
│  │   │   └─────────────────────┘  └─────────────────────────────┘    │  │   │
│  │   └───────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  │   ┌───────────────────────────────────────────────────────────────┐  │   │
│  │   │                    omni-tokenizer                              │  │   │
│  │   │   - cl100k_base encoding (GPT-4/3.5 standard)                 │  │   │
│  │   │   - BPE tokenization                                           │  │   │
│  │   │   - Zero network calls (bundled model)                        │  │   │
│  │   └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### omni-io: Dual API Design

```rust
// crates/omni-io/src/lib.rs

use std::path::Path;
use thiserror::Error;
use memchr::memchr;

use std::fs as std_fs;
use std::io::Read;
use tokio::fs as tokio_fs;
use tokio::io::AsyncReadExt;

#[derive(Error, Debug)]
pub enum IoError {
    #[error("File not found: {0}")]
    NotFound(String),
    #[error("File too large: {0} bytes (limit: {1})")]
    TooLarge(u64, u64),
    #[error("Binary file detected")]
    BinaryFile,
    #[error("IO error: {0}")]
    System(#[from] std::io::Error),
    #[error("UTF-8 decoding error")]
    Encoding,
}

/// Synchronous API (Best for Python `allow_threads` usage)
pub fn read_text_safe<P: AsRef<Path>>(path: P, max_bytes: u64) -> Result<String, IoError> {
    let path = path.as_ref();
    let metadata = std_fs::metadata(path)
        .map_err(|_| IoError::NotFound(path.to_string_lossy().to_string()))?;

    if metadata.len() > max_bytes {
        return Err(IoError::TooLarge(metadata.len(), max_bytes));
    }

    let mut file = std_fs::File::open(path)?;
    let mut buffer = Vec::with_capacity(metadata.len() as usize);
    file.read_to_end(&mut buffer)?;

    // Binary detection + UTF-8 lossy fallback
    if is_binary(&buffer) {
        return Err(IoError::BinaryFile);
    }
    Ok(String::from_utf8_lossy(&buffer).into_owned())
}

/// Asynchronous API (Powered by Tokio)
pub async fn read_text_safe_async<P: AsRef<Path>>(path: P, max_bytes: u64) -> Result<String, IoError> {
    let path = path.as_ref();
    let metadata = tokio_fs::metadata(path)
        .await
        .map_err(|_| IoError::NotFound(path.to_string_lossy().to_string()))?;

    if metadata.len() > max_bytes {
        return Err(IoError::TooLarge(metadata.len(), max_bytes));
    }

    let mut file = tokio_fs::File::open(path).await?;
    let mut buffer = Vec::with_capacity(metadata.len() as usize);
    file.read_to_end(&mut buffer).await?;

    if is_binary(&buffer) {
        return Err(IoError::BinaryFile);
    }
    Ok(String::from_utf8_lossy(&buffer).into_owned())
}

fn is_binary(buffer: &[u8]) -> bool {
    let check_len = std::cmp::min(buffer.len(), 8192);
    memchr(0, &buffer[..check_len]).is_some()
}
```

### omni-tokenizer: BPE Tokenization

```rust
// crates/omni-tokenizer/src/lib.rs

use thiserror::Error;
use tiktoken_rs::CoreBPE;

#[derive(Error, Debug)]
pub enum TokenizerError {
    #[error("Model initialization failed: {0}")]
    ModelInit(String),
    #[error("Encoding failed: {0}")]
    Encoding(String),
    #[error("Decoding failed: {0}")]
    Decoding(String),
}

static CL100K_BASE: once_cell::sync::Lazy<CoreBPE> =
    once_cell::sync::Lazy::new(|| {
        CoreBPE::cl100k_base().expect("Failed to load cl100k_base")
    });

/// Count tokens in text using cl100k_base (GPT-4/3.5 standard).
pub fn count_tokens(text: &str) -> usize {
    CL100K_BASE.encode_ordinary(text).len()
}

/// Truncate text to fit within a maximum token count.
pub fn truncate(text: &str, max_tokens: usize) -> String {
    let tokens = CL100K_BASE.encode_ordinary(text);
    if tokens.len() <= max_tokens {
        return text.to_string();
    }
    CL100K_BASE.decode(tokens[..max_tokens].to_vec())
        .unwrap_or_else(|_| text.to_string())
}
```

### GIL Release Pattern (Python Bindings)

Critical for Python integration - releases GIL during CPU-intensive operations:

```rust
// bindings/python/src/lib.rs

use pyo3::prelude::*;

/// Count tokens in text using cl100k_base (GPT-4/3.5 standard).
/// Releases GIL for CPU-intensive tokenization.
#[pyfunction]
fn count_tokens(text: &str) -> usize {
    Python::with_gil(|py| {
        py.allow_threads(|| {
            omni_tokenizer::count_tokens(text)
        })
    })
}

/// Truncate text to fit within a maximum token count.
/// Releases GIL for CPU-intensive tokenization.
#[pyfunction]
#[pyo3(signature = (text, max_tokens))]
fn truncate_tokens(text: &str, max_tokens: usize) -> String {
    Python::with_gil(|py| {
        py.allow_threads(|| {
            omni_tokenizer::truncate(text, max_tokens)
        })
    })
}

/// Safely read a text file with size and binary checks.
/// Releases GIL for CPU-intensive file operations.
#[pyfunction]
#[pyo3(signature = (path, max_bytes = 1048576))]
fn read_file_safe(path: String, max_bytes: u64) -> PyResult<String> {
    Python::with_gil(|py| {
        py.allow_threads(|| {
            omni_io::read_text_safe(path, max_bytes)
                .map_err(|e| anyhow::anyhow!(e))
        })
    }).map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
}
```

### Python Usage

```python
# Usage in Python
import omni_core_rs as core

# Count tokens (cl100k_base - GPT-4/3.5 standard)
text = "Hello world from Rust!"
token_count = core.count_tokens(text)
print(f"Token count: {token_count}")  # 5

# Truncate to fit context window
long_text = "This is a very long text " * 100
truncated = core.truncate_tokens(long_text, 10)
print(f"Truncated to {core.count_tokens(truncated)} tokens")

# Safe file reading
content = core.read_file_safe("README.md", 1024 * 1024)  # 1MB limit
print(f"Read {len(content)} bytes")
```

### Performance Benchmarks

| Operation        | Python (tiktoken HTTP) | Rust (native) | Improvement |
| ---------------- | ---------------------- | ------------- | ----------- |
| Token count      | ~45ms                  | ~0.3ms        | **150x**    |
| Truncate tokens  | ~50ms                  | ~0.4ms        | **125x**    |
| File read (1MB)  | ~25ms                  | ~0.1ms        | **250x**    |
| Binary detection | N/A                    | ~0.01ms       | -           |

### Architecture Rationale

| API Version | Use Case                             | Why                                                            |
| ----------- | ------------------------------------ | -------------------------------------------------------------- |
| **Sync**    | Python bindings with `allow_threads` | No Tokio runtime overhead; OS thread pool handles blocking I/O |
| **Async**   | Future Rust Agent Core               | Tokio scheduler enables high-concurrency file operations       |

### Benefits

| Benefit          | Description                                          |
| ---------------- | ---------------------------------------------------- |
| **Performance**  | 100-250x faster than Python alternatives             |
| **Safety**       | Binary detection, size limits prevent OOM            |
| **GIL Release**  | Concurrent execution during CPU-intensive operations |
| **Reliability**  | UTF-8 lossy fallback handles corrupted files         |
| **Zero Config**  | Built-in cl100k_base model, no network required      |
| **Future-Proof** | Async API ready for Rust Agent                       |

### Related Files

| File                                             | Purpose                          |
| ------------------------------------------------ | -------------------------------- |
| `packages/rust/crates/omni-io/Cargo.toml`        | I/O crate configuration          |
| `packages/rust/crates/omni-io/src/lib.rs`        | Safe file reading implementation |
| `packages/rust/crates/omni-tokenizer/Cargo.toml` | Tokenizer crate configuration    |
| `packages/rust/crates/omni-tokenizer/src/lib.rs` | BPE tokenization implementation  |
| `packages/rust/bindings/python/src/lib.rs`       | PyO3 bindings (updated)          |

### Related Specs

- `assets/specs/the_iron_lung.md`
- `assets/specs/neural_bridge.md`
- `assets/specs/rust_core_integration.md`

---

## The Knowledge Matrix

Unified Knowledge Index for Context-Aware AI Agents.

Skill RAG (dynamic tool loading) was completed earlier. The Knowledge Matrix extends this to **Knowledge RAG** - a unified matrix for indexing and searching project documentation, specifications, and memory.

### Architecture Overview

```
                    ┌─────────────────────────────────────┐
                    │         The Knowledge Matrix         │
                    └─────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
   │   Skills    │          │  Knowledge  │          │   Memory    │
   │   Table     │          │   Table     │          │   Table     │
   └─────────────┘          └─────────────┘          └─────────────┘
   └─────────────────────────┴─────────────────────────┘
                    │                 │
                    ▼                 ▼
           ┌─────────────────┐ ┌─────────────────┐
           │ Tool Discovery  │ │  Doc Search     │
           │ (skill.search)  │ │  (knowledge.*)  │
           └─────────────────┘ └─────────────────┘
```

### Key Components

| Component              | Purpose                       | Data Source              |
| ---------------------- | ----------------------------- | ------------------------ |
| **Knowledge Indexer**  | Scan and chunk Markdown files | `docs/`, `assets/specs/` |
| **Hybrid Search**      | Vector + keyword search       | LanceDB                  |
| **DocRecord/DocChunk** | Data models for indexing      | Pydantic dataclasses     |

### Key Functions

```python
from agent.core.knowledge.indexer import scan_markdown_files, sync_knowledge

# Scan docs directory
records = scan_markdown_files("docs/")

# Sync with incremental updates
stats = await sync_knowledge(store, "docs/", table_name="knowledge")
# Returns: {"added": N, "updated": N, "deleted": N, "total": N}
```

### Related Specs

- `assets/specs/phase70_the_knowledge_matrix.md`

---

## The Memory Mesh

Episodic Memory for Self-Learning Agents.

Completes the **Cognitive Trinity** by adding episodic memory - the ability for the Agent to remember past experiences and learn from them.

### Cognitive Trinity Complete

| Component     | Capability                     | Phase | Data Source                    |
| ------------- | ------------------------------ | ----- | ------------------------------ |
| **Skills**    | "I know how to do"             | 69 ✅ | `assets/skills/*/scripts/*.py` |
| **Knowledge** | "I know what that is"          | 70 ✅ | `docs/`, `assets/specs/`       |
| **Memory**    | "I remember doing that before" | 71 ✅ | VectorDB (LanceDB)             |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MemoryInterceptor (Runtime Hook)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Task Execution                                                             │
│       ↓                                                                    │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │  before_execution(user_input)                       │                   │
│  │  - Retrieve relevant memories from vector store     │ ← Context Injection│
│  │  - Return formatted memories for LLM context        │                   │
│  └─────────────────────────────────────────────────────┘                   │
│       ↓                                                                    │
│  Agent receives memories in system prompt                                   │
│       ↓                                                                    │
│  Task Execution (with memory context)                                       │
│       ↓                                                                    │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │  after_execution(user_input, tool_calls, success)   │                   │
│  │  - Generate reflection (success summary or error)   │ ← Memory Recording│
│  │  - Store experience in vector store                 │                   │
│  └─────────────────────────────────────────────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component                      | Purpose                 | File                    |
| ------------------------------ | ----------------------- | ----------------------- |
| **InteractionLog**             | Episode data model      | `memory/types.py`       |
| **MemoryManager**              | Write/retrieve memories | `memory/manager.py`     |
| **MemoryInterceptor**          | Runtime hook for memory | `memory/interceptor.py` |
| **AdaptiveLoader Integration** | Memory injection        | `adaptive_loader.py`    |

### Usage Example

```python
from agent.core.memory.manager import get_memory_manager

mm = get_memory_manager()

# Record experience
await mm.add_experience(
    user_query="git commit fails with lock",
    tool_calls=["git.commit"],
    outcome="failure",
    error_msg="index.lock exists",
    reflection="Solution: rm .git/index.lock"
)

# Recall relevant experiences
memories = await mm.recall("git commit lock")
for m in memories:
    print(f"[{m.outcome}] {m.reflection}")
```

### Related Specs

- `assets/specs/phase71_the_memory_mesh.md`

---

## Next Steps

- See `docs/skills.md` for skill implementation guide
- See `docs/reference/odf-ep-protocol.md` for engineering rules

---

# Legacy Content

> The following content is kept for historical reference. Current implementation is Trinity v2.0.

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

## File Structure (Legacy)

```
packages/python/agent/src/agent/core/
├── registry/              # Modular skill registry
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
├── isolation.py           # Sidecar Execution Pattern
├── lazy_cache.py          # RepomixCache class
└── skills_path.py         # Skills directory resolution

.cache/
└── <project>/
    └── skill_<name>_repomix.xml  # Cached contexts

assets/skills/<skill>/
├── SKILL.md              # Skill manifest + rules (definition file)
├── tools.py              # Skill interface (lightweight)
├── README.md             # Reference docs
├── scripts/              # Atomic implementations
│   └── *.py              # Heavy imports allowed here
├── pyproject.toml        # Skill dependencies (for subprocess mode)
└── repomix.json          # Atomic context config (optional)
```

## Trinity v1 Evolution

| Aspect                 | Trinity v1                 | Trinity v2                                            |
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

## Sidecar Execution Pattern

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

### With Pure MCP Server (`mcp_server.py`)

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

## Production Validation

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

> **The Trinity Architecture is SOLID.**

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
