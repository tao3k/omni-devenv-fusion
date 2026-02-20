# Architecture Audit and Blueprint Calibration (2026)

> **Status:** Calibrated against primary paper sources  
> **Target:** Xiuxian-Wendao LinkGraph-first Workflow  
> **Date:** February 20, 2026
> **Program Index:** `docs/plans/wendao-plan-consolidation-2026.md`

## 1. Citation Calibration (Primary Sources)

| Topic                            | Source                                                                                   | Validation                | Blueprint Impact                                                                                       |
| -------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------ |
| Omega evolving orchestration     | [Multi-Agent Collaboration via Evolving Orchestration](https://arxiv.org/abs/2505.19591) | Verified (`NeurIPS 2025`) | Omega is modeled as dynamic orchestration during execution, not one-shot routing.                      |
| LinkGraph PPR retrieval          | [HippoRAG](https://arxiv.org/abs/2405.14831)                                             | Verified (`NeurIPS 2024`) | Replace multi-hop BFS style related retrieval with single-step PPR ranking over graph state.           |
| Graph retrieval scaling          | [GRAG](https://arxiv.org/abs/2405.16506)                                                 | Verified (arXiv preprint) | Add divide-and-conquer subgraph retrieval path for large Markdown graphs.                              |
| Graph+vector hybrid alignment    | [HybridRAG](https://arxiv.org/abs/2408.04948)                                            | Verified (arXiv preprint) | Keep entity-aligned graph/vector hybrid policy; avoid full-corpus vector-first execution.              |
| Large-scale multi-agent spawning | [MegaAgent](https://arxiv.org/abs/2408.09955)                                            | Verified and corrected    | Correct prior wrong citation (`2408.13148`); keep dynamic sub-agent generation as budgeted capability. |

Notes:

- The previous reference of `2408.13148` for MegaAgent was incorrect and is now corrected.
- Affiliation claims (for example specific company attribution) are intentionally omitted unless explicitly verified in paper metadata.

## 1.1 Wendao Document Merge Contract

These plans are now merged under one `xiuxian-wendao` program contract to avoid drift:

| Document                                                  | Scope                                                     | Authority                                                      |
| --------------------------------------------------------- | --------------------------------------------------------- | -------------------------------------------------------------- |
| `docs/plans/link-graph-ppr-algorithm-spec.md`             | LinkGraph retrieval algorithm and execution backlog       | Single source of truth for retrieval logic and rollout gates.  |
| `docs/plans/knowledge-graph-agentic-construction-spec.md` | Agentic edge proposal/promotion workflow                  | Extension layer only; must not redefine retrieval kernel.      |
| `docs/plans/architecture_audit_report_2026.md`            | Research calibration and top-level architecture decisions | Program-level rationale and cross-document consistency anchor. |

Conflict resolution order:

1. Retrieval algorithm conflict -> follow `link-graph-ppr-algorithm-spec.md`.
2. Agentic workflow conflict -> follow `knowledge-graph-agentic-construction-spec.md`.
3. Terminology/version/citation mismatch -> reconcile in this architecture audit first, then propagate.

## 2. Calibrated Architecture Decisions

### 2.1 Omega: Dynamic Evolving Orchestration

Omega is the runtime orchestrator and must be allowed to re-plan during execution:

- introduce `agent.omega.re_plan` event hook;
- trigger re-plan when trajectory drifts (quality gate fail streak, repeated tool failures, graph timeout cascade);
- support expert reassignment, not only route selection.

### 2.2 LinkGraph Retrieval: Single-Step PPR Core

For related-note retrieval, the baseline algorithm becomes:

- seed selection from query intent and graph matches;
- one PPR propagation on the current graph state;
- top-k ranking by steady-state score.

This explicitly replaces BFS-only related traversal as the primary ranking path.

### 2.3 Large Graph Scaling: Divide-and-Conquer Subgraphs

For large repositories, retrieval runs in staged form:

- build candidate subgraphs from query seeds and structural filters;
- run PPR inside each subgraph;
- fuse scored candidates with deterministic tie-break rules.

This keeps latency bounded when graph size grows to tens of thousands of notes.

### 2.4 Graph-First Hybrid Policy

Default policy remains graph-first:

- use graph retrieval first (`graph_only` path when confidence is sufficient);
- escalate to hybrid/vector only when confidence is low or graph search times out;
- keep vector usage scoped by scenario to control token and embedding cost.

### 2.5 Qianhuan-Architect: Budgeted Sub-Agent Expansion

Dynamic agent spawning is retained as an optional capability:

- only for high-complexity directories or tasks;
- bounded by explicit concurrency and token budgets;
- all generated links remain provisional until gate promotion.

## 3. Current Code Reality Check (2026-02-20)

Already present:

- `search_planned` and `path_fuzzy` strategy are available in Wendao backend and policy routing.
- schema-based contracts and monitor signals exist for retrieval path observability.

Partially complete:

- divide-and-conquer subgraph retrieval kernel exists in Wendao PPR path, but benchmark gates
  and partition observability events are not complete yet.

Not yet complete:

- Omega re-plan hook is not yet wired as a first-class runtime event.

## 4. Next Objectives (After This Calibration)

1. Add benchmark and regression gates for subgraph partition/fusion.
2. Add PPR partition/fusion observability fields and monitor-phase events for runtime diagnosis.
3. Add `agent.omega.re_plan` event contract and runtime trigger policy.
4. Keep skills as thin wrappers; place algorithmic logic in common engine layers only.
