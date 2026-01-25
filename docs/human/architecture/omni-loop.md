# Omni Loop (CCA Runtime)

> **Status**: Active (Current)
> **Version**: v2.0 | 2026-01-24

## Overview

Omni Loop is the **CCA (Cognitive Code Agent) Runtime** that integrates all system components into a cohesive agent execution environment.

### Core Components

| Component      | Purpose                                               |
| -------------- | ----------------------------------------------------- |
| **ReAct Loop** | Execute tasks via Observe-Decide-Act-Reflect cycle    |
| **Router**     | Semantic routing to select appropriate skills         |
| **Librarian**  | RAG-powered knowledge retrieval                       |
| **Note-Taker** | Session reflection & wisdom distillation              |
| **Kernel**     | Tool execution via @skill_command decorated functions |

## CCA Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│                      CCA Runtime Cycle                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│    │ Observe  │ ─► │  Orient  │ ─► │  Decide  │               │
│    │ Context  │    │  Route   │    │  LLM     │               │
│    └──────────┘    └──────────┘    └──────────┘               │
│         ▲                                     │                │
│         │                                     ▼                │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│    │ Reflect  │ ◄── │   Act    │ ◄── │  Tool    │               │
│    │  Wisdom  │    │ Execute  │    │  Call    │               │
│    └──────────┘    └──────────┘    └──────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Cycle Phases

1. **Observe**: Build layered context (skills + knowledge + memory)
2. **Orient**: Semantic routing to select appropriate skills
3. **Decide**: LLM reasoning with context
4. **Act**: Execute tools via JIT loader
5. **Reflect**: Distill wisdom and save to memory

## Trinity Architecture Integration

Omni Loop implements the **Trinity Architecture** with three logical roles:

| Role             | Responsibility         | Example Tools             |
| ---------------- | ---------------------- | ------------------------- |
| **Orchestrator** | Planning & Strategy    | Context assembly, Routing |
| **Coder**        | Reading & Writing      | File operations, Search   |
| **Executor**     | Execution & Operations | Git, Terminal, Shell      |

## CLI Usage

### Interactive REPL

```bash
uv run omni run --repl
# Enter interactive mode for continuous task execution
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
