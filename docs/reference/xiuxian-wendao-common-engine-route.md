# Xiuxian-Wendao Common Engine Route (from ZK + Rucola + IWE Audit)

Date: 2026-02-18  
Status: Execution blueprint (ecosystem-aligned)

## Goal

Build one modular, high-performance LinkGraph backend for Omni that:

- supports multiple document formats (`markdown` now, `org` next),
- scales to many skills with one common API,
- has strict schema validation and deterministic cache invalidation/rebuild.

## Current Codebase Snapshot (What Already Exists vs Gaps)

Already in place:

- Common backend contract exists at
  `packages/python/foundation/src/omni/rag/link_graph/backend.py`.
- Common policy router exists at
  `packages/python/foundation/src/omni/rag/link_graph/policy.py`
  (`graph_only | hybrid | vector_only`).
- Shared record schema API exists at
  `packages/python/foundation/src/omni/foundation/api/link_graph_schema.py`
  and `packages/shared/schemas/omni.link_graph.record.v1.schema.json` (legacy cross-runtime contract).

Current gaps:

- `WendaoLinkGraphBackend` now has a working Rust engine path at
  `packages/python/foundation/src/omni/rag/link_graph/wendao_backend.py`
  (`search`, `neighbors`, `related`, `metadata`, `toc`, `stats`), but
  full behavior parity and production rollout still need broader benchmark and e2e validation.
- Factory default is now `wendao` at
  `packages/python/foundation/src/omni/rag/link_graph/factory.py` (single backend path).
- Rust CLI binary `wendao` is now provided by
  `packages/rust/crates/xiuxian-wendao/src/bin/wendao.rs`
  (for example: `cargo run -p xiuxian-wendao -- search "architecture"`).
- Common incremental index refresh API is now exposed at
  `WendaoLinkGraphBackend.refresh_with_delta(changed_paths, force_full=False)`,
  with monitor phases:
  `link_graph.index.delta.plan`, `link_graph.index.delta.apply`,
  `link_graph.index.rebuild.full`.
- Delta/full decision and fallback execution are now Rust-owned via
  `PyLinkGraphEngine.refresh_plan_apply(...)`; Python replays Rust phase events
  and keeps only cache invalidation + contract mapping.
- Live-Wire watcher now routes `SKILL.md` changes to LinkGraph delta refresh via
  common backend API (`packages/python/core/src/omni/core/kernel/watcher.py`),
  so hot-reload keeps graph index consistent without skill-layer custom logic.
- Live-Wire watcher now also watches LinkGraph markdown roots resolved from:
  `link_graph.watch_dirs` (explicit) or
  `link_graph.include_dirs` / `link_graph.include_dirs_auto_candidates`
  (derived), with patterns from `link_graph.watch_patterns`,
  then triggers common `refresh_with_delta`.
- Delta refresh planning now follows
  `link_graph.index.delta.full_rebuild_threshold` for automatic
  delta-vs-full selection under large change batches.
- Knowledge command/search surface is now routed through common LinkGraph API:
  `omni knowledge stats`, `knowledge.link_graph_toc`, `knowledge.link_graph_stats`, `knowledge.link_graph_links`,
  `knowledge.link_graph_find_related`, `search(mode=link_graph)`, and `search(mode=hybrid)` policy routing.
- `search(mode=link_graph|hybrid)` now uses common LinkGraph stats cache for fast-path observability:
  it prefers cached `graph_stats`, then does a short-budget probe via common helper,
  and schedules async refresh on miss (no full synchronous stats scan on every query).
  Response shape is stable even on cold cache (`total_notes/orphans/links_in_graph/nodes_in_graph`).
  Search responses also expose `graph_stats_meta` (`source`, `cache_hit`, `fresh`,
  `age_ms`, `refresh_scheduled`) for debugging freshness/perf behavior.
- `WendaoLinkGraphBackend.stats()` now uses Valkey persistent cache under
  `<link_graph.cache.key_prefix>:stats:*` with TTL control
  (`link_graph.stats_persistent_cache_ttl_sec`) and lazy engine initialization.
  This removes repeated cold-start graph rebuild for `knowledge.link_graph_stats`
  in short repeated CLI runs.
- `WendaoLinkGraphBackend` now supports index-scope controls:
  `link_graph.include_dirs` (relative whitelist, optional) and
  `link_graph.exclude_dirs` (additional non-hidden directories, optional).
  Hidden/runtime directories are always auto-excluded by built-in policy.
  This keeps LinkGraph focused on project knowledge paths and avoids environment/cache noise.
- Current LinkGraph cache strategy is db-first (Valkey):
  - Rust index snapshot cache is stored in Valkey by key prefix
    `xiuxian_wendao:link_graph:index:*` (configurable via `link_graph.cache.key_prefix`).
  - Redis URL resolution contract for LinkGraph cache is unified and config-first:
    `link_graph.cache.valkey_url` first, then `VALKEY_URL` fallback.
  - Default system config provides local development URL
    (`redis://127.0.0.1:6379/0`); production/user override should use
    user `wendao.yaml` or `VALKEY_URL`.
  - LinkGraph cache no longer falls back to unrelated runtime/session/discover
    Redis settings. This avoids cross-domain coupling and keeps cache behavior
    deterministic across skills.
  - Python common stats cache also uses Valkey (`<key_prefix>:stats:*`) with strict schema
    `xiuxian_wendao.link_graph.stats.cache.v1`; file-backed stats cache is removed.
  - Python only bridges config + query calls to Rust engine and propagates
    `XIUXIAN_WENDAO_LINK_GRAPH_VALKEY_*` + `VALKEY_URL` env contract; indexing/cache ownership remains in Rust.
- When `link_graph.include_dirs` is empty, common backend can auto-select existing
  directories from `link_graph.include_dirs_auto_candidates` when
  `link_graph.include_dirs_auto=true`, so project-wide defaults can stay lean
  without per-skill hardcoding.
- Rust parser now extracts wiki-links (`[[note]]`) and markdown links
  (`[text](../path/file.md#anchor)` and reference-style `[text][id]` + `[id]: ...`),
  with relative-path normalization and anchor stripping, improving graph edge
  coverage for standard markdown docs.
- `unified_knowledge` read APIs (`search`, `get_graph`, `find_related`, `get_stats`, `list_by_tag`)
  now consume common LinkGraph backend instead of direct legacy CLI reads.
- `unified_knowledge.add_entity` now calls backend-level `create_note` when available.
  Legacy `link_graph_client` fallback paths were removed; common backend is the only route.
- `link_graph_navigator` anchor/expand traversal now consumes common LinkGraph backend
  (`search`, `neighbors`, `metadata`) instead of legacy direct ZK CLI calls.
- Legacy `dual_core/vector_bridge` path is retired. The current skill-side
  entry is `assets/skills/knowledge/scripts/link_graph_search.py`; remaining
  gap is Rust-native backend/query implementation parity.

Conclusion:

- We should keep the current Python API surface and replace backend internals.
- Skills must remain thin wrappers; all heavy logic belongs to common layers.

## External Learning, Adapted to Omni (Not Copy-Paste)

From PageIndex we adopt the mechanism, not the stack:

- tree/structure-first narrowing,
- budgeted search depth/branching,
- optional semantic stage only on narrowed candidates.

This means Omni retrieval should follow:

1. structural graph hit discovery,
2. candidate source narrowing,
3. optional semantic/vector fallback only when graph confidence is low,
4. optional synthesis/rerank on the small candidate set.

This avoids full-corpus vectorization cost while keeping strong semantic reach.

## Source Audit: What to Reuse vs What to Avoid

### ZK (strong indexing/query architecture)

Use as reference:

- Parser/index are injected via ports in one container wiring:
  - `.cache/researcher/zk-org/zk/internal/cli/container.go:100`
  - `.cache/researcher/zk-org/zk/internal/cli/container.go:111`
  - `.cache/researcher/zk-org/zk/internal/cli/container.go:112`
- SQLite schema + FTS5 + trigger-based sync:
  - `.cache/researcher/zk-org/zk/internal/adapter/sqlite/db.go:90`
  - `.cache/researcher/zk-org/zk/internal/adapter/sqlite/db.go:123`
  - `.cache/researcher/zk-org/zk/internal/adapter/sqlite/db.go:130`
- Versioned migration with reindex flag:
  - `.cache/researcher/zk-org/zk/internal/adapter/sqlite/db.go:230`
  - `.cache/researcher/zk-org/zk/internal/adapter/sqlite/db.go:246`
- Rich query in one engine (FTS/regex/exact + link recursion + related):
  - `.cache/researcher/zk-org/zk/internal/adapter/sqlite/note_dao.go:548`
  - `.cache/researcher/zk-org/zk/internal/adapter/sqlite/note_dao.go:740`
  - `.cache/researcher/zk-org/zk/internal/adapter/sqlite/note_dao.go:669`
- Incremental indexing by source/target diff:
  - `.cache/researcher/zk-org/zk/internal/core/note_index.go:162`

Avoid copying directly:

- License is GPL:
  - `.cache/researcher/zk-org/zk/LICENSE:1`

### Rucola (strong local workflow ideas, weak scale characteristics)

Use as reference:

- `comrak` markdown parsing with wikilinks:
  - `.cache/researcher/Linus-Mussmaecher/rucola/src/data/note.rs:67`
  - `.cache/researcher/Linus-Mussmaecher/rucola/src/data/note.rs:73`
- Local cache snapshot for quick restart:
  - `.cache/researcher/Linus-Mussmaecher/rucola/src/data/index.rs:36`
  - `.cache/researcher/Linus-Mussmaecher/rucola/src/data/index.rs:260`
- File event driven incremental updates:
  - `.cache/researcher/Linus-Mussmaecher/rucola/src/data/index.rs:121`
  - `.cache/researcher/Linus-Mussmaecher/rucola/src/io/file_tracker.rs:83`

Avoid for core scale path:

- Backlink queries scan full in-memory map:
  - `.cache/researcher/Linus-Mussmaecher/rucola/src/data/index.rs:229`
- Full-text filter reads files at query time:
  - `.cache/researcher/Linus-Mussmaecher/rucola/src/data/filter.rs:181`
- License is GPL-3.0-only:
  - `.cache/researcher/Linus-Mussmaecher/rucola/Cargo.toml:12`

### IWE (strong graph primitives, not full backend fit as-is)

Use as reference:

- Parallel parse/build and ref index construction:
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/graph.rs:332`
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/graph.rs:357`
- Graph path extraction utilities:
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/graph/path.rs:74`

Known limitations for direct adoption:

- Search is fuzzy lexical path/text, not semantic:
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server/search.rs:57`
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server/search.rs:85`
- Watched file `CREATED/CHANGED` path in LSP server is no-op:
  - `.cache/researcher/iwe-org/iwe/crates/iwes/src/router/server.rs:118`
- Parser stack is `pulldown-cmark` (not `comrak`):
  - `.cache/researcher/iwe-org/iwe/crates/liwe/src/markdown/reader.rs:6`

## Target Architecture (Highly Modular)

### 1) Format Layer (`xiuxian_wendao::format`)

- `format::traits`:
  - `DocumentParser` (parse text -> canonical IR)
  - `DocumentNormalizer` (normalize paths, anchors, aliases)
- `format::markdown_comrak` (primary now)
- `format::org` (future module, same trait contract)

Rule: Query/index layers never import parser internals; they only consume canonical IR.

### 2) Canonical IR Layer (`xiuxian_wendao::ir`)

- `DocumentRecord`
- `NodeRecord` (heading/section/block anchors)
- `EdgeRecord` (source, target, edge_type, distance)
- `TagRecord`

All persisted records must validate against shared schemas under `packages/shared/schemas`.

### 3) Storage Layer (`xiuxian_wendao::store`)

- `store::doc` (raw doc metadata/checksum)
- `store::graph` (nodes/edges)
- `store::term` (optional lexical index hooks)
- `store::cache` (Valkey snapshot/state cache)
- `store::migrations`

Recommended baseline: SQLite (WAL + migrations + recursive CTE support), while vector storage remains in existing Omni vector store.

### 4) Index Layer (`xiuxian_wendao::index`)

- `index::planner` (diff vs full rebuild)
- `index::delta` (apply add/update/remove)
- `index::rebuild` (deterministic full rebuild path)
- `index::consistency` (post-index invariants, broken edge checks)

### 5) Query Layer (`xiuxian_wendao::query`)

- `query::search` (lexical graph search over titles/paths)
- `query::neighbors` (incoming/outgoing with hop bounds)
- `query::related` (distance + overlap scoring)
- `query::metadata` (tags/aliases/path)
- `query::budget` (max expansion/depth/timeout guardrails)
- `query::confidence` (graph confidence signal for policy escalation)

### 6) Runtime & Cache Layer (`xiuxian_wendao::runtime`)

- `runtime::bootstrap` (config + backend startup)
- `runtime::cache` (Valkey read/write + invalidation)
- `runtime::refresh` (delta/full rebuild decision and execution)
- `runtime::telemetry`
- `runtime::locks` (single-writer safety)

## Cache Contract (Strict)

LinkGraph cache payloads must keep a strict schema contract and version gate.
Shared schema:
`packages/shared/schemas/xiuxian_wendao.link_graph.valkey_cache_snapshot.v1.schema.json`.
Stats cache schema:
`packages/shared/schemas/xiuxian_wendao.link_graph.stats.cache.v1.schema.json`.

Core fields:

- `schema_version`
- `engine_version`
- `format_versions` (`markdown`, `org`, ...)
- `index_generation`
- `created_at`
- `source_fingerprint`

Load policy:

1. validate schema/version before using cached index payload,
2. if invalid/mismatch/corrupt: discard cache entry, rebuild from canonical sources, write fresh cache atomically,
3. emit structured cache-rebuild event for observability.

## Performance Strategy

- Keep reverse-edge index to avoid O(N) backlink scans.
- Use incremental diff indexing with checksum/path metadata.
- Keep full rebuild path deterministic and benchmarked.
- Use bounded caches only at query edge; never hide stale index state.
- Reuse backend instances in the common factory cache to avoid repeated
  engine bootstrap/index-cache warmup overhead per skill call.
- Keep semantic/vector calls out of indexing path by default.
- Only embed/index vectors for opt-in scopes (for example paper corpora).

### Runtime Budget Knobs (Current Common Layer)

These settings are now consumed by the common LinkGraph engine (not skill-local code):

- `link_graph.policy.search_timeout_seconds`
- `link_graph.policy.timeout_marker_ttl_seconds`
- `link_graph.policy.search_timeout_scale.machine_like`
- `link_graph.policy.search_timeout_scale.symbol_heavy`
- `link_graph.policy.search_timeout_scale.short`
- `link_graph.policy.search_timeout_scale.long_natural`
- `link_graph.policy.search_timeout_scale.default`
- `link_graph.proximity.timeout_seconds`
- `link_graph.proximity.max_parallel_stems`
- `link_graph.proximity.max_stems`
- `link_graph.proximity.neighbor_limit`
- `link_graph.proximity.stem_cache_ttl_seconds`

Default behavior is conservative for graph retrieval: policy search is time-boxed and
proximity boost is partial under timeout, so `knowledge.recall` can fast-fallback
to vector path instead of stalling on slow graph calls.

When `policy.search` times out, common policy writes a short-lived timeout marker.
The next proximity step for the same query consumes that marker and is skipped in
O(1), removing redundant graph subprocess work in the same recall execution. The
adaptive timeout scale also lowers budget for machine-like/slug-heavy queries so
slow graph lookups fail fast and hand off to vector path earlier.

## Benchmark Snapshot (2026-02-18)

Measured with `-v` on this repository workspace.
Numbers are for regression trend tracking, not absolute SLO.

| Command                                | Run                               | skill_tool_duration | CLI elapsed | RSS delta |
| -------------------------------------- | --------------------------------- | ------------------: | ----------: | --------: |
| `knowledge.link_graph_stats`           | cold (after clearing stats cache) |             82.79ms |       0.30s |  +8.4 MiB |
| `knowledge.link_graph_stats`           | warm                              |             20.95ms |       0.24s |  +1.1 MiB |
| `knowledge.search` (`mode=link_graph`) | run #1                            |            143.44ms |       0.36s |  +7.4 MiB |
| `knowledge.search` (`mode=link_graph`) | run #2                            |            143.84ms |       0.36s |  +7.9 MiB |

Reproduce:

```bash
rm -f .cache/link_graph/stats/*.stats.json
omni skill run knowledge.link_graph_stats '{}' -v
omni skill run knowledge.link_graph_stats '{}' -v
omni skill run knowledge.search '{"query":"architecture","mode":"link_graph","max_results":5}' -v
omni skill run knowledge.search '{"query":"architecture","mode":"link_graph","max_results":5}' -v
```

## Implementation Route

### Phase 0: Contract Freeze

- finalize common API and schema IDs,
- freeze record/cache JSON schema.
- define confidence and retrieval-budget contract fields.

### Phase 1: Rust Crate Skeleton

- create `packages/rust/crates/xiuxian-wendao`,
- add module tree (`format`, `ir`, `store`, `index`, `query`, `runtime`),
- add compile-only tests for boundaries.
- add FFI boundary with strict typed payloads (no ad-hoc dict pass-through).

### Phase 2: Markdown Path

- implement `markdown_comrak` parser adapter,
- implement IR conversion + schema validation tests.

### Phase 3: Storage + Migration + Cache Coherence

- implement SQLite schema migrations,
- implement Valkey cache read/write/invalidation path and failure tests.
- add schema/version mismatch tests (drop stale cache + rebuild).

### Phase 4: Query Parity

- implement `search/neighbors/related/metadata`,
- pass Python `omni.rag.link_graph` contract tests.
- implement confidence scoring and budget controls.
- integrate policy triggers in `omni.rag.link_graph.policy`.

### Phase 5: Rollout + Legacy Removal

- switch backend default to new engine,
- remove direct legacy ZK runtime path after regression and SLO gates.
- remove any remaining skill-level graph logic that bypasses common APIs.

## Gate Criteria Before Coding Org Mode

- p95 query latency and memory budget defined and met on markdown corpus,
- zero unresolved schema violations in CI,
- deterministic rebuild produces same query outputs on fixed fixture set.
- graph-first hit rate and fallback rate are measured and stable.
- no skill imports legacy ZK runtime modules directly.

## One-Shot Migration Rule (No Fragmented Ownership)

To avoid future maintenance debt:

- one common LinkGraph engine,
- one policy router,
- one schema validation entrypoint,
- one cache invalidation/rebuild strategy.

Any new skill must consume these common layers; no custom graph backend per skill.
