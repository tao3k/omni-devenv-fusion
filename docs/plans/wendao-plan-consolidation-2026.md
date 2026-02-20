# Wendao Plan Consolidation (2026)

> Status: Active  
> Date: February 20, 2026  
> Program: `xiuxian-wendao` LinkGraph and agentic graph evolution

## 1. Purpose

Unify LinkGraph-related plan documents into one execution entrypoint so implementation does not drift across parallel drafts.

## 2. Canonical Document Set

| Role                                            | Document                                                  | Ownership                                          |
| ----------------------------------------------- | --------------------------------------------------------- | -------------------------------------------------- |
| Retrieval algorithm source of truth             | `docs/plans/link-graph-ppr-algorithm-spec.md`             | `xiuxian-wendao` LinkGraph core (`src/link_graph`) |
| Agentic proposal and promotion policy           | `docs/plans/knowledge-graph-agentic-construction-spec.md` | Qianhuan-Architect extension on top of LinkGraph   |
| Research calibration and architecture rationale | `docs/plans/architecture_audit_report_2026.md`            | Program-level architecture audit                   |

Conflict policy:

1. Retrieval behavior conflict -> resolve in `link-graph-ppr-algorithm-spec.md`.
2. Agentic lifecycle conflict -> resolve in `knowledge-graph-agentic-construction-spec.md`.
3. Citation or terminology mismatch -> resolve in `architecture_audit_report_2026.md`, then propagate.

## 3. Unified Execution Backlog (Wendao)

1. W0 Contracts (Done)

- Add PPR-related schema fields and keep Python/Rust model parity.
- Gate:
  `uv run pytest packages/python/foundation/tests/unit/api/test_link_graph_search_options_schema.py -q`

2. W1 PPR Kernel (Done)

- Implement PPR scorer in `packages/rust/crates/xiuxian-wendao/src/link_graph/index`.
- Gate:
  `cargo test -p xiuxian-wendao --test test_link_graph`

3. W2 Replace `related` BFS Path (Done)

- Route related retrieval through PPR ranking.
- Gate:
  `cargo test -p xiuxian-wendao --test test_link_graph test_link_graph_neighbors_related_metadata_and_toc`

4. W3 Subgraph Partition and Fusion (In progress)

- Add divide-and-conquer path for large graph queries with bounded resource budgets.
- Gate:
  `uv run python scripts/benchmark_wendao_related.py --root . --stem README --runs 5 --warm-runs 1 --no-build --ppr-subgraph-mode auto`

5. W4 Agentic Graph Evolution

- Keep all suggested edges provisional first, add promotion traceability.
- Gate:
  proposal and promotion boundary tests in `xiuxian-wendao` plus schema validation in foundation layer.

6. W5 Default Rollout (Done for related path)

- Default related retrieval behavior is PPR-only.
- No compatibility ranking path is retained.

## 4. Change Control Rules

1. No skill-layer implementation of graph core algorithms.
2. Python stays as binding/adapter for `xiuxian-wendao` runtime behavior.
3. All plan updates must include:

- changed command(s),
- changed gate(s),
- changed owner module(s).
