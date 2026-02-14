# Milestone: Unified Search, Contracts & Keyword Backend Decision (Feb 2026)

**Status:** Completed  
**Scope:** Router/retrieval contract consistency, route explain API, Tantivy vs Lance FTS decision loop.

---

## Summary

This milestone closed the mainline work for (1) unified search and schema contracts, (2) route test JSON contract and CI, (3) routing score transparency (explain API), and (4) Tantivy vs Lance FTS decision with a fixed evaluation set and reproducible reports.

---

## Delivered

### 1. Contract and configuration

- **Single field for tool-search keywords:** Analytics and tool-search payloads use `routing_keywords` only; `keywords` is deprecated and removed from analytics output.
- **Snapshot contracts in version control:** `hybrid_payload_contract_v1.json` and `vector_payload_contract_v1.json` are committed; snapshot tests no longer depend on unversioned files.
- **Router rerank:** Only `router.search.rerank` is used; no fallback to legacy `rag.rust_search.rerank`. Indexer uses `parse_tool_search_payload` only.

### 2. Route CLI and E2E contract

- **Route CLI tests:** All route command tests use `_strip_ansi(result.output)` for assertions and JSON parsing so Rich ANSI does not break tests.
- **Route test JSON schema:** `packages/shared/schemas/omni.router.route_test.v1.schema.json` defines the shape of `omni route test --json` (top-level and `results[]`; optional `explain`, `file_path`; `confidence_profile.name` may be null).
- **Contract E2E in CI:** Foundation test `test_route_test_cli_json_validates_against_schema` runs in CI; it runs `omni route test "git commit" --local --json`, strips ANSI, validates JSON against the schema, and asserts no `keywords` (only `routing_keywords`).

### 3. Route explain API (score transparency)

- **Hybrid search:** Each result carries `payload.vector_score` and `payload.keyword_score` when present.
- **Route CLI:** `--explain` / `-e` with `--json` adds per-result `explain.scores`: `raw_rrf`, `vector_score`, `keyword_score`, `final_score`.
- **Schema:** Result item in route test schema includes optional `explain` with the above structure.
- **Docs:** `docs/reference/cli.md` and `docs/developer/cli.md` describe `--json --explain` usage.

### 4. Tantivy vs Lance FTS decision loop

- **Fixed evaluation set:** Rust test `test_keyword_backend_quality` with scenarios v1–v4; **v4_large** (120 queries, 10 scene layers) is the primary snapshot for decisions.
- **Decision report script:** `scripts/generate_keyword_backend_decision_report.py` defaults to v4_large, adds a per-scene summary (Tantivy vs Lance FTS vs tie by scene), and writes `docs/testing/keyword-backend-decision-report.md`.
- **Statistical report script:** `scripts/generate_keyword_backend_statistical_report.py` defaults to v4_large and writes bootstrap CI, sign test, and per-scene policy winner to `docs/testing/keyword-backend-statistical-report.md`.
- **Canonical decision doc:** `docs/testing/keyword-backend-decision.md` is the single entry point: default (Tantivy), when to use Lance FTS (single data plane), fallback policy, and how to regenerate (snapshots → `just keyword-backend-report` → `just keyword-backend-statistical`).
- **Just targets:** `just keyword-backend-report` and `just keyword-backend-statistical` regenerate the two reports from the v4 snapshot.

---

## Follow-up (out of scope for this milestone)

- **Explain: field-level contribution** – Which document fields contributed to the score; requires Rust-side support and is deferred.
- **Large-workspace batch convergence** – Any future work on very large workspaces (batching/throttling) is not part of this milestone.

---

## References

| Topic                         | Document                                                                                                                                 |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Route test schema             | `packages/shared/schemas/omni.router.route_test.v1.schema.json`                                                                          |
| Schema contract (no keywords) | [Schema Singularity](../reference/schema-singularity.md), [Vector/Router Schema Contract](../reference/vector-router-schema-contract.md) |
| Keyword backend decision      | [Keyword Backend Decision](../testing/keyword-backend-decision.md)                                                                       |
| CLI explain                   | [CLI Reference](../reference/cli.md), [CLI Guide](../developer/cli.md)                                                                   |
