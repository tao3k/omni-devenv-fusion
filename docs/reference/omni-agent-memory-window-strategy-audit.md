# Omni-Agent Memory/Window Strategy Audit

Last updated: 2026-02-18 (UTC)

## Scope

Audit target:

- `packages/rust/crates/omni-agent` memory + session window + context-budget strategy coupling
- Runtime observability quality for diagnosing memory/window behavior
- Alignment against reference projects:
  - `HKUDS/nanobot`
  - `zeroclaw-labs/zeroclaw`
  - `openclaw/openclaw`

## Current State (Omni-Agent)

### Implemented capabilities

- Bounded session window with Valkey-backed shared state (`session/bounded_store.rs`,
  `session/redis_backend.rs`)
- Rolling summary segments for drained old turns (`session/bounded_store.rs`)
- Context-budget pruning with strategy selector (`agent/context_budget.rs`)
- Session context snapshot/reset/resume/drop (`agent/session_context.rs`)
- memRL episode store + persistence backends (`agent/persistence.rs`, `agent/memory_state.rs`)
- Structured event registry for session/memory/dedup (`observability/session_events.rs`)

### Newly added in this iteration

- Adaptive memory recall plan:
  - Budget/window-aware `k1`, `k2`, `lambda`, min-score, and max context size
  - File: `packages/rust/crates/omni-agent/src/agent/memory_recall.rs`
- Recency-aware recall score fusion:
  - Recall ranking now blends base score with time-decay recency score so newer memories are
    favored when relevance is close, while strong relevance signals still dominate.
  - File: `packages/rust/crates/omni-agent/src/agent/memory_recall.rs`
- Recall metrics snapshot export:
  - Process-level recall metrics snapshot is now exported (planned/injected/skipped counters,
    selected/injected totals, and pipeline-latency buckets) and surfaced in `/session memory`
    dashboard/JSON output.
  - Files: `packages/rust/crates/omni-agent/src/agent/memory_recall_metrics.rs`,
    `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs.rs`
- Bounded memory context injection with score-based filtering
  - File: `packages/rust/crates/omni-agent/src/agent/mod.rs`
- New recall observability events:
  - `agent.memory.recall.planned`
  - `agent.memory.recall.injected`
  - `agent.memory.recall.skipped`
  - File: `packages/rust/crates/omni-agent/src/observability/session_events.rs`
- Runtime inspection command:
  - `/session memory` dashboard + JSON now expose `query_tokens`, `embedding_source`,
    `pipeline_duration_ms`, and `context_chars_injected`.
  - File: `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs.rs`
- Cross-instance snapshot persistence:
  - `/session memory` snapshot payload is now persisted via session backend key-space (special
    session key), so Valkey-backed multi-instance deployments can inspect latest recall state
    regardless of which instance receives the command.
  - File: `packages/rust/crates/omni-agent/src/agent/memory_recall_state.rs`
- Embedding config and dimension drift hardening:
  - Memory recall/store now resolves embedding model/dimension/client URL from canonical
    `embedding.*` settings keys, and dimension mismatches are auto-repaired via vector resampling
    (source label: `embedding_repaired`) instead of direct hash fallback.
  - Files: `packages/rust/crates/omni-agent/src/agent_builder.rs`,
    `packages/rust/crates/omni-agent/src/agent/mod.rs`,
    `packages/rust/crates/omni-agent/src/agent/embedding_dimension.rs`
- Session-level recall feedback adaptation:
  - Recall plan now applies a per-session feedback bias derived from assistant outcome
    classification (`success`/`failure`) to tighten or broaden recall aggressiveness over time.
  - Files: `packages/rust/crates/omni-agent/src/agent/memory_recall_feedback.rs`,
    `packages/rust/crates/omni-agent/src/agent/mod.rs`,
    `packages/rust/crates/omni-agent/src/agent/persistence.rs`
- Structured feedback signal pipeline:
  - Recall feedback now resolves through deterministic priority:
    1. explicit user feedback markers (`/feedback ...`, `feedback: ...`, `[feedback: ...]`),
    2. MCP tool execution outcome summary (`CallToolResult.is_error` + transport failures),
    3. assistant-text heuristic fallback.
  - Files: `packages/rust/crates/omni-agent/src/agent/memory_recall_feedback.rs`,
    `packages/rust/crates/omni-agent/src/agent/mcp.rs`,
    `packages/rust/crates/omni-agent/src/agent/mod.rs`
- First-class feedback command UX:
  - Telegram runtime now supports explicit session command feedback
    (`/session feedback up|down`, `/feedback up|down`, plus
    `success|failure|positive|negative|good|bad|+|-` aliases), and returns
    structured JSON/dashboard responses for applied/unavailable states.
  - Files: `packages/rust/crates/omni-agent/src/channels/telegram/commands/session.rs`,
    `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs.rs`,
    `packages/rust/crates/omni-agent/tests/channels_commands.rs`,
    `packages/rust/crates/omni-agent/tests/telegram_runtime/session_feedback.rs`
- Cross-instance recall feedback continuity:
  - Session feedback bias is now persisted into session backend key-space, so multi-instance
    deployments can continue adaptive recall policy after process switch/restart.
  - Files: `packages/rust/crates/omni-agent/src/agent/memory_recall_feedback_state.rs`,
    `packages/rust/crates/omni-agent/src/agent/mod.rs`
- Valkey startup strictness hardening:
  - When memory persistence resolves to Valkey (explicit `valkey` or `auto` with redis URL),
    startup is strict by default: initial state-load failure stops startup instead of silently
    continuing with degraded memory behavior. Local fallback remains disabled for Valkey mode.
  - A deliberate opt-out is available through `memory.persistence_strict_startup: false` (or
    `OMNI_AGENT_MEMORY_PERSISTENCE_STRICT_STARTUP=false`) for development scenarios.
  - Files: `packages/rust/crates/omni-agent/src/agent/memory_state.rs`,
    `packages/rust/crates/omni-agent/src/agent_builder.rs`,
    `packages/rust/crates/omni-agent/tests/agent_memory_persistence_backend.rs`
- Coverage:
  - Recall strategy unit tests: `packages/rust/crates/omni-agent/src/agent/memory_recall/tests.rs`
  - Event registry tests: `packages/rust/crates/omni-agent/tests/observability_session_events.rs`
  - Event sequence checker extended for recall events:
    `scripts/channel/check-omni-agent-event-sequence.sh`

## Reference Findings

## Nanobot

- Session manager uses append-only JSONL with explicit consolidation marker (`last_consolidated`)
  and non-destructive history behavior (`nanobot/session/manager.py`).
- Agent loop triggers background consolidation once message count crosses window threshold
  (`nanobot/agent/loop.py`).

Transferable lesson:

- Keep consolidation asynchronous and explicit; never mutate active history in-place unexpectedly.

## ZeroClaw

- Strong typed observability abstraction (`observability/traits.rs`) and concrete log observer
  (`observability/log.rs`) with stable event names and per-stage timing.
- Memory backends include fallback/cooldown behavior to avoid unstable external dependency
  flapping (`memory/lucid.rs`).

Transferable lesson:

- Recall strategy decisions should be observable as first-class events, not hidden in generic logs.

## OpenClaw

- Detailed session-compaction model and operational playbook (`docs/reference/session-management-compaction.md`).
- Explicit “pre-compaction memory flush” concept and configuration controls
  (`docs/concepts/memory.md`).

Transferable lesson:

- Couple compaction thresholds with memory durability actions before context loss.

## Gap Analysis (Remaining)

1. Recall quality feedback loop depth:
   - Explicit feedback commands are now available, but long-run adaptation quality is still
     evaluated mainly via black-box probes; there is no CI-level threshold/assertion on
     feedback-bias convergence behavior across longer session trajectories.
2. Compaction-memory coupling:
   - Turn storage is durable, but there is no explicit pre-compaction “flush checkpoint” policy
     tied to soft window pressure thresholds.
3. Metrics plane integration depth:
   - Process-level snapshot metrics are now available in command output, but there is still no
     external metrics sink/exporter (Prometheus/OpenTelemetry) for long-term aggregation.
4. CI observability assertions:
   - Event sequence checker exists; CI is not yet enforcing recall-event completeness and expected
     decision ratio thresholds.

## Recommended Next Steps

1. Add CI assertions for multi-turn feedback adaptation quality (for example bounded bias drift,
   command-feedback precedence invariants, and recall-decision stability bands).
2. Add soft-threshold pre-compaction memory checkpoint hooks and failure-mode tests.
3. Export recall metrics (`plan/injected/skipped`, latency buckets, selected/injected counts) for
   dashboarding.
4. Extend live CI workflow to assert recall event sequence and minimum recall telemetry coverage.
