# Skill Tool Context Practices

> Reference practices for skill tools: avoid content truncation, prefer chunking and compression.
> Informed by Codex analysis and project design principles.

## Design Principles

### 1. No Content Truncation

**Truncation causes hallucination.** When you cut content arbitrarily (prefix-only, prefix+suffix, or mid-content), the LLM loses critical context and may infer incorrectly.

- **Do NOT**: Truncate content with `[...truncated...]` or similar
- **Do**: Deliver content in chunks/sessions so the LLM can read fully across multiple calls

### 2. Chunking Over Truncation

Prefer **multiple sessions/batches** over truncation:

- Use `session_id` + `batch_index` (or equivalent) for long content
- Each batch returns **complete** content (no mid-batch truncation)
- LLM reads batch 0, then batch 1, etc., until done

### 3. Compression Is OK

**Repomix-style compression** is acceptable:

- Filter noise (comments, boilerplate, irrelevant files)
- Omit redundant structure
- **Preserve core content integrity** — what remains is complete and understandable
- Do NOT arbitrarily cut in the middle of important content

### 4. Filtering vs Truncation

| Approach        | Description                                   | Acceptable? |
| --------------- | --------------------------------------------- | ----------- |
| **Filtering**   | Return top N results, each result is complete | Yes         |
| **Compression** | Repomix-style: omit noise, keep signal        | Yes         |
| **Truncation**  | Cut content at char/token limit, lose middle  | No          |

### 5. Two Distinct Scenarios (Both Valid)

| Scenario       | Source                | Goal                                                                                              | Content Need                             | Truncation                    |
| -------------- | --------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------------- | ----------------------------- |
| **Git commit** | `git diff`, `git log` | Extract basic info → reflect current commit situation and changes → write accurate commit message | Structure, file list, high-level summary | Acceptable (e.g. 8k chars)    |
| **Researcher** | Repomix, codebase     | Deep architecture/code analysis, understand patterns and design                                   | Full content for reasoning               | Not acceptable — use chunking |

Both scenarios are useful. The distinction: **git commit** is a different stage — we only need enough from diff/log to describe the commit accurately. **Researcher** needs full content to avoid hallucination.

---

## Skill Tool Audit

### Tools With Content Truncation (Fixed)

| Skill          | Tool             | Location          | Fix Applied                                                      |
| -------------- | ---------------- | ----------------- | ---------------------------------------------------------------- |
| **researcher** | git_repo_analyer | research_graph.py | `create_chunked_session` + multi-batch LLM analysis + synthesize |
| **researcher** | (internal)       | research.py       | Removed truncation; returns full repomix content                 |

### Tools With Acceptable Truncation (Summary-Only Scenario)

| Skill   | Tool         | Location          | Current                      | Why OK                                                                                                                                                                                                       |
| ------- | ------------ | ----------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **git** | smart_commit | prepare_result.j2 | Diff truncated to 8000 chars | **Different scenario from researcher.** Goal: extract basic info from diff/log → reflect commit situation and changes → write accurate commit message. Truncated diff provides enough structure and summary. |

### Tools With Chunking (Correct)

| Skill          | Tool             | Pattern                                                       |
| -------------- | ---------------- | ------------------------------------------------------------- |
| **knowledge**  | recall           | `action=start` → `session_id`; `action=batch` + `batch_index` |
| **crawl4ai**   | crawl_url        | Smart mode: skeleton → chunk_indices → fetch                  |
| **researcher** | git_repo_analyer | `chunked=true`: start → shard → synthesize                    |

### Tools With Filtering (OK)

| Skill          | Tool                         | Limit                             | Notes                                |
| -------------- | ---------------------------- | --------------------------------- | ------------------------------------ |
| knowledge      | recall                       | limit=5, max_chunks=15            | Result count, not content truncation |
| knowledge      | search, link_graph_toc, etc. | limit/max_results                 | Filtering                            |
| memory         | search_memory                | limit=5                           | Filtering                            |
| skill          | discover                     | limit=3                           | Filtering                            |
| advanced_tools | smart_search                 | 300 matches, `truncated` metadata | Filtering; matches are complete      |
| advanced_tools | batch_replace                | max_files=50                      | Scope limit                          |

### Tools To Review

| Skill        | Tool                | Risk                       | Action                                        |
| ------------ | ------------------- | -------------------------- | --------------------------------------------- |
| **omniCell** | nuShell             | Command output can be huge | Add chunked mode or guidance to use pipelines |
| **code**     | code_search         | Search results             | Verify no truncation of match content         |
| **writer**   | load_writing_memory | Returns full guidelines    | Usually small; monitor                        |

---

## Implementation Plan

### Phase 1: Researcher (Done)

**Implemented**: `create_chunked_session` + multi-batch LLM analysis.

- When repomix ≤ 28k chars: single LLM call (unchanged).
- When repomix > 28k: split into batches; LLM analyzes each batch; final synthesis step combines partial analyses.
- No truncation; full content delivered across batches.

### Phase 2: OmniCell (Implemented)

`omniCell.nuShell` now supports chunked delivery for large payloads:

- `chunked=true` (or `action=start`) creates a chunked session and returns `session_id`
- `action=batch` + `session_id` + `batch_index` fetches one complete batch
- Uses common library `ChunkedSessionStore` + `create_chunked_session`

Pipelines are still recommended to reduce unnecessary context volume.

### Phase 3: Knowledge Recall Session State (Implemented)

`knowledge.recall` action-based chunked workflow now uses `ChunkedSessionStore` for
`action=start`/`action=batch` state persistence (including cached full results).

### Phase 4: Researcher Session State (Implemented)

`researcher` chunked workflow now uses `WorkflowStateStore` for master and child
chunk sessions (`action=start|shard|synthesize`) with compatibility read-path for
older `ChunkedSessionStore` metadata payloads.

### Phase 5: Documentation

- Update each skill's SKILL.md with context practices
- Add "Context handling" section: chunked / filtering / compression
- Reference this document in CLAUDE.md or AGENTS.md

---

## Checklist for New Tools

When adding a skill tool that returns content to the LLM:

- [ ] Does it return content that can exceed ~10k tokens?
- [ ] If yes: implement chunked delivery (session_id, batch_index)
- [ ] If no: use conservative `limit` for filtering
- [ ] Never truncate content with `[...truncated...]`
- [ ] Compression (repomix-style) is OK; truncation is not

---

## Common Library

`omni.foundation.context_delivery` provides reusable strategies for both scenarios:

```python
from omni.foundation.context_delivery import (
    prepare_for_summary,   # Summary-only (git diff)
    ActionWorkflowEngine,  # Action-based multi-step workflows (start/approve/status)
    ChunkedSession,
    ChunkedSessionStore,
    WorkflowStateStore,
    create_chunked_session,  # Full-content (researcher)
)
```

| Scenario                       | Use                                                                   | Example                                  |
| ------------------------------ | --------------------------------------------------------------------- | ---------------------------------------- | ------- | ------- |
| **Summary-only**               | `prepare_for_summary(content, max_chars=8000)`                        | Git diff → commit message                |
| **Full-content**               | `create_chunked_session(content, batch_size=28000)`                   | Repomix → architecture analysis          |
| **Persistent start/batch**     | `ChunkedSessionStore("workflow").create(...); get_batch_payload(...)` | Skill tool `action=start                 | batch`  |
| **Persistent action workflow** | `WorkflowStateStore("workflow").save/load(...)`                       | Skill tool `action=start                 | approve | status` |
| **Action dispatch + guards**   | `ActionWorkflowEngine(...).dispatch(...)`                             | Common action validation/ID/state checks |

Skills choose the strategy by scenario. See `packages/python/foundation/src/omni/foundation/context_delivery/`.

---

## Benchmark & Regression Commands

### Developer Mode Build Rule

- Default local workflow should avoid unnecessary rebuilds during debug/perf loops.
- Reinstall Rust Python bindings only when binding-related Rust/Python bridge code changed:
  `uv sync --reinstall-package omni-core-rs`
- Do not rerun reinstall commands when no relevant code changed.

Use these commands to verify performance and correctness after migration to common libraries:

```bash
# Knowledge recall benchmark (MCP path, warm phase enabled by default)
uv run python scripts/benchmark_knowledge_recall.py --tools knowledge.recall --runs 5 --json

# Recall phase profiling (init/embed/search/dual-core breakdown)
uv run python scripts/recall_profile_phases.py --query x --limit 5

# Verbose CLI monitor (must use -v): check Retrieval Signals row budget
omni skill run knowledge.recall '{"query":"x","chunked":false,"limit":2}' -v

# CI/local perf gate (P95 + RSS peak + row_budget memory signal)
uv run python scripts/knowledge_recall_perf_gate.py --runs 5 --warm-runs 1 --retrieval-mode auto

# One-command local gate (runs auto + graph_only and writes both reports)
just ci-local-recall-gates

# Graph-only perf gate (no embedding dependency)
uv run python scripts/knowledge_recall_perf_gate.py --runs 5 --warm-runs 1 --retrieval-mode graph_only

# Optional threshold overrides
OMNI_KNOWLEDGE_RECALL_P95_MS=2500 \
OMNI_KNOWLEDGE_RECALL_RSS_PEAK_DELTA_MB=320 \
OMNI_KNOWLEDGE_RECALL_ROW_BUDGET_RSS_PEAK_DELTA_MB=320 \
OMNI_KNOWLEDGE_RECALL_ROW_BUDGET_MEMORY_OBSERVED_MIN=1 \
uv run python scripts/knowledge_recall_perf_gate.py --runs 5 --warm-runs 1 --retrieval-mode auto

# Write machine-readable gate report JSON
uv run python scripts/knowledge_recall_perf_gate.py \
  --runs 5 --warm-runs 1 --retrieval-mode auto \
  --json-output .run/reports/knowledge-recall-perf/auto.json

# CI uploads artifacts from:
# .run/reports/knowledge-recall-perf/auto.json
# .run/reports/knowledge-recall-perf/graph_only.json

# Checkpoint regression (Python runtime + LangGraph saver/state + schema API)
uv run pytest \
  packages/python/foundation/tests/unit/runtime/test_checkpoint.py \
  packages/python/foundation/tests/unit/api/test_checkpoint_schema.py \
  packages/python/agent/tests/unit/test_langgraph/test_core_state.py \
  packages/python/agent/tests/unit/test_langgraph/test_checkpoint_saver.py -q

# Checkpoint regression (Rust core)
CARGO_TARGET_DIR=/tmp/omni-target-checkpoint \
  cargo test -p omni-vector --test test_checkpoint -- --nocapture
```

---

## Related

- [Context Optimization](../explanation/context-optimization.md) — Agent-level pruner (archive compression)
- [Knowledge Recall](../../assets/skills/knowledge/SKILL.md) — Reference chunked workflow
- [Researcher SKILL](../../assets/skills/researcher/SKILL.md) — Sharded analysis
