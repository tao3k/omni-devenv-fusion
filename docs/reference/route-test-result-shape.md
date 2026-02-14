# Route Test Result Shape (Algorithm Contract)

> Canonical shape of `omni route test --json` is defined by the **routing algorithm**: Rust `ToolSearchResult` → tool_search.v1 → Python adds `id`, `command`, `payload`, calibration. All data and snapshots on the vector side must conform before Python is wired.

See also: [Vector/Router Schema Contract](vector-router-schema-contract.md), [Skills and Router Databases](skills-and-router-databases.md), [Routing Search Schema](routing-search-schema.md).

---

## 1. Data flow

```
Rust: ToolSearchResult (omni-vector)
  name, description, input_schema, score, vector_score?, keyword_score?,
  skill_name, tool_name, file_path, keywords, intents, category
        │
        ▼ (Python bindings: keywords → routing_keywords, + final_score, confidence)
tool_search.v1 dict
        │
        ▼ (Python: id = tool_name, command = suffix, payload = nested metadata)
route_result_item (each element of results[])
```

- **Rust** never emits `id`, `command`, or `payload`; those are added by the Python layer.
- **Rust** uses `keywords` internally; the **contract** exposes only `routing_keywords` (no `keywords` in JSON).

---

## 2. Route result item (canonical fields)

| Field              | Source | Required | Description                                            |
| ------------------ | ------ | -------- | ------------------------------------------------------ |
| `id`               | Python | yes      | Stable tool id (e.g. full `tool_name`)                 |
| `name`             | Rust   | no\*     | Display name (tool_search.v1); Rust always provides it |
| `description`      | Rust   | yes      | Tool description                                       |
| `skill_name`       | Rust   | yes      | Skill name                                             |
| `tool_name`        | Rust   | yes      | Full tool name (e.g. `git.commit`)                     |
| `command`          | Python | yes      | Command suffix (e.g. `commit`)                         |
| `file_path`        | Rust   | no       | Source path                                            |
| `score`            | Rust   | yes      | Raw RRF/fusion score                                   |
| `vector_score`     | Rust   | no       | Vector component score                                 |
| `keyword_score`    | Rust   | no       | Keyword component score                                |
| `final_score`      | Python | yes      | Calibrated score                                       |
| `confidence`       | Python | yes      | `high` \| `medium` \| `low`                            |
| `routing_keywords` | Rust   | yes      | Keywords (no `keywords`)                               |
| `intents`          | Rust   | no       | Intent labels                                          |
| `category`         | Rust   | no       | Tool category                                          |
| `input_schema`     | Rust   | yes      | JSON Schema for inputs                                 |
| `explain`          | CLI    | no       | Present when `--explain` (score breakdown)             |
| `payload`          | Python | yes      | Nested `type` + `metadata`                             |

\*`name` is optional in the JSON schema for backward compatibility; the algorithm (Rust) always provides it. Python should pass it through so route test output is complete.

---

## 3. Canonical snapshot

The single source of truth for the full algorithm output shape is:

- **`packages/shared/schemas/snapshots/route_test_canonical_v1.json`**

It contains one full route test payload with one result item that includes all optional fields (`name`, `vector_score`, `keyword_score`, `intents`, `category`). Any producer (Rust bindings + Python) must be able to emit payloads that validate against `omni.router.route_test.v1.schema.json`; the canonical snapshot is the reference “full” example.

---

## 4. Lock order

1. **Rust/vector**: `ToolSearchResult` and bindings output (tool_search.v1 shape with `routing_keywords`) are fixed.
2. **Shared**: `omni.router.route_test.v1.schema.json` and `route_test_canonical_v1.json` are the contract and reference snapshot.
3. **Python**: `to_router_result()`, `build_tool_router_result()`, and CLI output are updated to conform (include `name`, `intents`, `category` when present; ensure `id`, `command`, `payload` match schema).
