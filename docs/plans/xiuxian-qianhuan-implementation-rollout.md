# Xiuxian-Qianhuan Implementation Rollout Plan

> Status: In-Execution (Audited)  
> Date: 2026-02-20  
> Scope: Convert agreed architecture into an executable rollout sequence with hard gates.

Primary planning note:

- This document is a runtime/governance gate plan.
- The primary implementation track for current core work is LinkGraph in
  `xiuxian-wendao`: `docs/plans/link-graph-ppr-algorithm-spec.md`.

## 1. Final Target (No Ambiguity)

1. Runtime control plane is Rust-first:
   - `Omega` governance
   - `Graph` planning
   - `ReAct` execution
   - `Xiuxian-Qianhuan` injection
   - `omni-memory` gate and evolution
2. Python remains MCP tool/service plane during transition.
3. All critical paths are auditable, replayable, and benchmarked.

## 2. Non-Negotiable Engineering Constraints

1. `omni-agent` stays orchestration-only.
2. Memory lifecycle policy does not live in channel/runtime handler modules.
3. Discover/routing must preserve confidence contract end-to-end.
4. No JSON-file state source on hot path (debug export only).
5. No hidden prompt mutation outside Xiuxian-Qianhuan snapshot assembly.

## 3. Data Plane Standard (Valkey + LanceDB + Arrow)

## 3.1 Responsibilities

1. `Valkey` (hot state + concurrency):
   - session/window runtime state
   - webhook dedup and command idempotency
   - stream events and near-real-time counters
   - hot discover cache
2. `LanceDB` (durable retrieval + analytics):
   - tool index and knowledge index
   - memory episodes and historical retrieval traces
   - offline benchmark datasets and replay analysis
3. `Arrow` (contract + zero-copy):
   - canonical row contracts for discover and memory gate
   - batch transport between retrieval, rerank, and persistence
   - stable schema versioning for cross-language compatibility

## 3.2 Canonical Rule

- Hot path reads/writes prioritize `Valkey`.
- Durable and analytical state lands in `LanceDB`.
- Inter-stage exchange format is `Arrow` contract, not ad-hoc JSON.

Scope note (to avoid ambiguity with LinkGraph engine internals):

- This rule applies to agent runtime/session/event/discover hot paths.
- `xiuxian-wendao` LinkGraph index snapshot cache also follows this rule:
  cache storage is Valkey-backed (db-first), while Python acts as a bridge to
  Rust and does not own graph cache/index state.
- LinkGraph cache config resolution is isolated to LinkGraph scope and uses
  `VALKEY_URL` as the single source of truth, with no fallback to unrelated
  session/discover settings.
- Missing LinkGraph cache URL is a fail-fast error (no implicit localhost default).

## 4. Discover/Routing Contract Upgrade

Current gap:

- `skill.discover` currently consumes hybrid routing but does not consistently expose full ranking contract (`final_score`, `confidence`, `ranking_reason`) in returned payload.

Target contract (`discover` output item):

- `tool`
- `usage`
- `score`
- `final_score`
- `confidence` (`high` | `medium` | `low`)
- `ranking_reason` (feature attribution summary)
- `input_schema_digest`
- `documentation_path`

Confidence behavior:

1. `high`: allow direct execution recommendation.
2. `medium`: return top-k + clarification prompt.
3. `low`: block direct execution and force intent refinement.

## 5. Two-Pass Paper Reflection to Execution Decision

What we adopt:

1. Dynamic graph parallelism for complex tasks.
2. Confidence-aware governance and fallback.
3. Plan-aware compression and bounded context.
4. Evidence-driven memory utility gate.
5. Reflective runtime with explicit state transitions.

What we reject:

1. Heavy online search/planning loops that damage latency.
2. Prompt-only qualitative gate without measurable utility/evidence.
3. Unbounded context growth and opaque summarization.
4. Runtime design that bypasses DB-backed observability.

## 6. Execution Sequence (A0-A7)

## A0 Contract Freeze (must pass first)

1. Freeze:
   - `OmegaDecision`
   - `PromptContextBlock`
   - `InjectionPolicy`
   - `InjectionSnapshot`
   - `MemoryGateDecision`
2. Freeze Arrow schemas for:
   - `discover_match.v1`
   - `memory_gate_event.v1`
   - `session_route_trace.v1`

Exit gate:

- contract tests green
- no unresolved schema diffs

## A1 Xiuxian-Qianhuan Typed Snapshot

1. Replace loose XML-only path with typed block assembly.
2. Add anchor block policy (`safety`, `policy` non-evictable).
3. Enforce deterministic ordering and truncation reporting.

Exit gate:

- deterministic replay tests pass
- anchor non-eviction tests pass

## A2 Omega Confidence Routing

1. Add confidence/risk/fallback to route decisions.
2. Add tool trust class signal (`evidence`, `verification`, `other`).
3. Ensure deterministic shortcut paths (`graph ...`, `omega ...`) use same route contracts.

Exit gate:

- route policy tests pass
- fallback correctness tests pass

## A3 Discover High-Throughput Path

1. Rust-side discover ranking pipeline (hot path).
2. Valkey read-through cache for discover results.
3. Return full confidence contract payload.

Exit gate:

- discover cache-hit p95 < 15ms
- discover cache-miss p95 < 80ms

## A4 Memory 3-in-1 Gate

1. Implement explicit utility ledger in `omni-memory`.
2. Gate decision must include ReAct/Graph/Omega evidence fields.
3. Promotion/purge requires evidence thresholds.

Exit gate:

- retain/obsolete/promote determinism tests pass
- gate replay audit passes

## A5 Reflective Runtime State Machine

1. Introduce explicit diagnose/plan/apply lifecycle.
2. Illegal transition -> explicit runtime error + event log.
3. Couple reflection results to next-turn policy hints.

Exit gate:

- state machine transition tests pass
- self-healing fault injection tests pass

## A6 Multi-Group Isolation and Black-Box Matrix

1. Multi-group/multi-thread mixed command matrix (`/reset`, `/resume`, normal turns).
2. Verify no cross-session contamination in memory and snapshots.
3. Verify command ACL and routing parity under concurrency.

Exit gate:

- session contamination rate = 0
- matrix suite green

## A7 Performance and SLO Sign-Off

1. Run 64/128/256 concurrency sweeps.
2. Track p50/p95 latency, error rate, memory peak, restart recovery.
3. Compare pre/post rollout baseline.

Exit gate:

- error rate < 0.1%
- no deadlock/hang in stress suite
- observability chain complete

## 6.1 Current Audit Snapshot (2026-02-20)

| Gate                            | Current Status                             | Evidence                                                                                                                                                                                                                                                  | Quality/Test Verdict                                                                                                                                                                                                                |
| :------------------------------ | :----------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A0 Contract Freeze              | ✅ Done (gate enforced)                    | `packages/shared/schemas/contract-freeze.lock.json`; `scripts/contract_freeze_lock.py`; `scripts/ci-contract-freeze.sh`; `cargo test -p omni-agent --test contracts`; `cargo test -p xiuxian-qianhuan --test contracts`                                   | Drift is fail-fast via lock verification + Rust contract tests + Python schema/snapshot suite in one gate.                                                                                                                          |
| A1 Typed Snapshot               | ✅ Done                                    | `packages/rust/crates/xiuxian-qianhuan/tests/contracts/test_injection_contracts.rs`; `packages/rust/crates/omni-agent/src/agent/injection/tests.rs`; `cargo test -p xiuxian-qianhuan --test contracts`; `cargo test -p omni-agent --lib injection::tests` | Deterministic roundtrip + multi-turn content hash + anchor non-eviction are covered by automated tests.                                                                                                                             |
| A2 Omega Confidence Routing     | ✅ Done (core path)                        | `packages/rust/crates/omni-agent/src/contracts/omega.rs`; `packages/rust/crates/omni-agent/tests/agent_injection.rs`; `cargo test -p omni-agent --test agent_injection` (pass)                                                                            | Confidence/risk/fallback/trust-class and fallback correctness are covered by automated tests.                                                                                                                                       |
| A3 Discover High-Throughput     | ✅ Done (gated, replay verified)           | `packages/rust/crates/omni-agent/tests/mcp_discover_cache.rs` (`discover_calls_use_valkey_read_through_cache_when_configured`); `scripts/channel/test_omni_agent_memory_ci_gate.py` (`run_discover_cache_gate`); `.run/logs/memory-ci-nightly-latest.log` | 2026-02-20 nightly replay passed discover cache latency gate with explicit test execution and no runtime failure.                                                                                                                   |
| A4 Memory 3-in-1 Gate           | ✅ Done (core path, replay verified)       | `packages/rust/crates/omni-agent/tests/agent_memory_gate_flow.rs`; `packages/rust/crates/omni-memory/src/gate.rs`; `.run/reports/omni-agent-memory-evolution.json`; `.run/logs/memory-ci-nightly-latest.log`                                              | Utility gate and memory self-correction remained green in nightly replay (`quality_score=98.5`, `successful_corrections=4`, `recall_credit_events=21`).                                                                             |
| A5 Reflective Runtime           | ✅ Done (gated, replay verified)           | `packages/rust/crates/omni-agent/tests/agent/reflection.rs` (`reflective_runtime_long_horizon_quality_thresholds`); `.run/reports/omni-agent-trace-reconstruction.json`; `.run/logs/memory-ci-nightly-latest.log`                                         | Reflection thresholds and lifecycle traces were revalidated (`quality_score=100.0`, `agent.reflection.lifecycle.transition=102`).                                                                                                   |
| A6 Multi-Group Isolation Matrix | ✅ Done (gate codified, replay verified)   | `scripts/channel/test_omni_agent_session_matrix.py`; `scripts/channel/test_omni_agent_memory_ci_gate.py` (`assert_session_matrix_quality`); `scripts/channel/test_memory_ci_gate.py`; `.run/reports/agent-channel-session-matrix.json`                    | Nightly replay passed matrix isolation (`19/19`, `overall_passed=true`, partition mode `chat`) with zero failed steps.                                                                                                              |
| A7 Performance Sign-Off         | ✅ Done (mandatory-gated, replay verified) | `.github/workflows/omni-agent-memory-gates.yaml` (`memory-gate-a7`); `.run/reports/omni-agent-memory-benchmark-nightly-61434-1771609391684.json`; `.run/logs/memory-ci-nightly-a7-latest.log`; `.run/reports/a7-performance-signoff-20260220.md`          | A7 path now runs as a mandatory workflow job; nightly benchmark is enforced with `--benchmark-iterations 3`, `mcp_error_turns == 0`, and waiting-warning budget (`mcp.pool.call.waiting`/`mcp.pool.connect.waiting`) capped at `0`. |

## 6.2 Audit Findings: Quality and Test Gaps

1. No blocking A1-A7 execution gaps remain after adding the live multi-group runbook and mandatory A7 gate path.

## 6.3 Immediate Remediation Checklist

1. Execute `docs/testing/omni-agent-live-multigroup-runbook.md` at least once per release cut and archive its artifacts with release evidence.
2. Keep one consolidated gate map (below) as the source of truth for A0-A7 command/report wiring.

## 6.4 Consolidated A0-A7 Gate Map

| Gate                            | Local command(s)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | CI entrypoint                                                                                                                                                          | Report artifacts                                                                                                                                                                                                                                                                                                               | Pass criteria (executable)                                                                                                                                                                                                                                                                |
| :------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A0 Contract Freeze              | `just test-contract-freeze`<br>`uv run pytest packages/python/foundation/tests/unit/services/test_contract_consistency.py::test_route_test_cli_json_validates_against_schema -v`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | `.github/workflows/ci.yaml` → `architecture-gate` (`Contract E2E - route test JSON...`, `Contract freeze - schemas and canonical snapshots`)                           | No persistent artifact by default (pytest/stdout)                                                                                                                                                                                                                                                                              | Freeze suite exits `0`; route-test JSON validates schema; no unresolved schema drift in freeze set.                                                                                                                                                                                       |
| A1 Typed Snapshot               | `cargo test -p xiuxian-qianhuan --test contracts`<br>`cargo test -p omni-agent --lib injection::tests`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | `.github/workflows/ci.yaml` → `architecture-gate` (`Rust gate - quality gates`, via `just rust-quality-gate` / `cargo nextest run --workspace`)                        | No persistent artifact by default (cargo stdout)                                                                                                                                                                                                                                                                               | Deterministic snapshot roundtrip passes; anchor block non-eviction remains enforced.                                                                                                                                                                                                      |
| A2 Omega Confidence Routing     | `cargo test -p omni-agent --test agent_injection`<br>`cargo test -p omni-agent --test contracts`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | `.github/workflows/ci.yaml` → `architecture-gate` (`Rust gate - quality gates`)                                                                                        | No persistent artifact by default (cargo stdout)                                                                                                                                                                                                                                                                               | Confidence/risk/fallback/trust-class contract tests pass; fallback path correctness remains deterministic.                                                                                                                                                                                |
| A3 Discover High-Throughput     | `python3 scripts/channel/test_omni_agent_memory_ci_gate.py --profile quick`<br>`OMNI_AGENT_DISCOVER_CACHE_HIT_P95_MS=15 OMNI_AGENT_DISCOVER_CACHE_MISS_P95_MS=80 OMNI_AGENT_DISCOVER_CACHE_BENCH_ITERATIONS=12 cargo test -p omni-agent --test mcp_discover_cache discover_calls_use_valkey_read_through_cache_when_configured -- --ignored --exact`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | `.github/workflows/omni-agent-memory-gates.yaml` → `memory-gate-quick`                                                                                                 | `.run/logs/omni-agent-webhook-ci.log`<br>`.run/logs/omni-agent-mock-telegram.log`                                                                                                                                                                                                                                              | Discover cache gate passes with p95 hit `<15ms` and miss `<80ms`; quick profile completes without runtime failures.                                                                                                                                                                       |
| A4 Memory 3-in-1 Gate           | `cargo test -p omni-agent --test agent_memory_gate_flow`<br>`python3 scripts/channel/test_omni_agent_memory_ci_gate.py --profile quick`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `.github/workflows/omni-agent-memory-gates.yaml` → `memory-gate-quick`                                                                                                 | `.run/logs/omni-agent-webhook-ci.log` (plus cargo stdout)                                                                                                                                                                                                                                                                      | Retain/obsolete/promote gate decisions stay deterministic; memory suite core path remains green.                                                                                                                                                                                          |
| A5 Reflective Runtime           | `cargo test -p omni-agent --lib reflective_runtime_long_horizon_quality_thresholds`<br>`python3 scripts/channel/test_omni_agent_memory_ci_gate.py --profile nightly --skip-matrix --skip-benchmark`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | `.github/workflows/omni-agent-memory-gates.yaml` → `memory-gate-quick` and `memory-gate-nightly`                                                                       | CI/runtime logs (no dedicated standalone report file)                                                                                                                                                                                                                                                                          | Reflective runtime quality threshold test exits `0`; no illegal transition regression under gate run.                                                                                                                                                                                     |
| A6 Multi-Group Isolation Matrix | `python3 scripts/channel/test_omni_agent_session_matrix.py --output-json .run/reports/agent-channel-session-matrix.json --output-markdown .run/reports/agent-channel-session-matrix.md`<br>`python3 scripts/channel/test_omni_agent_memory_ci_gate.py --profile nightly --skip-benchmark`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | `.github/workflows/omni-agent-memory-gates.yaml` → `memory-gate-nightly`<br>`.github/workflows/checks.yaml` → `telegram-session-isolation-gate` (targeted regressions) | `.run/reports/agent-channel-session-matrix.json`<br>`.run/reports/agent-channel-session-matrix.md`<br>`.run/reports/agent-channel-session-matrix-live.json`<br>`.run/reports/omni-agent-memory-evolution-live.json`                                                                                                            | `overall_passed=true`; failed steps `0`; total steps `>=20` (or `>=19` when `concurrent_baseline_cross_chat` is present and `concurrent_cross_group` is omitted in `chat` partition mode); required cross-group evidence and mixed-batch steps present and passing; 3 distinct group IDs. |
| A7 Performance and SLO Sign-Off | `python3 scripts/channel/test_omni_agent_mcp_startup_suite.py --allow-mcp-restart --output-json .run/reports/omni-agent-mcp-startup-suite.json --output-markdown .run/reports/omni-agent-mcp-startup-suite.md`<br>`python3 scripts/channel/test_omni_agent_mcp_startup_stress.py --output-json .run/reports/omni-agent-mcp-startup-stress.json --output-markdown .run/reports/omni-agent-mcp-startup-stress.md`<br>`python3 scripts/channel/test_omni_agent_mcp_tools_list_concurrency_sweep.py --base-url http://127.0.0.1:3002 --concurrency-values 64,128,256 --json-out .run/reports/a7-mcp-tools-list-64-128-256.json --markdown-out .run/reports/a7-mcp-tools-list-64-128-256.md`<br>`python3 scripts/channel/test_omni_agent_memory_ci_gate.py --profile nightly --skip-matrix --skip-evolution --benchmark-iterations 3 --max-mcp-call-waiting-events 0 --max-mcp-connect-waiting-events 0 --max-mcp-waiting-events-total 0` | `.github/workflows/omni-agent-memory-gates.yaml` → `memory-gate-a7` (mandatory on PR/schedule/workflow_dispatch).                                                      | `.run/reports/omni-agent-mcp-startup-suite.json`<br>`.run/reports/omni-agent-mcp-startup-suite-hot.json`<br>`.run/reports/omni-agent-mcp-startup-suite-cold.json`<br>`.run/reports/omni-agent-mcp-startup-stress.json`<br>`.run/reports/a7-mcp-tools-list-64-128-256.json`<br>`.run/reports/omni-agent-memory-benchmark*.json` | Startup and stress suites meet configured quality thresholds; tools/list sweep meets SLO target; memory benchmark gates must pass with `query_turns > 0`, `mcp_error_turns == 0`, and waiting-warning budget (`call/connect/total`) within configured limits.                             |

## 7. Rust Dependency Candidates (Only if profile proves need)

1. `moka`: concurrent TTL cache for discover hot path.
2. `dashmap`: low-contention concurrent maps.
3. `hashbrown` + `ahash`: high-throughput hash maps.
4. `smallvec`: reduce heap allocations on top-k pipelines.
5. `parking_lot`: lower lock overhead.
6. `simd-json`: optional only if JSON decode is proven bottleneck.

Rule:

- dependency introduction must be benchmark-backed, not preference-backed.

## 8. Acceptance Checklist Before Coding Starts

1. Plan docs reference this rollout as source of execution order.
2. Backlog feature names match A0-A7 gates.
3. Data plane contract is written and accepted.
4. Discover confidence contract is written and accepted.
5. Test and benchmark harness paths are linked in execution tasks.
