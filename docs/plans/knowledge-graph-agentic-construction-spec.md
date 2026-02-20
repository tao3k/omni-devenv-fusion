# Wendao Qianhuan-Architect Spec (Agentic Graph Construction)

> **Status:** Calibrated draft  
> **Target Version:** 2026.Q1  
> **Date:** February 20, 2026
> **Host Engine:** `packages/rust/crates/xiuxian-wendao/src/link_graph`
> **Retrieval Baseline Reference:** `docs/plans/link-graph-ppr-algorithm-spec.md`
> **Program Index:** `docs/plans/wendao-plan-consolidation-2026.md`

## 0. Scope Boundary in Wendao Program

This document defines the agentic extension layer only.

Boundary rules:

1. Retrieval algorithm, PPR math, and related ranking behavior are owned by `link-graph-ppr-algorithm-spec.md`.
2. This document owns only proposal, provisional storage, promotion, and traceability flow.
3. Any conflict with retrieval behavior must be resolved in the LinkGraph spec first, then propagated here.

## 1. Citation Calibration

| Scope                                           | Source                                                                                   | Validation                | Blueprint Impact                                                              |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------- | ----------------------------------------------------------------------------- |
| Large-scale autonomous multi-agent coordination | [MegaAgent](https://arxiv.org/abs/2408.09955)                                            | Verified                  | Qianhuan-Architect may spawn bounded sub-agents for large directory analysis. |
| Dynamic orchestration during execution          | [Multi-Agent Collaboration via Evolving Orchestration](https://arxiv.org/abs/2505.19591) | Verified (`NeurIPS 2025`) | Architect orchestration remains re-plannable by Omega runtime.                |

Correction:

- Prior citation `arXiv:2408.13148` for MegaAgent was incorrect and is now replaced by `arXiv:2408.09955`.

## 2. Goal

Qianhuan-Architect upgrades LinkGraph from passive parsing to controlled graph evolution:

- propose implicit links with evidence,
- reconcile aliases/entities,
- keep all agentic edges provisional until gate promotion.

## 3. Core Capabilities

### 3.1 Implicit Link Proposal

Trigger:

- incremental ingest,
- `omni sync knowledge`,
- explicit background maintenance window.

Flow:

1. generate candidate pairs from graph + optional hybrid signals;
2. run bridge reasoning on candidate pairs;
3. emit `suggested_link` records with confidence + evidence.

### 3.2 Alias and Entity Reconciliation

Flow:

1. extract entities from headings/frontmatter/content anchors;
2. cluster possible aliases;
3. produce canonical mapping and attach alias metadata in graph records.

### 3.3 Bounded Sub-Agent Expansion

For large Markdown trees, Architect may spawn worker sub-agents to parallelize candidate generation, but only under explicit limits:

- max concurrent workers;
- per-worker token budget;
- wall-clock budget for one build cycle.

## 4. Governance Model

### 4.1 Provisional-First Writes

Agent-suggested edges are never promoted immediately:

- initial state: `PROVISIONAL`;
- promotion requires gate evidence (`retain/obsolete/promote` path and usage outcomes).

### 4.2 Traceability Contract

Every agentic edge must carry:

- `agent_id`,
- `confidence`,
- `evidence`,
- `created_at`,
- `promotion_state`.

## 5. Runtime Integration Blueprint

1. Omega orchestrates when Architect runs and when to re-plan.
2. LinkGraph provides deterministic graph context and retrieval signals.
3. Librarian/vector remains optional for candidate narrowing, not mandatory full-corpus dependency.
4. Writes and reads must stay inside the `xiuxian-wendao` common engine path (no skill-local graph mutation logic).

## 6. Implementation Phases

1. **Phase A:** Passive logging only (no graph mutation).
2. **Phase B:** Surface provisional edges in hybrid search responses.
3. **Phase C:** Enable gated promotion to durable graph edges.
4. **Phase D:** Enable bounded sub-agent expansion for large repositories.

## 7. Acceptance Gates

Functional:

- no direct write from agentic proposal to verified edge;
- full audit trail for every promoted edge.

Safety:

- deterministic rollback for rejected proposals;
- strict schema validation at proposal and promotion boundaries.

Performance:

- bounded runtime for large-directory proposal cycles;
- no unbounded memory growth under repeated background runs.
