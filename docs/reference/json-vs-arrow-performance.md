# JSON vs Arrow Performance (Vector Search)

> How to measure and interpret the performance difference between the JSON and Arrow IPC paths for vector search.

See also: [Vector Store API](vector-store-api.md), [Search Result Batch Contract](search-result-batch-contract.md), [Python Arrow Integration Plan](python-arrow-integration-plan.md).

---

## 1. Two paths

| Path      | Flow                                                                                                                                 | Use case                                                                           |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **JSON**  | Rust `search_optimized` → list of JSON strings → Python `parse_vector_payload(raw)` per row                                          | Fallback when IPC unavailable or on error.                                         |
| **Arrow** | Rust `search_optimized_ipc` → IPC stream bytes → `pyarrow.ipc.open_stream(...).read_all()` → `VectorPayload.from_arrow_table(table)` | Default in `VectorStoreClient.search()` when the store has `search_optimized_ipc`. |

The Arrow path avoids per-row JSON encode (Rust) and decode (Python), and builds payloads from columnar data in one pass.

---

## 2. Running the benchmark

From the repo root:

```bash
# Default: 50 iterations, limit=20, repo=.
uv run python scripts/benchmark_json_vs_arrow.py

# Custom iterations and limit
uv run python scripts/benchmark_json_vs_arrow.py --iters 100 --limit 50

# Use a specific repo path for indexing (default is current repo)
uv run python scripts/benchmark_json_vs_arrow.py --repo /path/to/repo --iters 30
```

**Requirements:** `omni_core_rs` must be available; repo must have `assets/skills` so that `index_skill_tools` creates a non-empty table. If not, the script exits with a skip message.

**Output example:**

```
Vector search (limit=20, iters=50)
  JSON path:  2.35 ms ± 0.12
  Arrow path: 1.41 ms ± 0.08
  Ratio (JSON/Arrow): 1.67x
```

---

## 3. Interpreting results

- **Ratio > 1**: Arrow path is faster (typical; we expect roughly 30–50% latency reduction on the Python side from skipping JSON parse).
- **Ratio < 1**: Possible on very small result sets or cold runs; re-run with higher `--iters` or `--limit`.
- Results depend on hardware, table size, and limit; use for relative comparison (JSON vs Arrow on the same machine), not absolute SLA.

---

## 4. Where the gain comes from

1. **Rust:** Single RecordBatch write to IPC stream instead of N JSON strings.
2. **Python:** One IPC read + columnar access instead of N `json.loads` + dict construction.
3. **Memory:** Fewer intermediate allocations (no list of JSON strings).

---

## 5. Future optimization directions

### 5.1 Batch search (large limit)

When returning **100+ results** in one call, the Arrow advantage becomes more obvious:

- **JSON:** N serializations (Rust) + N parses (Python); memory scales with string length and number of rows.
- **Arrow:** One RecordBatch; IPC size grows linearly with rows but without per-row object overhead. Python builds payloads from columns in a single pass.

**Recommendation:** For batch search (e.g. `limit=100` or higher), prefer the IPC path and consider benchmarking with `--limit 100` to see a larger JSON/Arrow ratio.

### 5.2 Column projection (read only needed columns)

**Implemented.** Callers can request only the columns they need:

- **Rust:** `SearchOptions.ipc_projection` (optional list of column names). `search_results_to_ipc` builds a RecordBatch with only those columns. Allowed: `id`, `content`, `tool_name`, `file_path`, `routing_keywords`, `intents`, `_distance`, `metadata`.
- **Python:** `RustVectorStore.search_optimized_ipc(..., projection=["id", "content", "_distance", "metadata"])`. When `n_results >= 50`, `VectorStoreClient.search()` automatically uses this projection for the IPC path to reduce payload size.

**Usage:** For batch search (e.g. limit 100+), pass `projection` so the IPC stream omits unused columns (e.g. `tool_name`, `file_path`, `routing_keywords`, `intents` when only id/content/distance/metadata are needed).

---

## 6. Related

| Topic                      | Document                                                          |
| -------------------------- | ----------------------------------------------------------------- |
| Using IPC in code          | [Vector Store API](vector-store-api.md)                           |
| Batch schema               | [Search Result Batch Contract](search-result-batch-contract.md)   |
| Roadmap                    | [Python Arrow Integration Plan](python-arrow-integration-plan.md) |
| Future: batch + projection | §5 above                                                          |
