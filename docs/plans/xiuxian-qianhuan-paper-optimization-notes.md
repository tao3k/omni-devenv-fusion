# Xiuxian-Qianhuan Paper Optimization Notes (arXiv 2025-2026)

> Status: Draft (research-backed architecture audit, implementation not started)  
> Date: 2026-02-20  
> Method: Two-pass review (`quick read` -> `deep compare`) with reflection loop

## 1. Scope and Method

This report is the pre-implementation research gate for:

- Omega (governance + routing)
- Graph (workflow planning/parallelization)
- ReAct (execution loop)
- Xiuxian-Qianhuan (injection assembly)
- Memory self-evolution (retain/obsolete/promote)

Two-pass process:

1. Pass 1 (quick read): confirm relevant 2025-2026 arXiv papers and extract transferable mechanisms.
2. Pass 2 (deep compare): map mechanisms to current Rust code and identify concrete architecture deltas.

Reflection rule used in this report:

- `Evidence` (paper/code fact) -> `Gap` (what is missing) -> `Action` (what to change) -> `Risk` (what can fail).

## 2. Requested Titles vs arXiv Reality

The six previously suggested paper titles were not found as exact arXiv records.  
Therefore this audit uses nearest high-relevance, verifiable arXiv papers from 2025-2026.

## 3. Paper Corpus (Downloaded + Read)

Local corpus directory:

- `.data/research/papers/xiuxian-qianhuan`

Selected papers:

1. DynTaskMAS (2025-03-10): https://arxiv.org/abs/2503.07675
2. HALO (2025-05-17): https://arxiv.org/abs/2505.13516
3. Memory as Action / MemAct (2025-10-14): https://arxiv.org/abs/2510.12635
4. VIGIL (2025-12-08): https://arxiv.org/abs/2512.07094
5. PAACE (2025-12-18): https://arxiv.org/abs/2512.16970
6. MemRL (2026-01-06): https://arxiv.org/abs/2601.03192
7. InfiAgent (2026-01-06): https://arxiv.org/abs/2601.03204
8. Confidence Dichotomy (2026-01-12): https://arxiv.org/abs/2601.07264

## 4. Pass 1: Quick Read (Transferable Findings)

## 4.1 Omega / Graph / Orchestration

- DynTaskMAS reports dynamic task graphs + async parallel execution with measured throughput/resource gains.
- HALO reports hierarchical planning/role design/inference layering and structured workflow search (MCTS-like).

[Inference] Together these support moving from static route rules to policy-driven, confidence-aware route selection plus graph-level parallel decomposition.

## 4.2 Context Injection and Compression

- MemAct treats context curation as learnable actions (insert/delete) instead of passive truncation.
- PAACE emphasizes plan-aware context engineering and function-preserving compression over generic summarization.

[Inference] Injection should be policy-driven and plan-aware, not only char/token clipping.

## 4.3 Runtime Reliability and Self-Repair

- VIGIL proposes reflective runtime supervision as a separate maintenance plane, with state-gated transitions and explicit illegal-transition errors.
- Confidence Dichotomy shows calibration differs by tool type (evidence tools vs verification tools), and confidence should be explicitly controlled.

[Inference] Runtime governance should model tool trust classes and include explicit self-healing state transitions.

## 4.4 Memory Evolution and Long-Horizon Stability

- MemRL validates two-phase retrieval and runtime reinforcement on episodic memory.
- InfiAgent shows bounded-context execution with externalized persistent state for long-horizon stability.

[Inference] We should preserve bounded prompt context and externalize durable state, while keeping online memory adaptation in `omni-memory`.

## 5. Pass 2: Deep Compare Against Current Rust Code

## 5.1 Injection Layer (Xiuxian-Qianhuan)

Current code evidence:

- `packages/rust/crates/xiuxian-qianhuan/src/config.rs`
- `packages/rust/crates/xiuxian-qianhuan/src/window.rs`
- `packages/rust/crates/xiuxian-qianhuan/src/xml.rs`
- `packages/rust/crates/omni-agent/src/agent/system_prompt_injection_state.rs`

Observed:

- Strong baseline for bounded XML QA window normalization.
- Missing typed block contracts (`PromptContextBlock`, `InjectionPolicy`, `InjectionSnapshot`, `RoleMixProfile`) at runtime path level.
- No semantic-anchor concept for non-evictable critical blocks.

Optimization delta:

- Add typed, immutable snapshot assembly API and block provenance.
- Add category caps, deterministic ordering, and anchor blocks (`safety/policy` never dropped).

## 5.2 Omega Governance and Route Decision

Current code evidence:

- `packages/rust/crates/omni-agent/src/agent/mod.rs`
- `packages/rust/crates/omni-agent/src/agent/graph_bridge.rs`

Observed:

- Fast shortcut routing exists, but no explicit confidence-calibrated `OmegaDecision` contract.
- No formal pre-flight route simulation or tool-type calibration before graph/react selection.

Optimization delta:

- Introduce `OmegaDecision { route, confidence, risk, fallback_policy }`.
- Add tool trust classes (evidence vs verification) and calibration-aware route adjustments.

## 5.3 ReAct Runtime + Self-Healing

Current code evidence:

- `packages/rust/crates/omni-agent/src/agent/reflection.rs`
- `packages/rust/crates/omni-agent/src/agent/mod.rs`

Observed:

- Reflection exists but is heuristic and loosely coupled to runtime state transitions.
- No explicit state machine for self-repair stages.

Optimization delta:

- Introduce a separate reflective maintenance pipeline (VIGIL style) with explicit stage gates.
- Enforce illegal-transition errors for diagnoser/planner/apply stages.

## 5.4 Memory Evolution (MemRL Alignment)

Current code evidence:

- `packages/rust/crates/omni-memory/src/two_phase.rs`
- `packages/rust/crates/omni-memory/src/store.rs`
- `packages/rust/crates/omni-agent/src/agent/memory_recall.rs`
- `packages/rust/crates/omni-agent/src/agent/memory_recall_feedback.rs`

Observed:

- Two-phase recall and feedback bias are present.
- Current promotion/obsolete lifecycle scoring is still limited; no full 3-in-1 evidence ledger (ReAct+Graph+Omega evidence fusion) yet.

Optimization delta:

- Add memory utility ledger fields (access, success, reuse context, revalidation evidence).
- Promote/purge only through explicit utility + evidence gate contract.

## 5.5 Long-Horizon Window and Externalized State

Current code evidence:

- `packages/rust/crates/omni-window/src/window.rs`
- `packages/rust/crates/omni-agent/src/session/bounded_store.rs`
- `packages/rust/crates/omni-agent/src/agent/session_context.rs`

Observed:

- Bounded window and summary segments are implemented.
- No explicit file-centric persistent task state abstraction (InfiAgent pattern) in runtime contract.

Optimization delta:

- Add externalized workspace state manifest (state snapshot + fixed recent action window).
- Keep prompt window bounded while preserving recoverable long-horizon state outside prompt.

## 6. Fragmented Optimization Backlog (Pre-Implementation)

## P0 (must do first)

1. Freeze runtime contracts:
   - `OmegaDecision`
   - `PromptContextBlock`
   - `InjectionPolicy`
   - `InjectionSnapshot`
   - `MemoryGateDecision`
2. Add observability for injection and gate evidence:
   - snapshot created/dropped/truncated/anchored
   - route confidence and fallback reason
3. Add calibration metadata on tool calls (evidence vs verification class).

## P1 (core capability)

1. Implement immutable Xiuxian-Qianhuan typed snapshot builder.
2. Implement plan-aware context compression hook (PAACE-inspired).
3. Implement 3-in-1 memory gate scoring in `omni-memory`.

## P2 (stability/performance)

1. Add reflective maintenance state machine (VIGIL-inspired).
2. Add bounded long-horizon externalized state path (InfiAgent-inspired).
3. Add graph-parallel route policy experiment path (DynTaskMAS/HALO-inspired).

## 7. Verification and Audit Gate (Before Coding)

Required acceptance checks for this architecture phase:

1. Contract tests for snapshot immutability and anchor non-eviction.
2. Route policy tests for confidence/fallback correctness.
3. Session-isolation matrix across multi-group and multi-thread.
4. Memory gate tests for retain/obsolete/promote determinism.
5. Black-box benchmark: p95 latency, failure rate, context-token growth, memory utility trend.

## 8. Reflection Summary

What changed after paper review:

- We should not treat injection as only XML normalization; it must become typed immutable snapshot assembly.
- We should not treat route as static shortcuts; it needs policy + confidence + fallback semantics.
- We should not treat memory gate as qualitative only; it needs explicit evidence-scoring contracts.
- We should not rely only on rolling chat windows for long-horizon work; state externalization is required.

Main risk if skipped:

- Context drift under long sessions, unclear route failures, and non-auditable memory evolution.

## 9. Paper Decision Matrix (Adopt vs Discard)

This section turns research into explicit engineering decisions.

| Paper                | Good point to adopt                                     | Weak point to discard                                          | Project-specific implementation decision                                |
| -------------------- | ------------------------------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------- |
| DynTaskMAS           | Dynamic task-graph decomposition and parallel execution | Research setup can assume idealized coordination costs         | Keep graph-parallel scheduling, add runtime budget/fallback guards      |
| HALO                 | Hierarchical planning structure                         | Deep workflow search can be expensive in real-time workloads   | Keep hierarchy, avoid always-on expensive search loops                  |
| MemAct               | Context management as explicit action policy            | RL-heavy path is costly to operationalize early                | Start with policy + feedback adaptation, then evolve to learned policy  |
| VIGIL                | Reflective runtime and explicit stage transitions       | Affective framing is not required for our target               | Keep state-gated reflective runtime, use operational error taxonomy     |
| PAACE                | Plan-aware compression for long tasks                   | Synthetic training assumptions may not match production traces | Keep plan-aware compression hooks with runtime observability            |
| MemRL                | Two-phase retrieval + utility-oriented memory updates   | Reward shaping can drift if not constrained                    | Keep two-phase + utility ledger, enforce evidence-based gate thresholds |
| InfiAgent            | Bounded context + externalized state for long horizon   | File-centric abstraction is not required in our DB-first stack | Keep bounded context principle, use Valkey/LanceDB/Arrow data plane     |
| Confidence Dichotomy | Tool-type-aware confidence calibration                  | Verbal confidence alone is insufficient                        | Keep calibrated confidence with tool-class metadata and fallback policy |

## 10. Rust Ecosystem Guidance

Preferred baseline:

- continue using current Rust-first core (`omni-agent`, `omni-memory`, `omni-window`, vector stack).

Conditional dependency candidates (only if benchmark-proven):

- `moka` (concurrent TTL cache)
- `dashmap` (concurrent map)
- `hashbrown` + `ahash` (faster map/hash path)
- `smallvec` (allocation reduction on top-k pipelines)
- `parking_lot` (lock overhead reduction)
- `simd-json` (JSON decode hotspot only)
