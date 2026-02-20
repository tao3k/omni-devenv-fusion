# ZK Replacement Blueprint: IWE + Graph-First Dual-Core Retrieval

Date: 2026-02-18  
Status: Proposed (source-audited, report-corrected)

## Scope

This document re-audits local source caches and harvested reports, then defines a future-oriented path to replace ZK in Omni’s retrieval stack.

Audited source trees:

- `.cache/researcher/iwe-org/iwe`
- `.cache/researcher/VectifyAI/PageIndex`
- `.cache/researcher/OpenBMB/UltraRAG`
- `.cache/researcher/HKUDS/RAG-Anything`
- `.cache/researcher/microsoft/graphrag`
- `.cache/researcher/zk-org/zk`

Audited harvested reports:

- `.data/harvested/iwe-org/iwe`
- `.data/harvested/VectifyAI/PageIndex`
- `.data/harvested/OpenBMB/UltraRAG`
- `.data/harvested/microsoft/graphrag`

## Executive Decision

Decision: **Go for replacing ZK as the graph backend, but not with a vector-only stack**.

Target architecture:

1. Build one **common LinkGraph engine API** in Omni.
2. Implement an **IWE-backed Rust backend** for graph/link retrieval.
3. Use **graph-first retrieval by default**, with vector fallback by policy.
4. Delete ZK legacy path after parity and SLO gates.

## Report Corrections (Harvested vs Source)

### Correction 1: PageIndex harvested report is incomplete

- Harvested shard is a placeholder and does not contain repository analysis:
  - `.data/harvested/VectifyAI/PageIndex/shards/01_full_repository_analysis.md:1`
- Source truth: PageIndex explicitly positions itself as vectorless/no chunking:
  - `.cache/researcher/VectifyAI/PageIndex/README.md:14`
  - `.cache/researcher/VectifyAI/PageIndex/README.md:16`
  - `.cache/researcher/VectifyAI/PageIndex/README.md:68`

### Correction 2: “No-vector trend” is not universal

- `PageIndex`: strong vectorless positioning (source above).
- `UltraRAG`: explicit dense+sparse hybrid and vector backends:
  - `.cache/researcher/OpenBMB/UltraRAG/examples/hybrid_search.yaml:6`
  - `.cache/researcher/OpenBMB/UltraRAG/examples/hybrid_search.yaml:7`
  - `.cache/researcher/OpenBMB/UltraRAG/servers/retriever/parameter.yaml:29`
  - `.cache/researcher/OpenBMB/UltraRAG/servers/retriever/parameter.yaml:33`
- `RAG-Anything`: explicit vector-graph fusion + hybrid query modes:
  - `.cache/researcher/HKUDS/RAG-Anything/README.md:235`
  - `.cache/researcher/HKUDS/RAG-Anything/README.md:239`
  - `.cache/researcher/HKUDS/RAG-Anything/raganything/query.py:101`
  - `.cache/researcher/HKUDS/RAG-Anything/raganything/query.py:150`
- `GraphRAG`: dedicated vector storage packages and vector search APIs:
  - `.cache/researcher/microsoft/graphrag/packages/graphrag-vectors/graphrag_vectors/lancedb.py:4`
  - `.cache/researcher/microsoft/graphrag/packages/graphrag-vectors/graphrag_vectors/lancedb.py:92`

### Correction 3: IWE capability boundaries

What is true in source:

- IWE has strong Rust graph primitives and search index:
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server/search.rs:31`
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server/search.rs:57`
- Search is fuzzy ranking over path text (`SkimMatcherV2`), capped at 100:
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server/search.rs:3`
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server/search.rs:85`
- Search index is refreshed on `didSave` and `didChange`; watched file `CREATED/CHANGED` are currently no-op (only `DELETED` updates graph/index):
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server.rs:100`
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server.rs:110`
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server.rs:118`
- Node model is richer than commonly summarized:
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/model/node.rs:11`
- Markdown parser backend is `pulldown-cmark` (not `comrak`) with YAML metadata + wikilink + table options:
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/markdown/reader.rs:6`
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/markdown/reader.rs:78`

### Correction 4: Incremental index maintenance risk in upstream graph core

What is true in source:

- Document update deletes old branch then re-parses and merges new refs:
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/graph.rs:304`
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/graph.rs:309`
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/graph.rs:268`
- Ref index supports `merge` but has no remove/subtract API:
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/graph/index.rs:18`
- `remove_document` removes keys/content but does not explicitly rebuild/clean `RefIndex` maps:
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/graph.rs:127`

Implication: for long-running Omni services, we should treat upstream incremental behavior as a reference, not a final production strategy. Our common engine should own strict delta-index or deterministic rebuild policy.

Implication: IWE is a strong graph engine candidate, but it is not a drop-in replacement for ZK CLI semantics. Omni needs a contract adapter layer.

## Comparative Matrix (ZK vs IWE vs GraphRAG Family)

| System       | Core strength                                                       | Vector dependency | Best role in Omni                                              |
| ------------ | ------------------------------------------------------------------- | ----------------- | -------------------------------------------------------------- |
| ZK           | Mature note filters (`--link-to`, `--linked-by`, `--related`, tags) | Low               | Current graph baseline (to be replaced)                        |
| IWE          | Rust graph + path index + LSP update loop                           | None required     | **Primary future graph backend**                               |
| PageIndex    | Reasoning over hierarchical ToC, vectorless positioning             | None required     | Specialized long-doc reasoning mode, not default infra backend |
| UltraRAG     | Full RAG platform with dense+sparse hybrid pipelines                | Medium/High       | Reference for hybrid orchestration, not graph-only replacement |
| RAG-Anything | Multimodal graph+vector fusion with query modes                     | Medium/High       | Reference for multimodal hybrid policy                         |
| GraphRAG     | Graph extraction + vector stack for enterprise pipelines            | High              | Reference for graph+vector composition at larger scale         |

## Future Architecture: Common Engine First

Create a backend-agnostic shared engine (single API for all skills):

- Python contract: `omni.rag.link_graph`
- Rust implementation crate: `packages/rust/crates/xiuxian-wendao` (new)
- Optional Python bridge: thin binding only (no business logic duplication in skills)

### Algorithm-Only Reuse Draft (Recommended)

This is the robust/safe design for Omni:

1. Reuse IWE/liwe graph/search algorithms, but keep storage/index ownership in Omni.
2. Keep Omni vector store and LinkGraph cache lifecycle as first-class; do not couple to upstream markdown file loader as source of truth.
3. Parse markdown in Omni ingestion path (prefer `comrak`), normalize to shared graph records, then feed Rust graph core.
4. Keep one stable cross-language API contract (`search`, `neighbors`, `related`, `metadata`) for all skills.
5. Keep skill layer thin: policy + orchestration only, no skill-specific graph logic.

Why this is safer:

- Avoids lock-in to upstream parser/storage choices while still benefiting from proven graph algorithms.
- Supports future parser upgrades (`comrak` extensions, custom syntax) without API churn.
- Makes graph engine reusable across thousands of skills because data contract is centralized.

### Cache Coherence and Auto-Rebuild Strategy (Required for Production)

To prevent stale/broken index state after interruption or schema drift:

- Keep LinkGraph cache schema/version in shared contracts with explicit `schema_version`.
- Validate cache payload at load boundary in Python and Rust.
- Implement deterministic rebuild flow in common runtime:
  - fast-path load if schema/version valid;
  - on mismatch/corruption: drop stale cache, rebuild from canonical sources, write fresh cache atomically;
  - emit structured cache-rebuild event for observability.
- Reject silent partial loads: either valid state or explicit rebuild.

This aligns with the “no backward-compatibility branch” requirement: we keep one current schema contract and deterministic invalidation/rebuild path instead of accumulating legacy runtime branches.

### Common API (strict schema)

- `search_planned(query, limit, options) -> {"query","search_options","hits"}`
- `neighbors(stem, direction, hops) -> list[NeighborHit]`
- `related(stem, max_distance, limit) -> list[RelatedHit]`
- `metadata(stem) -> LinkGraphMetadata` (tags optional)

All payloads validated by shared schema contracts before returning to skill layer.

## Retrieval Policy: Graph-First, Vector-Fallback

Use one policy contract for all skills:

- `mode=graph_only`: default for link-rich docs and notebook-centric queries.
- `mode=hybrid`: graph retrieval first, vector fallback if graph confidence is low.
- `mode=vector_only`: semantic-heavy queries or graph coverage not available.

### Automatic fallback triggers (hybrid escalation)

Escalate from graph to hybrid/vector when any condition is met:

- `graph_hit_count < min_graph_hits`
- `graph_top_score < min_graph_score`
- `coverage_ratio < min_source_coverage`
- query classified as semantic abstraction (low lexical overlap with node titles/paths)

This preserves fast, deterministic graph retrieval while keeping semantic reach only when needed.

## Why This Strategy Is Better

1. Lower cost: most requests avoid embedding/vector roundtrips.
2. Better explainability: graph path and link reasons are auditable.
3. Stronger determinism: link/tag/path constraints are exact.
4. Scales to many skills: one shared engine + one policy, thin wrappers.
5. Future-proof: IWE backend can evolve without changing skill APIs.

## Migration Plan (No Skill-Level Compatibility Branches)

### Phase 1: Contract Lock

- Add shared LinkGraph schemas and runtime validators.
- Move all graph retrieval call sites to the new API surface.
- Keep current behavior via temporary backend adapter only behind the new API.

Exit criteria:

- No skill directly imports ZK client/proximity modules.

### Phase 2: IWE Rust Backend

- Implement `IweLinkGraphBackend` in Rust crate.
- Expose minimal FFI surface to Python runtime.
- Add fixtures and contract tests.

Exit criteria:

- Contract tests pass with IWE backend.

### Phase 3: Graph-First Policy Rollout

- Switch recall/search to policy-driven retrieval mode selection.
- Default to `graph_only`, escalate to `hybrid` by triggers.

Exit criteria:

- Recall quality non-regression + latency improvement on benchmark set.

Implementation update (2026-02-18):

- `omni.rag.link_graph.policy` is now implemented as a common layer with
  `graph_only | hybrid | vector_only` routing.
- `knowledge.recall` now uses the common policy API and returns retrieval path
  metadata (`retrieval_mode`, `retrieval_path`, `retrieval_reason`).
- `vector_only` explicitly skips dual-core graph boosts to keep pure vector
  latency low and predictable.

### Phase 4: Delete ZK Legacy

- Remove ZK adapters and related docs.
- Keep one production graph engine path (IWE-backed).

Exit criteria:

- No production imports from `omni.rag.zk_*`.

## SLO and Test Gates

Required gates before final cutover:

- Functional:
  - Contract tests for `search/neighbors/related/metadata`
  - Recall regression for representative queries
  - Failure-path tests (timeout, malformed state, empty graph)
- Performance:
  - p95 recall latency non-regression vs current baseline
  - added graph boost latency p95 <= 150ms (warm)
  - memory growth bounded under repeated recalls

## Immediate Next Implementation Steps

1. Add `LinkGraphBackend` contracts and shared schema package.
2. Implement backend registry (`iwe`, `mock`, temporary `zk_adapter`).
3. Move `knowledge.recall` dual-core boost to the new API surface.
4. Add policy selector (`graph_only|hybrid|vector_only`) with measurable fallback triggers.
5. Add benchmark suite to compare graph-only vs hybrid on the same query corpus.

## Status Update (2026-02-20)

Completed in common engine path (`xiuxian-wendao` + `omni.rag.link_graph`):

1. Search API is now hard-cut to `search_planned` (legacy `search*` removed from public runtime path and guarded by contract tests).
2. Wendao FTS scoring now includes graph-reference-aware boost:
   - signal = normalized weighted degree (`incoming*2 + outgoing*1`)
   - boost applied only for non-empty `fts` queries
   - exact/regex behavior unchanged
3. Search hot path now avoids per-document temporary string aggregation during token matching.
4. Regression coverage added for:
   - search `limit` enforcement
   - rank preference for highly referenced notes under equal lexical match

Current gap vs IWE to prioritize next:

1. Path/section-aware retrieval and ranking (IWE-style `SearchPath` context rank).
2. Optional fuzzy path ranking mode (Skim-like strategy) as a selectable match strategy.
3. Incremental index update quality under high file churn (delta-index benchmarking and repair policy).
