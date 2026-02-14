# Dual-Core Knowledge Architecture

## Two Cores

|                 | Core 1: ZK                                                  | Core 2: LanceDB + Arrow                       |
| --------------- | ----------------------------------------------------------- | --------------------------------------------- |
| **Engine**      | ZK CLI (external tool)                                      | omni-vector (Rust crate)                      |
| **Strength**    | Explicit link graph, FTS, tag/date filtering                | Vector similarity, BM25, schema-aware queries |
| **Data**        | 266 markdown notes, 127 linked                              | Skill tools, knowledge chunks, embeddings     |
| **Query**       | `zk list --match --linked-by --related`                     | Hybrid vector + keyword search                |
| **Enhancement** | omni-knowledge Rust (entity extraction, relation inference) | Tantivy FTS, Arrow columnar analytics         |

## Problem: Islands

Before integration, the two cores operated independently:

```
┌─────────────────────────┐     ┌─────────────────────────┐
│   Core 1: ZK            │     │   Core 2: LanceDB       │
│                         │     │                         │
│  zk_client.py           │     │  hybrid_search.py       │
│  zk_search.py           │  ✗  │  recall.py              │
│  zk_navigator.py        │     │  rust_vector.py         │
│  zk_enhancer.py         │     │  indexer.py             │
│  unified_knowledge.py   │     │  vector_schema.py       │
└─────────────────────────┘     └─────────────────────────┘
         ✗ No data sharing
         ✗ No cross-ranking
         ✗ No shared entity registry
```

Specific disconnections:

1. **Tool Router** uses LanceDB only. ZK graph not consulted.
2. **Knowledge Recall** uses LanceDB only. ZK link proximity ignored.
3. **ZK Search** has no real vector fallback. Semantic similarity unavailable.
4. **Entity Registry** split: ZK has notes, LanceDB has tool schemas. No cross-reference.

## Solution: Dual-Core Fusion

### Principle

**ZK is the primary knowledge graph engine.** LanceDB is the high-performance structured/semantic search engine. They are equals, not fallbacks.

### Integration Points

```
┌──────────────────────────────────────────────────────────────────┐
│                    DualCoreSearch                                  │
│                                                                  │
│  Query ──► Rust extract_query_intent() ──► FusionWeights         │
│              │           (computed once, flows to all bridges)    │
│         ┌────┴────────────────────┐                              │
│         ▼                         ▼                              │
│  ┌──────────────┐       ┌──────────────────┐                    │
│  │  Core 1: ZK  │       │  Core 2: LanceDB │                    │
│  │  FTS + Graph │       │  Vector + BM25   │                    │
│  │  Traversal   │       │  Dynamic weights │                    │
│  └──────┬───────┘       └────────┬─────────┘                    │
│         │                        │                               │
│         └────────┬───────────────┘                               │
│                  ▼                                                │
│         ┌──────────────────┐                                     │
│         │  Fusion Engine   │                                     │
│         │  - RRF merge     │  (vector_weight, keyword_weight     │
│         │  - Graph boost   │   from FusionWeights → Rust RRF)   │
│         │  - Entity rerank │                                     │
│         └──────┬───────────┘                                     │
│                ▼                                                  │
│         ┌──────────────────┐                                     │
│         │  KnowledgeGraph  │  (Rust, persisted)                  │
│         │  Entity + Relation accumulation                        │
│         └──────────────────┘                                     │
└──────────────────────────────────────────────────────────────────┘
```

### Five Bridges + Intent-Driven Fusion

#### Bridge 1: ZK → Router (Graph Signal for Tool Routing)

When routing a user query to the right tool:

```
User: "help me analyze a git repo"
  1. LanceDB hybrid search → ranked tool list
  2. ZK graph check: is "git repo" linked to any skill notes?
     → If docs/reference/researcher.md links to docs/reference/git.md → boost researcher
  3. Entity graph: does KnowledgeGraph have DOCUMENTED_IN/USES relations?
     → Multi-hop boost for connected tools
```

#### Bridge 2: LanceDB → ZK Search (Intent-Aware Semantic Fallback)

When ZK search finds few results via links:

```
User: "vector search optimization"
  1. compute_fusion_weights() → zk_proximity_scale=1.0 (code target → neutral)
  2. ZK FTS + link traversal → direct matches
  3. LanceDB vector search → semantically similar notes
  4. Fuse: ZK precision boost = 1.0 + 0.5 * zk_proximity_scale (dynamic)
     Graph boost scaled by zk_entity_scale
  5. Result: ZK precision + LanceDB coverage, balanced by query intent
```

**Implementation**: `zk_search.py::ZkHybridSearcher._merge_results` uses `FusionWeights` to dynamically adjust the ZK precision multiplier and graph boost scale.

#### Bridge 3: ZK Link Proximity + KG Entity → Knowledge Recall

When recalling knowledge chunks:

```
User: "how does the routing algorithm work?"
  1. compute_fusion_weights() → shared intent analysis for all bridges
  2. LanceDB recall → top-k chunks by semantic similarity
  3. Bridge 1a: zk_link_proximity_boost(fusion_scale=zk_proximity_scale)
     → If chunk A's doc links to chunk B's doc → boost co-linked chunks
  4. Bridge 1b: apply_kg_recall_boost(fusion_scale=zk_entity_scale)
     → If chunk source matches KG entities for query keywords → boost
  5. Result: semantically relevant + structurally connected + entity-connected chunks
```

**Implementation**: `recall.py::_apply_dual_core_recall_boost` computes fusion weights once and threads them through both ZK link proximity (Bridge 1a) and KG entity recall (Bridge 1b).

#### Bridge 4: Shared Entity Registry (`register_skill_entities`)

During `omni sync` / `omni reindex`:

```
omni sync
  1. Scanner parses SKILL.md → skill metadata
  2. Index tools into LanceDB (Core 2, existing)
  3. Build skill relationship graph (keyword overlap, same-skill edges)
  4. register_skill_entities() → Rust-native batch registration
     → SKILL entities (one per skill)
     → TOOL entities (one per command)
     → CONCEPT entities (one per routing keyword)
     → CONTAINS relations: Skill → Tool
     → RELATED_TO relations: Tool → keyword:*
  5. Graph persisted to knowledge.lance (kg_entities + kg_relations) + JSON dual-write
```

**Implementation**: `dual_core/graph_enrichment.py::register_skill_entities` → `KnowledgeGraph::register_skill_entities` (Rust, `graph/skill_registry.rs`)

This bridge ensures Bridge 3 has data: when `enrich_skill_graph_from_zk` searches the KnowledgeGraph for shared entities, it finds the entities registered here during sync.

#### Bridge 5: Query-Time KG Rerank (KG → Router at search time)

When routing a user query, after initial LanceDB hybrid search:

```
User: "help me search for knowledge about async patterns"
  1. Rust extract_query_intent() → action="search", target="knowledge", keywords=["search", "knowledge", "async", "patterns"]
  2. compute_fusion_weights() → zk_proximity_scale=1.5, kg_rerank_scale=1.3 (knowledge target boosts ZK)
  3. KnowledgeGraph.query_tool_relevance(keywords, hops=2) → multi-hop graph walk
     → Finds tools connected via keyword:search, keyword:knowledge entities
  4. apply_kg_rerank() → boosts tool scores by KG relevance * fusion_scale
  5. Result: tools with graph connections to query entities rank higher
```

**Implementation**: `dual_core/kg_rerank.py::apply_kg_rerank` + `dual_core/fusion_weights.py::compute_fusion_weights` → `KnowledgeGraph::query_tool_relevance` (Rust, `graph/query.rs`)

#### Intent-Driven Fusion Weights

The Rust-native `extract_query_intent` (in `graph/intent.rs`) decomposes queries into:

- **action**: canonical verb (search, create, commit, etc.)
- **target**: domain noun (knowledge, code, git, web, etc.)
- **context**: remaining qualifiers
- **keywords**: all significant tokens (stop-words removed)

`compute_fusion_weights()` uses these signals to dynamically adjust:

- `zk_proximity_scale`: ZK link proximity boost strength (Bridge 1a, 2, 3)
- `zk_entity_scale`: ZK entity graph enrichment strength (Bridge 1b, 2, 3)
- `kg_rerank_scale`: KG query-time rerank strength (Bridge 5)
- `vector_weight` / `keyword_weight`: Rust RRF fusion weights (Bridge 5 → agentic_search)

Rules:
| Query Target | ZK Emphasis | LanceDB Emphasis |
|---|---|---|
| knowledge, docs | 1.5x ZK proximity, 1.3x KG rerank | 0.9x vector |
| code, database, skill | 0.7x ZK proximity | 1.2x vector, 1.3x keyword |
| git (via action) | 0.8x ZK proximity | 1.4x keyword |
| (default) | 1.0x balanced | 1.0x balanced |

**Key architectural property**: No bridge computes fusion weights independently.
The `FusionWeights` object flows top-down from a single `compute_fusion_weights()` call,
eliminating redundant Rust calls and ensuring all bridges agree on query classification.

## Responsibility Split

### ZK CLI (External Tool)

- Scan all markdown files
- Detect links (markdown + wiki format)
- FTS, tag filtering, date filtering, graph traversal
- Complex query syntax

### omni-knowledge (Rust Crate) — Enhancement Layer

| Capability                                                 | Module                                      | Status |
| ---------------------------------------------------------- | ------------------------------------------- | ------ |
| Extract typed entity refs from `[[Entity#type]]`           | `zk.rs`                                     | Done   |
| Parse YAML frontmatter                                     | `enhancer.rs`                               | Done   |
| Infer relations (DOCUMENTED_IN, CONTAINS, RELATED_TO)      | `enhancer.rs`                               | Done   |
| Batch enhance notes (Rayon-parallelized)                   | `enhancer.rs`                               | Done   |
| Entity/Relation graph with multi-hop search                | `graph/query.rs`                            | Done   |
| Multi-signal entity search (fuzzy + alias + token overlap) | `graph/query.rs`                            | Done   |
| Bidirectional multi-hop traversal (outgoing + incoming)    | `graph/query.rs`                            | Done   |
| Query-time tool relevance scoring                          | `graph/query.rs`                            | Done   |
| Entity deduplication and normalization                     | `graph/dedup.rs`                            | Done   |
| Graph persistence (JSON save/load)                         | `graph/persistence.rs`                      | Done   |
| Batch skill entity registration (Bridge 4)                 | `graph/skill_registry.rs`                   | Done   |
| Lightweight query intent extractor (action/target/context) | `graph/intent.rs`                           | Done   |
| PyO3 bindings for all above                                | `graph_py.rs`, `enhancer_py.rs`, `zk_py.rs` | Done   |

### omni-vector (Rust Crate) — Structured Search

| Capability                                                  | Module              | Status |
| ----------------------------------------------------------- | ------------------- | ------ |
| LanceDB vector store creation/management                    | `store.rs`          | Done   |
| Tantivy BM25 keyword index                                  | `keyword.rs`        | Done   |
| Weighted RRF fusion (dynamic weights via ToolSearchOptions) | `skill/ops_impl.rs` | Done   |
| Schema-aware field boosting                                 | `search.rs`         | Done   |
| Agentic search with intent + dynamic weights                | `ops/agentic.rs`    | Done   |

### Python Layer — Thin Orchestration

| Responsibility                                             | Module                                     |
| ---------------------------------------------------------- | ------------------------------------------ |
| ZK CLI async subprocess calls                              | `zk_client.py`                             |
| DualCoreSearch fusion logic (intent-aware merge)           | `zk_search.py`                             |
| Rust enhancer delegation                                   | `zk_enhancer.py`                           |
| LanceDB vector search bridge (dynamic weights passthrough) | `rust_vector.py`                           |
| **Dual-core bridges (modularized package)**                | **`dual_core/`**                           |
| Bridge 1a: ZK link proximity boost (fusion-scaled)         | `dual_core/zk_proximity.py`                |
| Bridge 1b: KG entity recall boost (fusion-scaled)          | `dual_core/kg_recall.py`                   |
| Bridge 2: LanceDB → ZK vector bridge                       | `dual_core/vector_bridge.py`               |
| Bridge 3+4: Graph enrichment + entity registry             | `dual_core/graph_enrichment.py`            |
| Bridge 5: KG query-time rerank (fusion-scaled)             | `dual_core/kg_rerank.py`                   |
| Dynamic fusion weights (intent → weights)                  | `dual_core/fusion_weights.py`              |
| Bridge constants and graph path resolution                 | `dual_core/_config.py`                     |
| **Unified intent pipeline: recall**                        | `recall.py::_apply_dual_core_recall_boost` |
| **Unified intent pipeline: router**                        | `hybrid_search.py::HybridSearch.search`    |
| **Unified intent pipeline: ZK hybrid**                     | `zk_search.py::ZkHybridSearcher.search`    |
| Sync hook (Bridge 4 caller)                                | `indexer.py`, `reindex.py`                 |

## Data Flow

### Sync Time (Index Building)

```
omni sync / omni reindex
  │
  ├── Scanner → SKILL.md frontmatter
  │     ├── LanceDB index_skill_tools() → skills.lance (Core 2)
  │     ├── build_relationship_graph() → skill_graph.json (keyword overlap edges)
  │     └── register_skill_entities() → knowledge.lance + JSON (Bridge 4, Rust-native)
  │           Creates: SKILL, TOOL, CONCEPT entities + CONTAINS, RELATED_TO relations
  │
  └── ZK CLI → auto-detects links between all 266+ markdown files
```

### Query Time (Unified Intent Signal)

All query-time pipelines share a **single intent analysis** via `compute_fusion_weights()`.
This ensures consistent behavior: one Rust extraction drives all bridges.

```
Query → Rust extract_query_intent() → FusionWeights (computed once per pipeline)
  │
  ├── Tool Routing (HybridSearch.search)
  │     ├── Rust agentic_search(semantic_weight, keyword_weight) ← from FusionWeights
  │     ├── Associative rerank → skill_graph.json
  │     ├── Bridge 3: enrich_skill_graph_from_zk()
  │     └── Bridge 5: apply_kg_rerank(fusion_scale=kg_rerank_scale)
  │
  ├── Knowledge Recall (recall skill command)
  │     ├── Core 2: LanceDB vector + keyword → top-k chunks
  │     ├── Bridge 1a: zk_link_proximity_boost(fusion_scale=zk_proximity_scale)
  │     └── Bridge 1b: apply_kg_recall_boost(fusion_scale=zk_entity_scale)
  │
  └── ZK Hybrid Search (zk_hybrid_search skill command)
        ├── Core 1: ZK FTS + link traversal → reasoning-based results
        ├── Bridge 2: LanceDB vector fallback
        ├── Merge: ZK precision boost = 1.0 + 0.5 * zk_proximity_scale
        └── Graph boost: base_boost * zk_entity_scale
```

## Graph Persistence

### Arrow-Native Storage (Primary)

The KnowledgeGraph is stored as **Lance tables** inside `knowledge.lance`, unified with knowledge chunks in the same Arrow ecosystem:

```
.cache/omni-vector/
├── skills.lance/         # Core 2: skill/tool index
├── knowledge.lance/      # Core 2: knowledge chunks + KG
│   ├── [knowledge chunks] # Existing vector+keyword index
│   ├── kg_entities/      # Entity Arrow table (ANN-ready)
│   │   ├── id, name, entity_type, description (Utf8)
│   │   ├── aliases (JSON Utf8), confidence (Float32)
│   │   ├── vector (FixedSizeList<Float32>) ← ANN search
│   │   └── metadata, created_at, updated_at (Utf8)
│   └── kg_relations/     # Relation Arrow table
│       ├── id, source, target, relation_type (Utf8)
│       ├── description, source_doc (Utf8)
│       └── confidence (Float32), metadata (Utf8)
├── memory.hippocampus.lance/
└── knowledge-graph.json  # Legacy JSON (dual-write during migration)
```

**Benefits over JSON**:

- **Columnar filtering**: Fast entity_type / confidence threshold queries
- **Vector ANN search**: Entity embeddings enable semantic entity lookup
- **Incremental writes**: Lance merge_insert (no full-file rewrite)
- **Unified ecosystem**: Same storage layer as skills, knowledge chunks, checkpoints

### Persistence API

| API                     | Rust                               | Python (via PyO3)                       |
| ----------------------- | ---------------------------------- | --------------------------------------- |
| Save to Lance           | `kg.save_to_lance(dir, dim).await` | `kg.save_to_lance(dir, dimension=1024)` |
| Load from Lance         | `kg.load_from_lance(dir).await`    | `kg.load_from_lance(dir)`               |
| Save to JSON (legacy)   | `kg.save_to_file(path)`            | `kg.save_to_file(path)`                 |
| Load from JSON (legacy) | `kg.load_from_file(path)`          | `kg.load_from_file(path)`               |

### Bridge Load/Save Resolution

All bridge modules (`kg_recall`, `kg_rerank`, `graph_enrichment`) use `_load_kg` / `_save_kg` from `dual_core/_config.py`:

1. **Default runtime** (no explicit paths): Try Lance → JSON fallback; dual-write to both
2. **Explicit `lance_dir`**: Lance only
3. **Explicit `graph_path`**: JSON only (test-friendly, no side-effects on project cache)

This ensures tests with `tmp_path` are isolated from the project's real Lance DB.

### Population

- **Sync-time seeding**: Every `omni sync` registers all skills/tools/keywords as entities (Bridge 4, dual-write)
- **Search-time enrichment**: Each query can discover new entity connections
- **Cross-session memory**: The graph persists across restarts, accumulating knowledge

## Test Coverage

| Bridge                    | Test File                                               | Tests                                          |
| ------------------------- | ------------------------------------------------------- | ---------------------------------------------- |
| Bridge 1a (ZK → Recall)   | `test_dual_core.py::TestZkLinkProximityBoost`           | 5                                              |
| Bridge 2 (LanceDB → ZK)   | `test_dual_core.py::TestBuildVectorSearchForZk`         | 4                                              |
| Bridge 3 (ZK → Router)    | `test_dual_core.py::TestEnrichSkillGraphFromZk`         | 5                                              |
| Bridge 4 (Sync → KG)      | `test_dual_core.py::TestRegisterSkillEntities`          | 5                                              |
| Dynamic Fusion Weights    | `test_dual_core.py::TestFusionWeights`                  | 6                                              |
| Skill wiring              | `test_dual_core.py::TestSkillCommandWiring`             | 3                                              |
| Router wiring             | `test_dual_core.py::TestRouterSkillRelationshipsWiring` | 2                                              |
| Rust: Graph CRUD + search | `test_graph.rs`                                         | 23 (incl. Lance roundtrip, skill registration) |
| Rust: Intent extractor    | `test_intent.rs`                                        | 14 (action/target/context decomposition)       |
| **Total**                 |                                                         | **67**                                         |
