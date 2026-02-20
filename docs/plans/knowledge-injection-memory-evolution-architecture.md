# Xiuxian-Qianhuan Injection + Memory Self-Evolution + Reflection (Rust Architecture Draft)

> Status: Draft (Architecture only, no implementation changes in this document)
> Date: 2026-02-20
> Scope: Define a Rust-first architecture that unifies Xiuxian-Qianhuan typed injection, MemRL-style memory evolution, and reflection feedback under one runtime contract.

## 1. Goals

- Build a **typed prompt/knowledge injection system** in Rust.
- Keep injection **atomic**, **bounded**, and **auditable** per session/turn.
- Support **multi-role mixed prompt injection** for scenario-specific reflection and execution quality.
- Connect injection directly with:
  - memory recall,
  - reflection,
  - self-evolution feedback.
- Avoid hidden Python-side runtime prompt mutation.

## Naming

- System codename: `Xiuxian-Qianhuan`
- Scope: the runtime prompt/knowledge injection system capable of role transformation and mixed-domain composition.
- Technical contracts remain explicit and stable:
  - `PromptContextBlock`
  - `InjectionPolicy`
  - `InjectionSnapshot`
  - `RoleMixProfile`

## 2. Non-Goals

- Rewriting all MCP tools in Rust now.
- Breaking MCP `tools/list` and `tools/call` contracts.
- Introducing a second runtime orchestration loop.

## 3. Layer Boundaries

1. `Omega` (policy layer)

- Chooses route: `react` vs `graph`.
- Chooses injection policy:
  - category budgets,
  - max chars/tokens,
  - ordering and dedupe mode.

2. `Xiuxian-Qianhuan Injection Engine` (assembly layer)

- Builds typed prompt context from multiple sources.
- Applies deterministic ordering and budget trimming.
- Produces one immutable `InjectionSnapshot` per turn.

3. `Graph/ReAct` (execution layer)

- Consume the built snapshot.
- Run planning/execution only.
- No ad-hoc runtime prompt mutation.

4. `Memory Self-Evolution` (learning layer)

- Uses execution result + reflection to update recall credit/Q-values.
- Writes feedback for next-turn injection policy tuning.

## 3.1 Package Placement (Hard Constraint)

- Memory core logic must **not** live in `omni-agent`.
- `omni-agent` is orchestration-only and consumes memory via trait/interface.
- Short-term memory lifecycle, 3-in-1 revalidation, purge/promotion policy, and state transitions belong to Rust-only memory package(s):
  - primary: `packages/rust/crates/omni-memory`
  - optional split (if needed): `omni-memory-lifecycle`, `omni-memory-reflection`
- `knowledge` skill remains MCP-facing long-term knowledge interface and is not the runtime short-term memory engine.

## 3.2 Memory Exposure Model (Core + Tool Facade)

- `Rust memory` is the core engine (single source of truth):
  - lifecycle state machine
  - 3-in-1 (ReAct+Graph+Omega) revalidation
  - purge/promotion decisions
- `skill memory` remains useful and should be kept as an MCP-facing tool facade:
  - callable from any MCP-compatible client
  - implemented as thin adapter via bindings/bridge to Rust memory core
  - must not duplicate memory policy logic
- Rule:
  - policy and state transitions in core,
  - exposure and interoperability in skill facade.

## 3.3 Corrected Misconceptions (Canonical)

This architecture replaces earlier ambiguous interpretations:

- Misconception: `memory` is long-term knowledge storage.
  - Correct: `memory` is short-term operational memory with purge/revalidation lifecycle.
- Misconception: `knowledge` and `memory` can share one policy surface.
  - Correct: `knowledge` is durable curated knowledge; `memory` is transient runtime context.
- Misconception: memory policy can live in agent runtime modules.
  - Correct: memory policy/state transitions live in Rust memory core package(s); `omni-agent` is orchestration-only.
- Misconception: MCP memory tools own memory policy.
  - Correct: MCP memory tools are facade/interop surface; policy remains in Rust core.

## 3.4 Data Plane Boundaries (Mandatory)

- `Valkey`:
  - hot session/runtime state
  - dedup/idempotency
  - stream events and fast counters
  - discover short-lived cache
- `LanceDB`:
  - durable tool/knowledge indexes
  - episodic memory persistence
  - replay and benchmark analytics source
- `Arrow`:
  - canonical batch schema between retrieval, ranking, and gate decisions

Rule:

- Prompt assembly and memory gate logic may read from both planes,
  but must not bypass data-plane contracts through ad-hoc JSON files in hot paths.

## 4. Typed Contracts

## 4.1 PromptContextBlock

Required fields:

- `block_id`: stable identifier for dedupe/audit
- `category`: one of:
  - `safety`
  - `policy`
  - `session_injection`
  - `memory_recall`
  - `knowledge`
  - `workflow`
  - `tooling`
  - `reflection`
- `priority`: numeric ordering key
- `payload`: rendered text/XML payload

Optional fields:

- `source`: producer marker (`knowledge.recall`, `session.inject`, etc.)
- `tags`: classification labels
- `ttl_turns`: auto-expire policy
- `trace_refs`: related event IDs

## 4.2 InjectionPolicy

- `max_blocks`
- `max_chars` (and/or token budget)
- `category_cap` map (`memory_recall <= n`, etc.)
- `ordering_strategy`:
  - `priority_then_category`
  - `fixed_category_order`
- `dedupe_strategy`:
  - `block_id`
  - `source+category`

## 4.3 InjectionSnapshot

- `session_id`
- `turn_id`
- `policy_applied`
- `blocks_used[]`
- `dropped_blocks`
- `truncated_blocks`
- `chars_injected`
- `created_at`

This snapshot is immutable and becomes the only prompt context authority for that turn.

## 4.4 ReflectionRecord

- `turn_id`
- `outcome` (`success` | `failure` | `partial`)
- `failure_class` (tool error, policy error, timeout, etc.)
- `corrective_action`
- `recall_credit_delta`
- `next_turn_hint`

## 4.5 RoleMixProfile

Defines scenario-adaptive mixed-role prompt composition selected by Omega.

Fields:

- `profile_id`: stable profile name (`debug_reflection`, `recovery_reflection`, `architecture_reflection`, etc.)
- `roles[]`: ordered role list (for example `Debugger`, `FailureAuditor`, `TestVerifier`)
- `weights[]`: optional role influence weights
- `constraints[]`: explicit policy/guardrail constraints for this profile
- `activation_reason`: why this profile was selected (complexity/risk/failure class)
- `mode`: injection mode (`single`, `classified`, `hybrid`)

## 4.6 Discover and Routing Contract

Tool discovery and route governance must expose calibrated fields for policy control:

- `score`
- `final_score`
- `confidence` (`high`, `medium`, `low`)
- `ranking_reason`
- `usage_template`

Behavior policy:

- `high`: direct route recommendation
- `medium`: return candidates with required clarification
- `low`: block execution and force intent refinement

## 5. Atomic Injection Workflow

1. Intake turn and resolve `session_id`.
2. Omega computes `InjectionPolicy`.
3. Collect candidate blocks from:
   - session XML injection,
   - memory recall,
   - knowledge retrieval,
   - window summaries,
   - operator policy blocks.
4. Build one `InjectionSnapshot` atomically.
5. Pass snapshot to Graph/ReAct execution.
6. Run reflection and create `ReflectionRecord`.
7. Apply memory evolution update using:
   - outcome,
   - reflection signal,
   - recalled candidate credit.

## 6. Macro-Oriented API Plan (Rust)

Goal: reduce call-site boilerplate and validation bugs.

Planned macro surface:

- `inject_block!()`:
  - typed block creation with compile-time required fields
- `inject_policy!()`:
  - policy declaration with explicit limits
- `inject_snapshot!()`:
  - atomic assembly from block list + policy
- `inject_role_mix!()`:
  - typed role-mix profile construction and validation

## 6.1 Injection Modes (Flexible by Design)

The injector must support multiple composition modes:

- `single`:
  - one compact injection block for low-complexity/focused tasks
- `classified`:
  - category-aware injection (`memory_recall`, `knowledge`, `reflection`, etc.) with per-category budgets
- `hybrid`:
  - role-mix + classified context blocks in one snapshot

Mode selection is owned by Omega policy.

## 6.2 Role-Mix Composition Rules

- Role-mix is a first-class contract, not free-form prompt text.
- Each role contributes typed constraints/objectives, merged deterministically.
- Conflict resolution is explicit:
  - priority ordering
  - hard constraints first
  - budget trimming after merge
- Result is serialized into the same immutable `InjectionSnapshot`.

Example intent (API shape only):

```rust
let block = inject_block!(
    category = knowledge,
    priority = 80,
    source = "knowledge.recall",
    tags = ["rag", "link-graph"],
    payload = "<qa>...</qa>"
);
```

## 7. Integration with MemRL Self-Evolution

- Recall remains two-phase (semantic + utility/Q rerank).
- Injection snapshot records which recalled blocks were injected.
- Reflection outcome updates:
  - recall feedback bias,
  - candidate credit weights,
  - future policy (tighten/broaden recall budget).

This keeps model weights frozen while memory evolves online.

## 7.1 Short-Term Memory Retention Policy (No Time-Based TTL)

`memory` is a short-term operational layer and must not be retained by wall-clock days.
Retention is decided by usage frequency and revalidation evidence.

Lifecycle states:

- `open`: newly created issue/workaround memory
- `active`: frequently retrieved and still useful
- `cooling`: low-frequency, candidate for revalidation
- `revalidate_pending`: queued for reflection verification
- `purged`: removed from memory store (kept only as audit event)
- `promoted`: upgraded to long-term `knowledge` entry

Required signals per memory item:

- `hit_count`: successful retrieval count
- `miss_streak`: consecutive relevant turns where item was not selected/useful
- `last_hit_turn`: last turn sequence ID (not timestamp)
- `utility_score`: runtime usefulness score (from execution outcome)
- `revalidation_score`: reflection confidence about current validity

Event-driven TTL score (example contract):

```
ttl_score =
  w_hit * ewma(hit_rate)
  + w_utility * utility_score
  - w_miss * miss_streak
  - w_stale * inactivity_turn_gap
```

Policy:

- Keep in `active` while `ttl_score >= active_threshold`.
- Move to `cooling` when below threshold.
- Enter `revalidate_pending` when below `revalidate_threshold`.
- Purge only when revalidation confirms stale/fixed with enough confidence.

## 7.2 3-in-1 Revalidation Loop (ReAct + Graph + Omega)

When a memory item enters `revalidate_pending`, runtime must run the `3-in-1` loop:

1. ReAct pass (execution reality)
   - Collect latest tool-call outcomes and failure/recovery traces.
   - Determine whether the issue/workaround is still exercised in live execution.
2. Graph pass (workflow structure)
   - Validate whether the issue path in workflow DAG is still reachable/relevant.
   - Check whether dependency path or task decomposition still requires this memory item.
3. Omega pass (final policy decision)
   - Aggregate signals and produce final verdict:
     - `retain`
     - `obsolete`
     - `promote`
   - Only Omega can authorize purge/promotion.

Purging rule:

- Never purge by elapsed days.
- Purge only when `3-in-1` verdict is `obsolete`.

## 7.3 Boundary: Memory vs Knowledge

- `memory`:
  - short-term, operational, retractable
  - tracks transient bugs/workarounds
  - must support automatic purge after revalidation
- `knowledge`:
  - long-term, reusable, stable
  - created only via promotion gate from proven outcomes
  - feeds long-horizon self-evolution

Promotion gate (memory -> knowledge):

- repeated high-utility outcomes across sessions/tasks,
- reflection says pattern is stable and reusable,
- not a one-off workaround.

## 7.4 3-in-1 Gate Contract (Authoritative)

Both purge and promotion must pass the same `3-in-1 reflection` gate:

- `ReAct` engine
- `Graph` engine
- `Omega` engine

No direct delete/promote is allowed without this contract.

Engine responsibilities:

1. ReAct

- Provides execution-grounded evidence from tool loops.
- Emits: failure recurrence, recovery success, latest action outcomes.

2. Graph

- Provides workflow-structure evidence.
- Emits: path reachability, dependency-chain relevance, decomposition impact.

3. Omega

- Final policy arbiter.
- Uses ReAct + Graph outputs and additional evidence factors to decide:
  - `obsolete`: purge short-term memory
  - `retain`: keep/update short-term memory
  - `promote`: persist high-value stable memory to long-term knowledge

Omega evidence factors (inputs, not separate 3-in-1 lanes):

- upstream/downstream dependency status
- repository/codebase verification signals
- runtime trend and utility signals

Gate outputs (must be recorded):

- `verdict`
- `confidence`
- `react_evidence_refs[]`
- `graph_evidence_refs[]`
- `omega_factors[]`
- `reason`
- `next_action` (`purge` | `retain` | `promote`)

## 8. Observability Contract

Required structured events:

- `agent.injection.policy.selected`
- `agent.injection.role_mix.selected`
- `agent.injection.snapshot.created`
- `agent.injection.block.dropped`
- `agent.injection.block.truncated`
- `agent.reflection.recorded`
- `agent.memory.evolution.applied`

Each event should include:

- `session_id`, `turn_id`
- latency fields
- counts and budget metrics
- category distribution

## 9. Current Gap (Must Be Closed in Implementation Stage)

- Deterministic shortcut paths (`graph ...`, `omega ...`) can bypass unified injection assembly if they directly forward MCP calls.
- Target behavior: both shortcut and normal paths must consume the same `InjectionSnapshot` contract.

## 10. Black-Box Validation Matrix

Mandatory scenarios:

- multi-group session isolation
- mixed `/reset` + `/resume` with concurrent traffic
- long-context compression + recall injection under budget pressure
- role-mix profile switching across scenarios (debug vs architecture vs recovery)
- classified vs single vs hybrid mode parity checks
- injected wrong hint followed by reflection-driven correction in subsequent turn
- deterministic replay: same snapshot inputs produce same ordered output

## 11. Rollout Plan (Documentation-Gated)

1. Freeze architecture contracts (`PromptContextBlock`, `InjectionPolicy`, `InjectionSnapshot`, `ReflectionRecord`).
2. Implement injector core crate API and macros.
3. Integrate into Rust `run_turn` for normal and shortcut paths.
4. Wire reflection + memory credit update to snapshot references.
5. Add black-box + stress tests and observability dashboards.

## 12. Rust Contract Draft (Implementation Target)

This section defines implementation-facing contracts to keep architecture stable.

Implementation ownership:

- `omni-memory`: owns these contracts and state transitions.
- `omni-agent`: only calls memory interfaces and logs turn-level references.

### 12.1 Memory Lifecycle

```rust
enum MemoryLifecycleState {
    Open,
    Active,
    Cooling,
    RevalidatePending,
    Purged,
    Promoted,
}
```

### 12.2 Retention Signals

```rust
struct MemoryRetentionSignals {
    hit_count: u64,
    miss_streak: u32,
    last_hit_turn: u64,
    utility_score: f32,
    revalidation_score: f32,
    ttl_score: f32,
}
```

### 12.3 3-in-1 Gate Inputs

```rust
struct ReactEvidence {
    tool_failures: u32,
    recovery_success: u32,
    recurrence_score: f32,
    evidence_refs: Vec<String>,
}

struct GraphEvidence {
    path_reachable: bool,
    dependency_relevance_score: f32,
    decomposition_impact_score: f32,
    evidence_refs: Vec<String>,
}

struct OmegaFactors {
    upstream_status_score: f32,
    codebase_verification_score: f32,
    runtime_utility_trend_score: f32,
    notes: Vec<String>,
}
```

### 12.4 3-in-1 Gate Verdict

```rust
enum MemoryGateVerdict {
    Retain,
    Obsolete,
    Promote,
}

struct MemoryGateDecision {
    verdict: MemoryGateVerdict,
    confidence: f32,
    react_evidence_refs: Vec<String>,
    graph_evidence_refs: Vec<String>,
    omega_factors: Vec<String>,
    reason: String,
    next_action: String, // purge | retain | promote
}
```

### 12.5 Promotion Record (Memory -> Knowledge)

```rust
struct MemoryPromotionRecord {
    memory_id: String,
    promoted_to_knowledge_id: String,
    decision: MemoryGateDecision,
    reusable_pattern_summary: String,
}
```

### 12.6 Required Events

- `agent.memory.lifecycle.transition`
- `agent.memory.revalidate.started`
- `agent.memory.revalidate.decision`
- `agent.memory.purged`
- `agent.memory.promoted`

Required event fields:

- `session_id`
- `turn_id`
- `memory_id`
- `state_before`
- `state_after`
- `ttl_score`
- `decision.verdict`
- `decision.confidence`
