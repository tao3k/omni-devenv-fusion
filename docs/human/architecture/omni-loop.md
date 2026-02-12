# Omni Loop (CCA Runtime)

> **Status**: Active (Current)
> **Version**: v2.1 | 2026-01-25 (Self-Evolution Enabled)

## Overview

Omni Loop is the **CCA (Cognitive Code Agent) Runtime** that integrates all system components into a cohesive agent execution environment.

### Core Components

| Component         | System (Omega) | Purpose                                                     |
| :---------------- | :------------- | :---------------------------------------------------------- |
| **ReAct Loop**    | Cortex         | Execute tasks via Observe-Decide-Act-Reflect cycle          |
| **Librarian**     | Knowledge      | RAG-powered knowledge retrieval                             |
| **Hippocampus**   | Memory         | Long-term memory recall and experience commitment           |
| **Cerebellum**    | Navigation     | Semantic scanning and AST-based routing                     |
| **Immune System** | Homeostasis    | Conflict detection and isolated execution audit             |
| **Evolution**     | Evolution      | Self-learning: harvest skills & extract rules from sessions |

## CCA Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                      CCA Runtime Cycle                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│    │ Observe  │ ─► │  Orient  │ ─► │  Decide  │               │
│    │ Context  │    │  (Cortex)│    │  (LLM)   │               │
│    └──────────┘    └──────────┘    └──────────┘               │
│         ▲                                     │                │
│         │                                     ▼                │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│    │ Reflect  │ ◄── │   Act    │ ◄── │  Tool    │               │
│    │(Evolution)│    │(Executor)│    │  Call    │               │
│    └──────────┘    └──────────┘    └──────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Cycle Phases

1. **Observe**: Build layered context (Knowledge + Hippocampus Memory)
2. **Orient**: Cortex decomposition and task prioritization
3. **Decide**: LLM reasoning with context
4. **Act**: Execute tools via Homeostasis-isolated environments
5. **Reflect**: Evolution distills wisdom and saves to Hippocampus

## Self-Evolution

Omni Loop implements **Self-Evolution** to continuously improve from successful sessions.

### Dual-Path Evolution Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Self-Evolution Architecture                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Fast Path: Semantic Memory                     │   │
│  │  (System 1 - Fast Thinking)                                      │   │
│  │                                                                   │   │
│  │  User Correction → VectorStore → Context Injection → Future Action│   │
│  │  Rules/preferences applied automatically                         │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Slow Path: Procedural Skills                   │   │
│  │  (System 2 - Slow Thinking)                                      │   │
│  │                                                                   │   │
│  │  Successful Workflow → Harvester → Factory → quarantined skill   │   │
│  │  Complex workflows solidified into new Skills                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Memory Recall (Fast Path)

Before executing a task, Omni Loop searches for relevant learned rules:

```python
async def _inject_memory_context(self, task: str) -> None:
    """Associative Recall - Fast Path"""
    memories = await vector_store.search(query=task, n_results=3)
    if memories:
        self.context.add_system_message(
            f"\n[RECALLED MEMORIES]\n{memories}\n[/RECALLED MEMORIES]\n"
        )
```

### Harvester (Post-Execution)

After successful sessions (ending with `EXIT_LOOP_NOW`):

| Path     | Trigger                        | Output                      |
| -------- | ------------------------------ | --------------------------- |
| **Fast** | User corrections/preferences   | Rule saved to VectorStore   |
| **Slow** | Successful workflow (3+ tools) | Skill file in `quarantine/` |

### Skill Factory

Generated skills follow standard Omni Skill structure:

```python
# assets/skills/harvested/quarantine/{skill_name}.py
@skill(name="{skill_name}", description="{description}")
class {ClassName}:
    @tool
    async def run(self, ctx, {params}) -> str:
        """Auto-generated skill from observed workflow."""
        raise NotImplementedError("Requires manual implementation")
```

### Safety Measures

- All harvested skills go to `quarantine/` directory
- Must pass static analysis before promotion
- Require at least one integration test
- Human review recommended before activation

## Trinity Architecture Integration

Omni Loop implements the **Trinity Architecture** with three logical roles:

| Role             | Responsibility         | Example Tools             |
| ---------------- | ---------------------- | ------------------------- |
| **Orchestrator** | Planning & Strategy    | Context assembly, Routing |
| **Coder**        | Reading & Writing      | File operations, Search   |
| **Executor**     | Execution & Operations | Git, Terminal, Shell      |

## CLI Usage

### omni run vs omni run terminal: The Commander vs The Soldier

Understanding the distinction between `omni run` and `omni run terminal` is fundamental to mastering the Omni-Dev Fusion architecture:

| Aspect           | `omni run` (The Commander/Brain)             | `omni run terminal` (The Soldier/Limb)      |
| ---------------- | -------------------------------------------- | ------------------------------------------- |
| **Role**         | Perception, Memory, Reasoning, Orchestration | Actual execution (Git, Terminal, Shell)     |
| **Input**        | High-level intent ("fix the bug")            | Specific commands ("git commit -m '...'")   |
| **Output**       | Plans, strategies, decisions                 | File edits, git operations, command results |
| **Memory**       | Full episodic memory access                  | Ephemeral execution context                 |
| **Intelligence** | Intent-driven, context-aware                 | Stateless, deterministic execution          |

```
┌─────────────────────────────────────────────────────────────────┐
│                    omni run (The Commander)                     │
│                                                                 │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │ Perception  │ → │  Reasoning  │ → │   Orchestration     │   │
│  │ Build Ctx   │   │  LLM + Mem  │   │   Route → Execute   │   │
│  └─────────────┘   └─────────────┘   └─────────────────────┘   │
│         │               │                    │                  │
│         │               │                    ▼                  │
│         │               │         ┌─────────────────────┐       │
│         │               │         │  Decides: "Call    │       │
│         │               │         │  terminal.spawn     │       │
│         │               │         │  with command"      │       │
│         │               │         └─────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 omni run terminal (The Soldier)                 │
│                                                                 │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │  Receive    │ → │  Execute    │ → │   Return Result     │   │
│  │  Command    │   │  Precisely  │   │   (No thinking)     │   │
│  └─────────────┘   └─────────────┘   └─────────────────────┘   │
│                                                                 │
│  "I don't decide WHAT to do, I just DO it exactly as told"     │
└─────────────────────────────────────────────────────────────────┘
```

### Key Advantages of This Separation

| Capability          | Without Separation                 | With Commander/Soldier Model               |
| ------------------- | ---------------------------------- | ------------------------------------------ |
| **Memory**          | Commands forgotten after execution | All decisions archived to VectorDB         |
| **Attention**       | Full context in every command      | Rust Pruner compresses to ~45KB stable     |
| **Self-Correction** | No learning from mistakes          | Fast Path: User corrections → VectorDB     |
| **Intent-Driven**   | User must specify exact commands   | "Fix the bug" → Omni Loop plans & executes |

### Practical Examples

```bash
# THE COMMANDER: High-level intent, memory-enabled (Natural language instructions)
uv run omni run "Please use terminal to echo 'Hello Memory'"
# → Omni Loop reasons, recalls similar fixes, orchestrates solution
# → Archives entire session to memory for future recall

# THE SOLDIER: Direct tool execution (Bypass Agent)
uv run omni skill run "terminal.run_command" '{"cmd": "echo hello"}'
# → Executes exactly one command, returns output
# → No context, no memory, no learning (Pruner/Archiver NOT triggered)
```

### When to Use Each

| Task                             | Command                                     | Why                          |
| -------------------------------- | ------------------------------------------- | ---------------------------- |
| "Analyze this codebase"          | `omni run "..."`                            | Needs reasoning + memory     |
| "Create a new feature"           | `omni run "..."`                            | Planning + execution         |
| "Commit my changes"              | `omni run "..."`                            | Context-aware commit message |
| "Run this specific bash command" | `omni skill run "terminal.run_command" ...` | Direct execution             |
| "Run tests"                      | `omni skill run ...`                        | No intelligence needed       |
| "Tail a log file"                | `omni skill run ...`                        | Simple pass-through          |

### Interactive REPL

```bash
uv run omni run --repl
# Enter interactive mode for continuous task execution
# Each command benefits from accumulated context + memory
```

### Single Task Execution

```bash
uv run omni run "fix the bug" --steps 3
# Execute a single task with max 3 steps (ReAct Mode)
```

### Available Options

| Option              | Description                          |
| ------------------- | ------------------------------------ |
| `-s, --steps`       | Maximum steps (default: 10, max: 20) |
| `--json, -j`        | Output as JSON                       |
| `--repl`            | Enter interactive REPL mode          |
| `--verbose/--quiet` | Show/hide tool execution details     |

## Ingest Command

Index content into vector store for search and retrieval:

```bash
# Index documentation
omni ingest knowledge                    # Index docs/ (default)
omni ingest knowledge --dir assets/how-to  # Custom directory

# Index skills
omni ingest skills                       # Index skill tools
omni ingest skills --clear               # Full rebuild

# Index everything
omni ingest all                          # Knowledge + Skills

# Check status
omni ingest status                       # Show ingest status
omni ingest status --json                # JSON output
```

### Ingest Options

| Command     | Options                          | Description                  |
| ----------- | -------------------------------- | ---------------------------- |
| `knowledge` | `--dir`, `--json`, `--verbose`   | Index Markdown documentation |
| `skills`    | `--clear`, `--json`, `--verbose` | Index skill tools            |
| `all`       | `--clear`, `--json`, `--verbose` | Index all content            |
| `status`    | `--json`                         | Show ingest status           |

## Enriched Output

Omni Loop produces a **CCA Session Report** with detailed metrics:

```
┌─────────────────────────────────────────────────────────────────┐
│                  ✨ CCA Session Report ✨                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Task: fix the bug                                               │
│  Session ID: abc123                                             │
│                                                                 │
│  ┌────────────────┬────────────────┐                           │
│  │ Metric         │ Value          │                           │
│  ├────────────────┼────────────────┤                           │
│  │ Steps          │ 3              │                           │
│  │ Tools          │ 5              │                           │
│  │ Est. Tokens    │ ~1250          │                           │
│  └────────────────┴────────────────┘                           │
│                                                                 │
│  ┌────────────────┬────────────────┐                           │
│  │ Tool           │ Count          │                           │
│  ├────────────────┼────────────────┤                           │
│  │ git_status     │ 1              │                           │
│  │ read_files     │ 2              │                           │
│  │ write_file     │ 2              │                           │
│  └────────────────┴────────────────┘                           │
│                                                                 │
│  Reflection & Outcome:                                          │
│  Fixed the off-by-one error in the loop counter.               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Report Metrics

| Metric          | Description                     |
| --------------- | ------------------------------- |
| **Steps**       | Number of execution steps taken |
| **Tools**       | Total tool invocations          |
| **Est. Tokens** | Estimated token consumption     |
| **Tool Usage**  | Per-tool invocation counts      |

## Trinity Loop (Knowledge → Memory)

Omni Loop implements a complete read/write cycle:

```
1. Agent calls knowledge.search_project_knowledge
   └─ Returns: docs + hint "Try memory.search_memory"

2. Per system_context.xml, agent calls memory.search_memory
   └─ Returns: past experiences with similar patterns

3. Agent uses context to solve task

4. After completion, Note-Taker distills wisdom
   └─ Saves to memory via save_memory
```

## Trinity Architecture Integration

Omni Loop integrates with the **Trinity Architecture** layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    Omni Loop (CCA Runtime)                   │
│  Kernel → Router → Skills → Knowledge → Memory → MCP Tools  │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│  Trinity Architecture                                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Foundation (L1): Config, MCP, Utils                  │    │
│  │   → omni.foundation.config.settings                  │    │
│  │   → omni.foundation.mcp_core                         │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Core (L2): Kernel, Router, Skills, Knowledge         │    │
│  │   → omni.core.kernel.engine                          │    │
│  │   → omni.core.router                                 │    │
│  │   → omni.core.skills.discovery                       │    │
│  │   → omni.core.knowledge.librarian                    │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ MCP-Server (L3): Protocol handlers                   │    │
│  │   → omni.mcp.server                                  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Related Documentation

- [Kernel Architecture](../../architecture/kernel.md) - Microkernel engine
- [Router Architecture](../../architecture/router.md) - Semantic routing system
- [MCP-Server Architecture](../../architecture/mcp-server.md) - MCP protocol
- [Knowledge Matrix](knowledge-matrix.md) - Documentation RAG
