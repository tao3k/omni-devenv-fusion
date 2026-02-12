# Vector/Router Common Schema Contract

> Single contract for tool search, vector search, and hybrid search. No legacy fields; CI and CLI enforce the contract.

See also: [Schema Singularity](schema-singularity.md) §6, [Vector Search Options Contract](vector-search-options-contract.md).

---

## 1. Field definitions

### Tool search (`omni.vector.tool_search.v1`)

| Field                                                   | Type                        | Required | Description                                                    |
| ------------------------------------------------------- | --------------------------- | -------- | -------------------------------------------------------------- |
| `schema`                                                | string                      | yes      | Must be `omni.vector.tool_search.v1`                           |
| `name`                                                  | string                      | yes      | Tool display name (e.g. `git.commit`)                          |
| `tool_name`                                             | string                      | yes      | Full tool name (e.g. `git.commit`)                             |
| `routing_keywords`                                      | string[]                    | no       | **Canonical** keywords for routing/hybrid search; default `[]` |
| `description`                                           | string                      | no       | Tool description                                               |
| `input_schema`                                          | object/string               | no       | JSON Schema for tool input                                     |
| `score`, `vector_score`, `keyword_score`, `final_score` | number                      | no       | Scores from fusion/rerank                                      |
| `confidence`                                            | `high` \| `medium` \| `low` | no       | Confidence label                                               |
| `skill_name`, `file_path`, `intents`, `category`        | string / string[]           | no       | Metadata                                                       |

**Forbidden:** `keywords` (legacy). Use `routing_keywords` only.

### Vector search result (`omni.vector.search.v1`)

| Field      | Type   | Required | Description                     |
| ---------- | ------ | -------- | ------------------------------- |
| `schema`   | string | yes      | Must be `omni.vector.search.v1` |
| `id`       | string | yes      | Document/row id                 |
| `content`  | string | yes      | Document body text              |
| `metadata` | object | yes      | Arbitrary metadata              |
| `distance` | number | yes      | Distance/similarity             |
| `score`    | number | no       | Normalized score if present     |

**Forbidden:** `keywords`. This payload is for document search, not tool routing.

### Hybrid search result (`omni.vector.hybrid.v1`)

| Field                           | Type   | Required | Description                     |
| ------------------------------- | ------ | -------- | ------------------------------- |
| `schema`                        | string | yes      | Must be `omni.vector.hybrid.v1` |
| `id`                            | string | yes      | Document/row id                 |
| `content`                       | string | yes      | Document body text              |
| `metadata`                      | object | yes      | May include `debug_scores`      |
| `source`                        | string | yes      | e.g. `hybrid`                   |
| `score`                         | number | yes      | Fusion score                    |
| `vector_score`, `keyword_score` | number | no       | Component scores                |

**Forbidden:** `keywords`.

### Route test payload (`omni.router.route_test.v1`)

| Field                         | Type   | Description                                                                |
| ----------------------------- | ------ | -------------------------------------------------------------------------- |
| `schema`                      | string | `omni.router.route_test.v1`                                                |
| `query`                       | string | User intent query                                                          |
| `results`                     | array  | List of router result objects (each has `routing_keywords`, no `keywords`) |
| `stats`                       | object | `semantic_weight`, `keyword_weight`, `rrf_k`, `strategy`                   |
| `count`, `threshold`, `limit` | number | Result counts and thresholds                                               |
| `confidence_profile`          | object | `name`, `source`                                                           |

Each item in `results` must use `routing_keywords`; `keywords` is forbidden.

---

## 2. Version upgrade rules

- **Current version:** All contracts are **v1** (`*.v1` in schema ID).
- **Adding fields:** New optional fields may be added; consumers must ignore unknown fields. JSON schemas use `additionalProperties: false`, so new fields require a new schema version (e.g. v2).
- **Breaking changes:** A new schema version (e.g. `omni.vector.tool_search.v2`) must be introduced. Old and new versions may coexist during migration; parsers validate the `schema` field and reject unsupported versions.
- **Deprecation:** Do not add deprecated fields to the same schema. Introduce a new version and document the migration path.

---

## 3. No-backward-compatibility policy for legacy fields

- **`keywords` is not supported.** There is no compatibility layer that accepts or maps `keywords` to `routing_keywords`. All parsers (`parse_tool_search_payload`, `parse_vector_payload`, `parse_hybrid_payload`) reject payloads that contain the `keywords` field.
- **Stored data:** LanceDB metadata must use `routing_keywords` only. After reindex, the writer writes only `routing_keywords`. Use `omni db validate-schema` to audit; use `omni reindex --clear` to fix legacy data.
- **CI:** Snapshot and schema tests fail if payloads or snapshots contain `keywords` or if schema and snapshot drift.

---

## 4. Validation and tooling

| Command / API                             | Purpose                                                                                                        |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `omni db validate-schema`                 | Audit skills/router tables for legacy `keywords`; exit non-zero if any found                                   |
| `omni reindex`                            | Post-reindex runs contract check; result includes `schema_validation` and optional `schema_validation_warning` |
| `validate_vector_table_contract(entries)` | Python: given list of row-like dicts, returns `total`, `legacy_keywords_count`, `sample_ids`                   |

---

## Related documentation

- [Schema Singularity](schema-singularity.md)
- [Vector Search Options Contract](vector-search-options-contract.md)
- [MCP Tool Schema](mcp-tool-schema.md)
