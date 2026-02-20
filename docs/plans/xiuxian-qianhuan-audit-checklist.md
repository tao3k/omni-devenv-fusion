# Integrated Architecture Audit Checklist (2026)

> **Goal:** Track validation, implementation, and performance with LinkGraph-first execution.  
> **Primary Track:** `xiuxian-wendao` LinkGraph engine (`packages/rust/crates/xiuxian-wendao`).  
> **Scope:** LinkGraph PPR, Omega routing, Xiuxian-Qianhuan injection, Agentic KG construction, 3-in-1 Gate.

Status legend:

- ✅ Done: implemented and backed by automated test(s)
- 🟡 Partial: implemented but missing one required validation axis
- ⚪ Pending: not implemented or not validated yet

## 1. Omega: Governance & Routing

| ID   | Check Item                    | Verification Method                                                                                                                       | Status  | Evidence/Trace                                                                                                                                                                                                                                                                             |
| :--- | :---------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------- | :------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| O-01 | **Confidence Route Contract** | Validate `OmegaDecision` carries `route/confidence/risk/fallback/tool_trust_class`, and route decisions are emitted as structured events. | ✅ Done | `packages/rust/crates/omni-agent/src/contracts/omega.rs`; `packages/rust/crates/omni-agent/tests/contracts/test_runtime_contracts.rs`; `packages/rust/crates/omni-agent/src/agent/mod.rs` (`session.route.decision_selected`)                                                              |
| O-02 | **Failure Fallback**          | Fault-inject bridge path and verify fallback action is applied deterministically without context corruption.                              | ✅ Done | `packages/rust/crates/omni-agent/tests/agent_injection.rs` (`omega_shortcut_retries_without_metadata_after_bridge_error`); `packages/rust/crates/omni-agent/src/agent/mod.rs` (`session.route.fallback_applied`)                                                                           |
| O-03 | **Next-Turn Policy Coupling** | Verify reflection outputs can influence next-turn route policy via hint application.                                                      | ✅ Done | `packages/rust/crates/omni-agent/src/agent/reflection_runtime_state.rs`; `packages/rust/crates/omni-agent/src/agent/omega/decision.rs` (`apply_policy_hint`); `packages/rust/crates/omni-agent/tests/agent/reflection.rs`; `packages/rust/crates/omni-agent/tests/agent/omega_decision.rs` |

## 2. Xiuxian-Qianhuan: Injection & Snapshots

| ID   | Check Item                | Verification Method                                                                                               | Status  | Evidence/Trace                                                                                                                                                                                                                                                        |
| :--- | :------------------------ | :---------------------------------------------------------------------------------------------------------------- | :------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| X-01 | **Snapshot Immutability** | Verify snapshot contract stability and invariant validation (`max_chars`, `max_blocks`, deterministic roundtrip). | ✅ Done | `packages/rust/crates/xiuxian-qianhuan/tests/contracts/test_injection_contracts.rs` (`injection_snapshot_content_hash_is_stable_across_turn_loop` + roundtrip/budget tests)                                                                                           |
| X-02 | **Semantic Anchors**      | Verify anchor categories (`safety`, `policy`) are non-evictable during block pressure and char-budget truncation. | ✅ Done | `packages/rust/crates/omni-agent/src/agent/injection/assembler.rs` (anchor-priority budget path); `packages/rust/crates/omni-agent/src/agent/injection/tests.rs` (`anchor_categories_survive_block_and_char_budget_pressure`)                                         |
| X-03 | **Hybrid Mode Assembly**  | Verify `RoleMixProfile` is selected/attached for multi-domain queries and emitted in snapshot traces.             | ✅ Done | `packages/rust/crates/omni-agent/src/agent/injection/assembler.rs` (`select_role_mix`); `packages/rust/crates/omni-agent/src/agent/injection/tests.rs`; `packages/rust/crates/omni-agent/tests/agent_injection.rs` (shortcut metadata includes `role_mix_profile_id`) |

## 3. LinkGraph: PPR & Structural Influence

| ID   | Check Item                                   | Verification Method                                                                                                   | Status     | Evidence/Trace |
| :--- | :------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------- | :--------- | :------------- |
| G-01 | **PPR Latency (<50ms)**                      | Benchmark the `xiuxian-wendao` LinkGraph PPR kernel on 10k+ node fixture (new WG2 benchmark target).                  | ⚪ Pending |                |
| G-02 | **Structural Weight Effectiveness (Wendao)** | Search "Architecture". Verify high-structure nodes (for example MOC-style hubs) rank in Top-3 with configured priors. | ⚪ Pending |                |
| G-03 | **HippoRAG Seed Accuracy**                   | Verify `Librarian` semantic seeds correctly ground the PPR random walk.                                               | ⚪ Pending |                |

## 4. Qianhuan-Architect: Agentic KG Construction

| ID   | Check Item                      | Verification Method                                                                 | Status     | Evidence/Trace                                                                                                                                     |
| :--- | :------------------------------ | :---------------------------------------------------------------------------------- | :--------- | :------------------------------------------------------------------------------------------------------------------------------------------------- |
| A-01 | **Implicit Discovery Accuracy** | Sample `suggested_link` traces and audit generated bridge reasoning quality.        | ⚪ Pending | No runtime `suggested_link` audit harness bound to this checklist yet                                                                              |
| A-02 | **Provisional Link Isolation**  | Verify provisional links stay isolated from normal retrieval before promotion gate. | ⚪ Pending | Requires dedicated integration test against provisional-link path                                                                                  |
| A-03 | **Entity Alias Mapping**        | Verify aliases resolve to canonical nodes during query and graph traversal.         | 🟡 Partial | `packages/rust/crates/xiuxian-wendao/tests/test_graph.rs` (alias search coverage); gap: add cross-session isolation + promotion boundary assertion |

## 5. 3-in-1 Gate & Memory Lifecycle

| ID   | Check Item                    | Verification Method                                                                          | Status  | Evidence/Trace                                                                                                                                                                                                             |
| :--- | :---------------------------- | :------------------------------------------------------------------------------------------- | :------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M-01 | **Utility-Based Promotion**   | Verify repeated successful episode accumulates utility and reaches `promote` verdict.        | ✅ Done | `packages/rust/crates/omni-agent/tests/agent_memory_gate_flow.rs` (`repeated_success_turns_reuse_episode_and_reach_promote_threshold`); `packages/rust/crates/omni-memory/src/gate.rs`                                     |
| M-02 | **Purge Validation**          | Verify obsolete verdict triggers deterministic purge of episode and Q-table entry.           | ✅ Done | `packages/rust/crates/omni-agent/tests/agent_memory_gate_flow.rs` (`repeated_failure_turns_trigger_obsolete_and_purge_episode`); `packages/rust/crates/omni-agent/src/agent/persistence.rs`                                |
| M-03 | **Reflection Record Quality** | Verify reflection lifecycle and hint derivation quality under complex, multi-step scenarios. | ✅ Done | `packages/rust/crates/omni-agent/tests/agent/reflection.rs` (`reflective_runtime_long_horizon_quality_thresholds`); CI gate binding in `scripts/channel/test_omni_agent_memory_ci_gate.py` (`run_reflection_quality_gate`) |

## 6. Observability & System Integrity

| ID   | Check Item                  | Verification Method                                                                                             | Status  | Evidence/Trace                                                                                                                                                                                                                                                                                             |
| :--- | :-------------------------- | :-------------------------------------------------------------------------------------------------------------- | :------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S-01 | **End-to-End Traceability** | Reconstruct turn path from route/injection/reflection/memory events using structured logs and report artifacts. | ✅ Done | `scripts/channel/reconstruct_omni_agent_trace.py`; `scripts/channel/test_omni_agent_memory_ci_gate.py` (`run_trace_reconstruction_gate`, `assert_trace_reconstruction_quality`); `packages/python/agent/tests/unit/channel/test_reconstruct_omni_agent_trace.py`; `scripts/channel/test_memory_ci_gate.py` |
| S-02 | **Schema Integrity**        | Validate route/memory/discover contracts remain schema-compatible and test-covered.                             | ✅ Done | `packages/shared/schemas/omni.agent.route_trace.v1.schema.json`; `packages/rust/crates/omni-agent/tests/contracts/test_runtime_contracts.rs`                                                                                                                                                               |

---

## 7. Audit Log / Decision Journal

_Use this section to record "Why" a check failed or was modified._

- **2026-02-19:** Audit Checklist initialized based on HippoRAG and H-MAC research integration.
- **2026-02-20:** Regression pass updated O/X/A/M statuses with concrete runtime-test evidence and explicit gap notes.
- **2026-02-20:** Injection track closed: X-01/X-02/X-03 promoted to Done with contract + runtime tests and shortcut metadata trace validation.
- **2026-02-20:** Reflection quality gate closed: M-03 promoted to Done with long-horizon threshold test and CI gate wiring.
- **2026-02-20 (Live multi-group):** three-group live matrix passed with `19/19` steps (`.run/reports/agent-channel-session-matrix-live.json`), live evolution DAG passed with quality score `99.0` (`.run/reports/omni-agent-memory-evolution-live.json`), and live trace reconstruction reached score `100.0` with route/injection/reflection/memory stages present (`.run/reports/omni-agent-trace-reconstruction-live.json`).
- **2026-02-20 (Nightly replay, 17:35 UTC):** full A1-A7 memory CI gate passed (`.run/logs/memory-ci-nightly-latest.log`), including matrix `19/19` (`.run/reports/agent-channel-session-matrix.json`), evolution `quality_score=98.5` (`.run/reports/omni-agent-memory-evolution.json`), benchmark with `mcp_error_turns=0` (`.run/reports/omni-agent-memory-benchmark.json`), and trace reconstruction `quality_score=100.0` with route/injection/reflection/memory present (`.run/reports/omni-agent-trace-reconstruction.json`).
- **2026-02-20 (A7 mandatory gate replay, 17:51 UTC):** nightly A7 path passed with enforced settings (`--benchmark-iterations 3`, waiting-warning budget all zero) using `scripts/channel/test_omni_agent_memory_ci_gate.py --profile nightly --skip-matrix --skip-evolution ...`; report/log evidence: `.run/reports/omni-agent-memory-benchmark-nightly-61434-1771609391684.json`, `.run/reports/omni-agent-trace-reconstruction-nightly-61434-1771609391684.json`, `.run/logs/memory-ci-nightly-a7-latest.log`.
- **2026-02-20 (Runbook formalization):** added `docs/testing/omni-agent-live-multigroup-runbook.md` and indexed it in `docs/testing/README.md` and `docs/index.md` to standardize `Test1/Test2/Test3` live evidence capture.

## 8. A1-A7 Remaining Gaps (Execution-Focused)

1. No blocking A1-A7 execution gaps remain; keep running the live multi-group runbook per release cut.
