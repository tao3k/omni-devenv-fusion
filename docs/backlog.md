# Omni-Dev-Fusion Backlog

> Feature-based task tracking. No phases, just priorities.

---

## Legend

| Status        | Meaning                  |
| ------------- | ------------------------ |
| `Todo`        | Not started              |
| `In Progress` | Actively being worked on |
| `Blocked`     | Waiting on dependencies  |
| `Done`        | Completed                |

---

## High Priority

_(No active high priority items - see Medium Priority below)_

---

## Medium Priority

### Schema-Driven Security (Permission Gatekeeper)

Implement permission boundaries for skills before allowing external/untrusted tools.

| Task                         | Status | Description                                                                    |
| ---------------------------- | ------ | ------------------------------------------------------------------------------ |
| **Define Permission Schema** | `Done` | Added `permissions` field to Rust `SkillMetadata` (auto-generates JSON Schema) |
| **Permission Validator**     | `Done` | Rust `PermissionGatekeeper` + Python `SecurityValidator` wrapper               |
| **Integration Tests**        | `Done` | 14 Rust tests + 12 Python tests passing                                        |

**Architecture:**

- **Rust Core**: `omni-security` crate with `PermissionGatekeeper.check()`
- **Python Wrapper**: `omni.core.security.SecurityValidator`
- **Schema**: Generated from Rust via `schemars` derive macro

**Related Files:**

- `packages/rust/crates/omni-security/src/lib.rs`
- `packages/rust/bindings/python/src/security.rs`
- `packages/python/core/src/omni/core/security/`
- `docs/explanation/permission-gatekeeper.md`

---

### Context Optimization (The Token Diet)

Reduce token usage in the CCA loop without losing context quality.

| Task                          | Status | Description                                                |
| ----------------------------- | ------ | ---------------------------------------------------------- |
| **Smart Context Trimming**    | `Done` | Implement `ContextPruner` with tiered priority layers      |
| **Auto-Summarization API**    | `Done` | Add `ContextManager.prune_with_summary()` method           |
| **Vector Index Optimization** | `Done` | Adaptive IVF-FLAT partitions (256 vectors/partition)       |
| **TikToken Integration**      | `Todo` | Replace char-based token estimation with accurate tiktoken |

**Documentation:**

- [Context Optimization Guide](./explanation/context-optimization.md)
- [Vector Index Guide](./explanation/vector-index.md)
- [Rust-Python Bridge](./explanation/rust-python-bridge.md)

**Related Files:**

- `packages/python/agent/src/omni/agent/core/context/pruner.py`
- `packages/python/agent/src/omni/agent/core/context/manager.py`
- `packages/python/agent/src/omni/agent/core/omni.py`
- `packages/python/agent/tests/unit/test_context/`
- `packages/rust/crates/omni-vector/src/index.rs`
- `packages/rust/crates/omni-vector/src/search.rs`

---

## Low Priority

### Developer Experience

Improvements that make development easier but aren't blocking core functionality.

| Task                    | Status | Description                                          |
| ----------------------- | ------ | ---------------------------------------------------- |
| **Skill Generator CLI** | `Todo` | Interactive CLI for creating new skills with prompts |
| **Hot Reload Logs**     | `Todo` | Improve logging for skill hot-reload events          |
| **Dashboard Metrics**   | `Todo` | Real-time dashboard for session metrics              |
| **Tutorial: New Skill** | `Todo` | Step-by-step guide for creating a custom skill       |

---

### Agent TUI / Visual Thinking Pipeline

Interactive TUI to visualize the Trinity Architecture thinking process (Sniffing → Recall → Plan → Act).

| Task                      | Status | Description                                                  |
| ------------------------- | ------ | ------------------------------------------------------------ |
| **Event Bus System**      | `Todo` | Create EventBus for publishing Trinity phase events          |
| **Textual TUI App**       | `Todo` | Build Textual-based TUI with thinking pipeline visualization |
| **LangGraph Integration** | `Todo` | Connect LangGraph node transitions to event stream           |
| **CLI Integration**       | `Todo` | Add `--tui` mode to `omni run` command                       |
| **Interactive Features**  | `Todo` | F1 Help, F2 History, F3 Stats, pause/resume, Ctrl+C to abort |

**Architecture:**

- **Event System**: Lightweight pub/sub for SNIFFING → RECALL → PLAN → ACT → REFLECT events
- **UI Framework**: Textual (interactive TUI companion to Rich)
- **Layout**: Left stats panel + Right thinking pipeline + Bottom command input

**Related Files (to be created):**

- `packages/python/agent/src/omni/agent/events.py`
- `packages/python/agent/src/omni/agent/core/events.py`
- `packages/python/agent/src/omni/agent/tui/`
- `packages/python/agent/src/omni/langgraph/tui_integration.py`

**Usage:**

```bash
uv run omni run "git commit" --tui    # Start TUI mode
```

**Plan File:**

- `.claude/plans/partitioned-cooking-leaf.md`

---

## Completed

| Feature                             | Date       | Notes                                                    |
| ----------------------------------- | ---------- | -------------------------------------------------------- |
| **Permission Gatekeeper**           | 2026-01-21 | Zero Trust security with Rust PermissionGatekeeper       |
| **Context Optimization**            | 2026-01-21 | ContextPruner + ContextManager for token diet            |
| **Skill Ecosystem Standardization** | 2026-01-20 | Template upgrades, writer cleanup, skill check --example |
| **Core Omni Refactoring**           | 2026-01-19 | LoopState, ActionGuard, AdaptivePlanner                  |
| **Anti-Confusion Loop**             | 2026-01-19 | Prevents repeated file reads                             |
| **Adaptive Planning**               | 2026-01-18 | Dynamic step estimation                                  |
| **NoteTaker Optimization**          | 2026-01-18 | Token reduction from 4000 to 500                         |

---

## How to Use This Backlog

1. **Pick a task** from High Priority
2. **Create a branch** with descriptive name: `feature/skill-template-update`
3. **Complete the work** with tests
4. **Update this file** to mark as `Done` with date
5. **Commit** with: `docs(backlog): complete Skill Ecosystem Standardization`

---

_Built on standards. Not reinventing the wheel._
