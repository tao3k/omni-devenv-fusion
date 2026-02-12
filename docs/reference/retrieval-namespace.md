# Retrieval Namespace

This project uses a precise retrieval namespace:

- `omni.rag.retrieval.interface`
- `omni.rag.retrieval.lancedb`
- `omni.rag.retrieval.hybrid`
- `omni.rag.retrieval.factory`
- `omni.rag.retrieval.node_factory`

## Core API

### Types and Contracts

- `RetrievalResult`
- `RetrievalConfig`
- `RetrievalBackend`

`RetrievalConfig` is the Python-side orchestration contract aligned with Rust scanner options:

- Core: `collection`, `top_k`, `score_threshold`
- Scanner options: `where_filter`, `batch_size`, `fragment_readahead`, `batch_readahead`, `scan_limit`
- Hybrid keywords: `keywords`

`LanceRetrievalBackend.search(...)` forwards scanner options to `VectorStoreClient.search(...)`.
`LanceRetrievalBackend.search_hybrid(...)` forwards `keywords` to `VectorStoreClient.search_hybrid(...)`.

### Backends

- `LanceRetrievalBackend`
- `HybridRetrievalBackend` (Rust-native hybrid only; no Python-side fusion fallback)

## Engine Boundary

- Retrieval engines (vector/BM25/hybrid fusion) are implemented in Rust.
- Python namespace is orchestration-only:
  - config and typed contracts
  - backend selection and routing
- Python post-processing is limited to deterministic normalization:
  - threshold filtering
  - dedupe (prefer `id`, fallback `content`)
  - stable score-desc ranking
- `VectorStoreClient.search_hybrid(...)` delegates to Rust binding `search_hybrid`
  (not `search_tools`), aligning RAG retrieval with engine-layer ownership.
- Canonical hybrid payload contract (`omni.vector.hybrid.v1`):
  - required: `schema`, `id`, `content`, `metadata`, `source`, `score`
  - optional debug: `vector_score`, `keyword_score`
- Canonical vector payload contract (`omni.vector.search.v1`):
  - required: `schema`, `id`, `content`, `metadata`, `distance`
  - optional: `score` (Rust-emitted normalized similarity used by Python facades)
- Canonical tool-search payload contract (`omni.vector.tool_search.v1`):
  - required: `schema`, `name`, `description`, `score`, `tool_name`, `confidence`, `final_score`
- Python parses both contracts through `omni.foundation.services.vector_schema`:
  - `parse_vector_payload(...)`
  - `parse_hybrid_payload(...)`
  - `parse_tool_search_payload(...)`
- Confidence/final score semantics are Rust-owned and emitted by bindings.
  Python router consumes these fields and does not implement score calibration logic.

### Knowledge Retrieval API (Python Orchestration Layer)

`omni.core.knowledge.librarian.KnowledgeStorage` exposes explicit retrieval methods:

- `vector_search(vector, limit)`:
  - delegates to Rust binding `search_optimized`
  - semantic-only retrieval
- `text_search(query_text, query_vector, limit)`:
  - delegates to Rust binding `search_hybrid`
  - text + vector hybrid retrieval
- `search(vector, limit)`:
  - compatibility alias to `vector_search`

`omni.core.knowledge.librarian.Librarian.query(query, limit)` uses `text_search(...)`
so text queries benefit from hybrid retrieval by default.

### Factory

- `create_retrieval_backend(kind, ...)`
  - Supported `kind`: `lance`, `hybrid`
  - Legacy aliases are intentionally rejected (`lancedb`, `vector`)

### LangGraph Node Factory

- `create_retriever_node(...)`
- `create_hybrid_node(...)`

## Tracer/Pipeline Integration

`RetrievalToolInvoker` supports:

- `retriever.search`
- `retriever.hybrid_search`
- `retriever.index`
- `retriever.get_stats`

Example retrieval chain:

```yaml
pipeline:
  - retriever.hybrid_search:
      input:
        query: "$query"
      output:
        - results
```

Runtime YAML can set the default retrieval backend:

```yaml
runtime:
  retrieval:
    default_backend: lance # lance | hybrid
```

`default_backend` and payload-level `backend` use the same strict set: `lance` or `hybrid`.

At runtime, explicit payload selection still has higher priority:

```json
{ "backend": "hybrid" }
```

## Testing

Primary tests:

- `packages/python/foundation/tests/unit/rag/test_retrieval_namespace.py`
- `packages/python/foundation/tests/unit/rag/test_retrieval_factory.py`
- `packages/python/foundation/tests/unit/rag/test_retrieval_node_factory.py`
- `packages/python/foundation/tests/unit/tracer/test_retrieval_invoker.py`
