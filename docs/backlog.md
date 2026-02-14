# Omni-Dev-Fusion Backlog

> **Project progress is determined by feature name only.** Track status by the feature headings below. No phases, no stage numbers—just priorities and feature names.

---

## Legend

| Status        | Meaning                  |
| ------------- | ------------------------ |
| `Todo`        | Not started              |
| `In Progress` | Actively being worked on |
| `Blocked`     | Waiting on dependencies  |
| `Deferred`    | Out of scope for now     |
| `Done`        | Completed                |

---

## High Priority

### Omni-Vector Phase 2 (out-of-scope follow-ups)

Items deferred from [milestone 2026-02 omni-vector](milestones/2026-02-omni-vector-optimization-and-arrow-native.md), now tracked here.

| Task                         | Status | Description                                                                                                                 |
| ---------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------- |
| **Tantivy Writer reuse**     | Done   | Implemented: KeywordIndex caches `RefCell<Option<IndexWriter>>`, reused across bulk_upsert/upsert_document/index_batch      |
| **simd-json (optional)**     | Done   | Added: writer_impl uses simd_json::serde::from_slice for MetadataExtract/Value, fallback to serde_json on error             |
| **Connection pool**          | Done   | Implemented: `DatasetCache` + LRU eviction, `new_with_cache_options(..., DatasetCacheConfig { max_cached_tables })`; see §2 |
| **Async index build**        | Done   | `create_index_background(table_name)` implemented (spawns index build, returns immediately); see §3                         |
| **Compressed serialization** | Done   | Lance V2_1 storage via `default_write_params()` for Dataset::write and append; see §4                                       |

---

## Medium Priority

_(none)_

---

## Low Priority

### Developer Experience

Improvements that make development easier but aren't blocking core functionality.

| Task                    | Status | Description                                                          |
| ----------------------- | ------ | -------------------------------------------------------------------- |
| **Tutorial: New Skill** | Done   | Covered by **skill generator**: `omni skill generate` (Jinja2 + LLM) |

---

### Agent TUI / Visual Thinking Pipeline _(deferred)_

Interactive TUI to visualize the Trinity Architecture; not in scope for now.

| Task                      | Status   | Description                                                  |
| ------------------------- | -------- | ------------------------------------------------------------ |
| **Event Bus System**      | Deferred | Create EventBus for publishing Trinity phase events          |
| **Textual TUI App**       | Deferred | Build Textual-based TUI with thinking pipeline visualization |
| **LangGraph Integration** | Deferred | Connect LangGraph node transitions to event stream           |
| **CLI Integration**       | Deferred | Add `--tui` mode to `omni run` command                       |
| **Interactive Features**  | Deferred | F1 Help, F2 History, F3 Stats, pause/resume, Ctrl+C to abort |

---

## Completed

| Feature                             | Date       | Notes                                                    |
| ----------------------------------- | ---------- | -------------------------------------------------------- |
| **TikToken Integration**            | 2026-02-04 | Rust-only omni-tokenizer + PyO3, no Python fallback      |
| **Enhanced Test-Kit**               | 2026-02-04 | Layer markers, assertion helpers, demo tests             |
| **Testing Layer Strategy**          | 2026-02-04 | @unit, @integration, @cloud markers in omni.test_kit     |
| **Tool Schema Definition**          | 2026-02-04 | tool.schema.yaml in packages/shared/schemas/             |
| **Unified Response Format**         | 2026-02-04 | ToolResponse with status, data, error_code, metadata     |
| **Error Code System**               | 2026-02-04 | CoreErrorCode enum (1xxx-9xxx categories)                |
| **Provider Pattern**                | 2026-02-04 | VariantProvider, VariantRegistry in omni.core.skills     |
| **Robust Task Workflow**            | 2026-01-29 | Graph-based workflow with Reflection & Discovery Fixes   |
| **Permission Gatekeeper**           | 2026-01-21 | Zero Trust security with Rust PermissionGatekeeper       |
| **Context Optimization**            | 2026-01-21 | ContextPruner + ContextManager for token diet            |
| **Skill Ecosystem Standardization** | 2026-01-20 | Template upgrades, writer cleanup, skill check --example |
| **Core Omni Refactoring**           | 2026-01-19 | LoopState, ActionGuard, AdaptivePlanner                  |
| **Anti-Confusion Loop**             | 2026-01-19 | Prevents repeated file reads                             |
| **Adaptive Planning**               | 2026-01-18 | Dynamic step estimation                                  |
| **NoteTaker Optimization**          | 2026-01-18 | Token reduction from 4000 to 500                         |

---

## Architecture Improvements (Feb 2026)

| Feature                          | Status | Description                                         |
| -------------------------------- | ------ | --------------------------------------------------- |
| **Provider Pattern**             | `Done` | VariantProvider, VariantRegistry for skill variants |
| **Tool Schema Definition**       | `Done` | tool.schema.yaml in packages/shared/schemas/        |
| **Testing Layer Strategy**       | `Done` | @unit, @integration, @cloud markers                 |
| **Unified Response Format**      | `Done` | ToolResponse with ResponseStatus enum               |
| **Error Code System**            | `Done` | CoreErrorCode with 1xxx-9xxx categories             |
| **Enhanced Test-Kit**            | `Done` | assert helpers, layer markers, fixtures             |
| **Shared Type Definition**       | `Done` | Pydantic types in core module                       |
| **Knowledge System Enhancement** | `Done` | omni-knowledge Rust crate + PyO3 bindings           |

**Related Files:**

- `packages/python/core/src/omni/core/responses.py`
- `packages/python/core/src/omni/core/errors.py`
- `packages/python/core/src/omni/core/skills/variants.py`
- `packages/python/core/src/omni/core/testing/layers.py`
- `packages/python/test-kit/src/omni/test_kit/asserts.py`
- `packages/python/core/src/omni/core/shared/skill_metadata_schema.py`
- `packages/python/core/src/omni/core/shared/tool_schema.py`

**Knowledge System Files:**

- `packages/rust/crates/omni-knowledge/src/lib.rs`
- `packages/rust/crates/omni-knowledge/src/types.rs`
- `packages/rust/crates/omni-knowledge/src/storage.rs`
- `packages/rust/crates/omni-knowledge/tests/test_knowledge.rs`
- `packages/python/core/src/omni/core/knowledge/types.py`
- `packages/python/core/tests/units/knowledge/test_librarian.py`
