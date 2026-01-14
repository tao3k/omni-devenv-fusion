# Phase 36: Trinity v2.0 - Swarm Engine + Skills

> **Status**: Implemented (Current)
> **Date**: 2024-XX-XX
> **Related**: Phase 35 (Sidecar + Pure MCP), Phase 39 (Self-Evolving Feedback)

## Overview

Phase 36 represents a major evolution of the Trinity Architecture, introducing:

1. **Phase 36**: Trinity v2.0 with **Swarm Engine** - Runtime orchestrator with skill dispatch
2. **Phase 36.5**: **Hot Reload & Index Sync** - Dynamic skill loading
3. **Phase 36.6**: **Production Stability** - Async Task GC, Atomic Upsert, Startup Reconciliation

## Trinity v2.0 Architecture

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
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Phase 36: Swarm Engine

### Key Innovation: Execution is a Skill

**Before (Legacy)**: Executor was a Python module

```python
# Legacy - DO NOT USE
from common.mcp_core.execution import SafeExecutor

executor = SafeExecutor()
result = await executor.run("ls", ["-la"])
```

**After (Phase 36)**: Executor is a logical role played by skills

```python
# New approach - Use the terminal skill via Swarm Engine
from agent.core.swarm import get_swarm

result = await get_swarm().execute_skill(
    skill_name="terminal",
    command="run_task",
    args={"command": "ls", "args": ["-la"]},
    mode="direct",  # or "sidecar_process", "docker"
    timeout=60,
)
```

### Swarm Engine Implementation

```python
# agent/core/swarm.py

class Swarm:
    """Runtime orchestrator for skill dispatch and isolation."""

    _instance: Optional["Swarm"] = None
    _skills: Dict[str, ISkill] = {}
    _observers: List[Callable] = []

    @staticmethod
    def get_instance() -> "Swarm":
        """Get or create the Swarm singleton."""
        if Swarm._instance is None:
            Swarm._instance = Swarm()
        return Swarm._instance

    async def execute_skill(
        self,
        skill_name: str,
        command: str,
        args: dict,
        mode: str = "direct",
        timeout: int = 60,
    ) -> dict:
        """
        Execute a skill command with optional isolation.

        Args:
            skill_name: Name of the skill (e.g., "terminal", "git")
            command: Command to execute (e.g., "run_task", "status")
            args: Command arguments
            mode: Execution mode ("direct", "sidecar_process", "docker")
            timeout: Command timeout in seconds

        Returns:
            Command result dict
        """
        # Load skill if not loaded
        if skill_name not in self._skills:
            await self._load_skill(skill_name)

        skill = self._skills[skill_name]

        # Execute based on mode
        if mode == "direct":
            return await self._execute_direct(skill, command, args, timeout)
        elif mode == "sidecar_process":
            return await self._execute_sidecar(skill, command, args, timeout)
        elif mode == "docker":
            return await self._execute_docker(skill, command, args, timeout)
        else:
            raise ValueError(f"Unknown execution mode: {mode}")

    async def _execute_direct(
        self,
        skill: ISkill,
        command: str,
        args: dict,
        timeout: int,
    ) -> dict:
        """Execute directly in main process."""
        cmd = skill.commands.get(command)
        if cmd is None:
            raise CommandNotFoundError(command)

        result = await cmd.func(**args)
        return {"success": True, "result": result}

    async def _execute_sidecar(
        self,
        skill: ISkill,
        command: str,
        args: dict,
        timeout: int,
    ) -> dict:
        """Execute in isolated subprocess."""
        return await run_skill_script(
            skill_dir=skill.manifest.path,
            script_name=f"scripts/{command}.py",
            args=args,
            timeout=timeout,
        )
```

---

## Phase 36.5: Hot Reload & Index Sync

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Phase 36.5: Hot Reload System                            │
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
   └─ Index Sync Observer → Vector Store Upsert
```

### Observer Pattern

```python
from agent.core.skill_manager import get_skill_manager

manager = get_skill_manager()

async def on_skill_change(skill_name: str, change_type: str):
    """Callback signature (Phase 36.5): (skill_name, change_type)"""
    if change_type == "load":
        await index_single_skill(skill_name)
    elif change_type == "unload":
        await remove_skill_from_index(skill_name)
    elif change_type == "reload":
        await index_single_skill(skill_name)

manager.subscribe(on_skill_change)
```

### Debounced Notifications

```python
# Loading 10 skills at startup
for skill in skills:
    manager._notify_change(skill, "load")
# → ONE notification after 200ms (not 10!)
```

---

## Phase 36.6: Production Optimizations

### 1. Async Task GC Protection

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

### 2. Atomic Upsert (Vector Store)

```python
# Single atomic operation (no race conditions)
collection.upsert(
    documents=[semantic_text],
    ids=[skill_id],
    metadatas=[metadata],
)
```

### 3. Startup Reconciliation

```python
async def reconcile_index(loaded_skills: list[str]) -> dict[str, int]:
    """
    Cleanup phantom skills after crash/unclean shutdown.

    1. Get all local skill IDs from vector store
    2. Compare with loaded skills
    3. Remove phantoms (in index but not loaded)
    4. Re-index missing skills

    Returns:
        {"removed": N, "reindexed": N}
    """
    # Get all skill IDs in vector store
    stored_ids = set(await vm.list_all_ids())

    # Find phantoms (in store but not loaded)
    loaded_set = set(loaded_skills)
    phantoms = stored_ids - loaded_set

    # Remove phantoms
    for phantom_id in phantoms:
        await vm.delete(phantom_id)

    # Re-index any missing from disk
    missing = loaded_set - stored_ids
    for skill_name in missing:
        await index_single_skill(skill_name)

    return {"removed": len(phantoms), "reindexed": len(missing)}
```

---

## Performance at Scale

| Metric                        | Value                          |
| ----------------------------- | ------------------------------ |
| Concurrent reload (10 skills) | 1 notification (90% reduction) |
| Reload time (with sync)       | ~80ms                          |
| Phantom skill detection       | Automatic at startup           |
| Task GC safety                | Guaranteed                     |

## Evolution Comparison

| Aspect             | Phase 29 (Protocols) | Phase 36 (Swarm)                       |
| ------------------ | -------------------- | -------------------------------------- |
| **Execution Path** | Direct function call | Swarm Engine → Skill dispatch          |
| **Executor Type**  | Function             | Logical role (Terminal skill)          |
| **Hot-Reload**     | Manual               | Automatic with observers               |
| **Isolation**      | None                 | Direct, sidecar, docker modes          |
| **Index Sync**     | Manual               | Automatic with debounced notifications |

## Key Files

| File                          | Purpose                        |
| ----------------------------- | ------------------------------ |
| `agent/core/swarm.py`         | Swarm Engine implementation    |
| `agent/core/skill_manager.py` | SkillManager with hot reload   |
| `agent/core/module_loader.py` | Module loading with hot-reload |
| `agent/core/registry/`        | Modular skill registry         |

## Related Specs

- `assets/specs/phase29_trinity_protocols.md`
- `assets/specs/phase35_sidecar_mcp.md`
- `assets/specs/phase39_self_evolving_feedback_loop.md`
- `assets/specs/phase40_automated_reinforcement_loop.md`
