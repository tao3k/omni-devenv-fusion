# Vector Search Options Contract

_This file is auto-generated from `SearchOptionsContract` in `vector_schema.py`._

This document defines the external contract for scanner tuning options passed from Python to Rust via `search_optimized(...)`.

## Scope

- Python entrypoint: `VectorStoreClient.search(...)`
- Rust binding: `PyVectorStore.search_optimized(table_name, query, limit, options_json)`
- Rust runtime: `omni-vector::SearchOptions`

## JSON Schema

```json
{
  "additionalProperties": false,
  "description": "Contract for scanner tuning options passed to Rust search_optimized.",
  "properties": {
    "where_filter": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "SQL-like Lance filter or serialized JSON metadata filter expression.",
      "title": "Where Filter"
    },
    "batch_size": {
      "anyOf": [
        {
          "maximum": 65536,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Scanner batch size. Effective Rust default is 1024 when omitted.",
      "title": "Batch Size"
    },
    "fragment_readahead": {
      "anyOf": [
        {
          "maximum": 256,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Fragments prefetched per scan. Effective Rust default is 4 when omitted.",
      "title": "Fragment Readahead"
    },
    "batch_readahead": {
      "anyOf": [
        {
          "maximum": 1024,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Batches prefetched per scan. Effective Rust default is 16 when omitted.",
      "title": "Batch Readahead"
    },
    "scan_limit": {
      "anyOf": [
        {
          "maximum": 1000000,
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Hard cap on scanned candidates before post-processing.",
      "title": "Scan Limit"
    }
  },
  "title": "SearchOptionsContract",
  "type": "object"
}
```

## Request-Level Constraints

- `n_results` range: `1..=1000`
- `collection` must be non-empty

If validation fails, Python returns an empty result list and does not call Rust.

## Recommended Profiles

- `small` (local/dev, <=100k rows): `batch_size=256`, `fragment_readahead=2`, `batch_readahead=4`
- `medium` (balanced): `batch_size=1024`, `fragment_readahead=4`, `batch_readahead=16`
- `large` (throughput oriented): `batch_size=2048`, `fragment_readahead=8`, `batch_readahead=32`, optionally set `scan_limit`

When scanner options are omitted in Python, `run_semantic_search(...)` applies these profiles
adaptively by `n_results`:

- `n_results <= 20` → `small`
- `20 < n_results <= 200` → `medium`
- `n_results > 200` → `large`

Start from `medium`, then benchmark against your dataset/query mix before raising readahead.

## Effective Defaults

Python always sends effective values for:

- `batch_size`
- `fragment_readahead`
- `batch_readahead`

`scan_limit` remains optional and is omitted unless explicitly set.

Rust `SearchOptions::default()` still defines baseline values used when callers bypass this Python layer:

- `batch_size = 1024`
- `fragment_readahead = 4`
- `batch_readahead = 16`
- `scan_limit = None` (uses ANN fetch count)

## Embedding Cache Behavior

- In-process cache: LRU by query (fast path within one process).
- Cross-process warm cache: the last query embedding is persisted at
  `$PRJ_CACHE_HOME/omni-vector/query-embed-last.json` (keyed by embedding signature + query hash).
- Signature mismatch (provider/model/dimension/url changes) automatically invalidates persisted reuse.

## Canonical Example

```json
{
  "where_filter": "{\"name\":\"tool.echo\"}",
  "batch_size": 512,
  "fragment_readahead": 2,
  "batch_readahead": 8,
  "scan_limit": 64
}
```

## Error Codes (Service Layer)

- `VECTOR_REQUEST_VALIDATION`: invalid request inputs (`n_results`, `collection`, option ranges)
- `VECTOR_BINDING_API_MISSING`: Rust binding missing required method (`search_optimized`)
- `VECTOR_PAYLOAD_VALIDATION`: Rust payload/schema mismatch in vector search response
- `VECTOR_TABLE_NOT_FOUND`: requested collection/table does not exist
- `VECTOR_RUNTIME_ERROR`: unexpected runtime failure in vector search
- `VECTOR_HYBRID_PAYLOAD_VALIDATION`: payload/schema mismatch in hybrid search response
- `VECTOR_HYBRID_TABLE_NOT_FOUND`: requested collection/table does not exist for hybrid search
- `VECTOR_HYBRID_RUNTIME_ERROR`: unexpected runtime failure in hybrid search

## CI Performance Thresholds by OS

The perf guard test (`test_search_perf_guard`) reads thresholds from environment variables:

- `OMNI_VECTOR_PERF_P95_MS`
- `OMNI_VECTOR_PERF_RATIO_MAX`

Current CI matrix values:

- `ubuntu-latest`: `OMNI_VECTOR_PERF_P95_MS=700`, `OMNI_VECTOR_PERF_RATIO_MAX=4.0`
- `macos-latest`: `OMNI_VECTOR_PERF_P95_MS=900`, `OMNI_VECTOR_PERF_RATIO_MAX=4.5`

Only performance guardrails differ by OS. API/schema/default behavior remains cross-platform identical.
