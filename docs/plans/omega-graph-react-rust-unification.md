# Omega + Graph + Loop/ReAct: Rust Unification Blueprint

> Goal: converge execution into a single Rust runtime (`omni-agent`) by fusing Omega reasoning, Graph planning, ReAct tool execution, and authoritative Xiuxian-Qianhuan injection, then progressively remove Python runtime paths.
>
> Detailed companion: [Xiuxian-Qianhuan Injection + Memory Self-Evolution + Reflection](./knowledge-injection-memory-evolution-architecture.md)
>
> LinkGraph execution companion (primary core track): [LinkGraph PPR Algorithm Spec](./link-graph-ppr-algorithm-spec.md)
>
> Execution sequence companion: [Xiuxian-Qianhuan Implementation Rollout Plan](./xiuxian-qianhuan-implementation-rollout.md)

## 1. Scope and Boundaries

- In scope:
  - Unify Omega, Graph, and ReAct under one Rust execution kernel.
  - Keep Python as MCP tool provider during transition.
  - Move session windowing, compression, and memory self-evolution to Rust-first execution path.
- Out of scope:
  - Rewriting every tool/skill from Python to Rust immediately.
  - Breaking existing MCP contracts during migration.

## 2. Target Architecture

```mermaid
flowchart LR
  U[User / Channel] --> G[omni-agent gateway/repl]
  G --> R[Unified Rust Runtime Kernel]

  R --> O[Omega Deliberation Engine]
  O --> I[Xiuxian-Qianhuan Assembler]
  R --> P[Graph Planning Engine]
  R --> X[ReAct Execution Engine]

  X --> M[MCP Client Pool]
  M --> PY[Python MCP Tool Servers (transition)]
  M --> RS[Rust-native MCP servers]

  R --> W[omni-window]
  R --> MM[omni-memory]
  R --> KG[xiuxian-wendao / link-graph]
  R --> SPI[Session Prompt Injection XML]

  W --> I
  MM --> I
  KG --> I
  SPI --> I
  I --> P
  I --> X
  W --> MM
  MM --> R
  KG --> R
```

## 3. Unified Runtime Workflow

1. Intake:
   - Receive request and resolve `session_id` (channel/chat/thread aware).
   - Load bounded context from `omni-window`.
2. Omega deliberation:
   - Evaluate complexity and choose execution route (`react` direct vs `graph` first).
   - Produce context policy (what to inject, max size, ordering, role-mix profile, injection mode).
3. Xiuxian-Qianhuan context assembly (knowledge inject role):
   - Assemble typed context blocks from:
     - session prompt injection XML (operator/session scoped),
     - memory recall context (`omni-memory`, MemRL-style),
     - bounded summaries/window state (`omni-window`),
     - knowledge context (`xiuxian-wendao`, link-graph).
   - Compose scenario-specific mixed-role prompts (for example debug/recovery/architecture reflection packs).
   - Apply deterministic ordering and token budget before execution.
4. Execution routing:
   - Fast/simple request goes to ReAct execution with assembled context.
   - Complex request triggers Graph plan synthesis first, then ReAct/tool execution.
5. Omega quality gating:
   - Evaluate plan quality, risk, and tool ordering.
   - Repair plan before execution when quality checks fail.
6. ReAct execution:
   - Execute tool loop with budget, retries, and structured error taxonomy.
   - Call tools through MCP client pool only.
7. Self-evolution update:
   - Store episode outcome and feedback in `omni-memory`.
   - Persist session window snapshots and summary segments.
8. Response:
   - Emit user-facing answer plus structured observability events.

## 3.1 Xiuxian-Qianhuan: Architectural Role

- Ownership:
  - Owned by Rust runtime, policy decided by Omega.
  - Not owned by Python runtime loop.
- Responsibility:
  - Deliver high-signal context to Graph/ReAct without changing model weights.
  - Provide flexible injection modes (`single`, `classified`, `hybrid`) and mixed-role composition.
  - Keep context bounded, session-scoped, and auditable.
- Non-goals:
  - No free-form hidden prompt mutation in random call sites.
  - No bypass of context policy on deterministic execution paths.
- Contract direction:
  - Introduce typed `PromptContextBlock` and `InjectionPolicy` contracts.
  - Keep tool payload contracts stable; pass injected context through explicit fields only when schema supports it.

## 4. Feature-Name Roadmap (Backlog-Aligned)

Project progress must be tracked by feature name (not phase/stage labels). Recommended feature names:

| Feature name                             | Definition of done                                                                        |
| ---------------------------------------- | ----------------------------------------------------------------------------------------- |
| **Unified Rust Execution Kernel**        | One Rust entry for channel/repl/gateway execution; no Python runtime loop on hot path.    |
| **Graph Planning Engine (Rust)**         | Graph planning API runs inside Rust runtime and produces stable, testable plan contracts. |
| **Omega Deliberation Engine (Rust)**     | Quality gates and plan-repair logic run in Rust with structured outputs.                  |
| **ReAct Tool Runtime (Rust)**            | Tool-call loop, retry, budget, and failure policy consolidated in Rust.                   |
| **Session Window Compression (Rust)**    | Predictable context compression and restore strategy backed by `omni-window`.             |
| **Memory Self-Evolution Runtime (Rust)** | Outcome feedback and recall adaptation persisted via DB-backed `omni-memory`.             |
| **Python Runtime Decommissioning**       | Python side is MCP tool service only; no duplicated runtime loop entrypoints.             |

## 5. Migration Rules

- Single authority:
  - Runtime orchestration authority is Rust.
  - Python authority is tool implementation behind MCP.
- Thin orchestrator rule:
  - `omni-agent` remains orchestration-only.
  - Memory lifecycle/revalidation/promotion core logic must live in Rust memory package(s), not inside agent runtime modules.
- MCP interoperability rule:
  - Keep `skill memory` as MCP-facing tool surface for external clients.
  - `skill memory` acts as a thin facade to Rust memory core (via bindings/bridge), without duplicating policy logic.
- Prompt/context authority:
  - Prompt/knowledge injection authority is Rust `Xiuxian-Qianhuan Assembler`.
  - Python side must not inject hidden runtime prompt context.
- No dual-loop fallback:
  - Do not keep long-term “Rust loop + Python loop” behavior parity mode.
  - Keep one execution contract and migrate callers to it.
- Contract-first evolution:
  - Keep MCP `tools/list` and `tools/call` behavior stable while internals move.
  - Version schemas when changing output shape.
- Isolation by default:
  - Session partition key is mandatory (`channel:chat_id:thread_id` when applicable).
  - Window snapshots and memory feedback must be session-scoped.

## 5.1 Boundary Corrections (Roadmap Clarification)

- `memory`:
  - short-term operational runtime memory (Rust core owned)
  - exposed through MCP memory skill facade for interoperability
- `knowledge`:
  - long-term durable knowledge interface (MCP knowledge skill)
- `omni-agent`:
  - orchestration only; no embedding of memory lifecycle policy logic

## 5.2 Data Plane Standard (Valkey + LanceDB + Arrow)

- `Valkey`:
  - hot runtime state, dedup/idempotency, stream events, and high-concurrency caches.
- `LanceDB`:
  - durable retrieval state, tool/knowledge indexes, episodic memory persistence, replay analytics.
- `Arrow`:
  - canonical inter-stage schema for ranking/gate traces with zero-copy batch movement.

Rule:

- no hot-path JSON file state source;
- read-through/write-through flows must follow `Valkey -> LanceDB` boundaries with Arrow contracts.

## 5.3 Discover Confidence Contract

`skill.discover` and route selection must preserve calibrated ranking metadata end-to-end:

- `score`
- `final_score`
- `confidence` (`high` | `medium` | `low`)
- `ranking_reason`
- `usage_template`

Policy:

- `high`: direct recommendation allowed
- `medium`: top-k + clarification
- `low`: refine intent before execution

## 6. Quality Gates

- Correctness:
  - Cross-session isolation matrix (multi-group, multi-thread, mixed `/reset` and `/resume` concurrency).
  - Deterministic parser and command routing tests in dedicated `tests/` modules.
  - Prompt injection determinism tests (same inputs => same ordered context blocks).
- Reliability:
  - MCP startup and reconnect resilience under slow-start and transient failures.
  - No silent exits; structured startup/shutdown diagnostics.
- Performance:
  - Baseline and regression benchmark for p50/p95 latency, failure rate, and memory peak.
  - Concurrent-session load tests for gateway mode.
- Observability:
  - Structured events for session lifecycle, snapshot operations, memory recall/update, MCP call duration, and tool failures.

## 7. Python Runtime Removal End-State

- End-state contract:
  - `omni-agent` is the only runtime orchestrator.
  - Python process provides MCP tools and supporting services only.
- Cleanup targets:
  - Remove Python runtime loop command paths after Rust parity is proven.
  - Keep compatibility wrappers only where they map directly to Rust commands.
- Acceptance rule:
  - Removal is complete only after black-box suites pass on multi-session, multi-channel, and memory self-evolution scenarios.

## 8. Contract Seeds (Next)

- `OmegaDecision`:
  - route (`react` | `graph`)
  - risk level
  - injection policy (enabled blocks, max chars/tokens, ordering strategy)
- `PromptContextBlock`:
  - source (`memory_recall` | `session_xml` | `window_summary` | `knowledge`)
  - priority, size, session scope
  - payload (rendered text/XML)
- `TurnTrace`:
  - selected route, tool chain, retries, latency, failure taxonomy
  - injection stats (`blocks_used`, `chars_injected`, dropped-by-budget)
- `ReflectionRecord`:
  - outcome, failure category, corrective action
  - memory credit update and next-turn strategy hint
- `DiscoverMatch`:
  - tool id, usage template, score/final_score/confidence, ranking_reason, schema digest
