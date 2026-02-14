# Routing Search: Value Flow and Algorithm Alignment

> How each **value** flows from **data source** → **storage** → **algorithm** (semantic / keyword / intent). Standardization rules and scenario validation ensure precision and a single contract.

See also: [Routing Search Schema](routing-search-schema.md), [Skill Routing Value Standard](skill-routing-value-standard.md) (canonical: `packages/shared/schemas/skill-routing-value-standard.md` — quality of routing_keywords, intents, description), [omni.router.routing_search.v1](packages/shared/schemas/omni.router.routing_search.v1.schema.json), [Canonical v1](packages/shared/schemas/snapshots/routing_search_canonical_v1.json).

---

## 1. Value flow overview

| Value                | Data source                       | Storage                                       | Semantic              | Keyword (Tantivy)                  | Intent (strategy + rerank)       |
| -------------------- | --------------------------------- | --------------------------------------------- | --------------------- | ---------------------------------- | -------------------------------- |
| **tool_name**        | Scanner / indexer (skill.command) | Lance metadata, Tantivy field                 | In embedding template | Field `tool_name`, boost **5.0**   | —                                |
| **description**      | Scanner / indexer                 | Lance `content` (and metadata), Tantivy field | In embedding template | Field `description`, boost **1.0** | Rerank: metadata_alignment_boost |
| **intents**          | SKILL.md / decorator / indexer    | Lance metadata, Tantivy field (joined)        | In embedding template | Field `intents`, boost **4.0**     | Rerank + file_discovery_boost    |
| **routing_keywords** | SKILL.md / decorator / indexer    | Lance metadata, Tantivy field `keywords`      | —                     | Field `keywords`, boost **3.0**    | Rerank + file_discovery_boost    |
| **category**         | Decorator / infer / indexer       | Lance metadata, Tantivy (stored)              | —                     | Stored, **not** in query parser    | category_filter + rerank         |

---

## 2. Data sources

- **Rust path** (e.g. `index_skill_tools_dual`): SKILL.md → `routing_keywords`, `intents`; script decorator → `category` (or `infer_category_from_skill`). Tool records built by omni-scanner.
- **Python path** (e.g. `SkillIndexer.index_skills`): Skill manifest (commands, description, routing_keywords, intents, category). Used when router is initialized from kernel/skill context.

Both paths must produce **the same shape** of metadata (tool_name, description, routing_keywords, intents, category) so that Tantivy and Lance see a single contract.

---

## 3. Source value standardization

To keep matching precise and behaviour consistent:

1. **routing_keywords** and **intents**
   - **Trim** each entry; **drop empty**; **dedupe** (first occurrence wins).
   - Implemented: Rust `extract_string_array_field` (skill/mod.rs); Python indexer `_normalize_string_list`.

2. **category**
   - Non-empty string; if missing, fallback to skill name (Rust) or `skill_name` (Python).
   - Used for intent filter and rerank; no need to lowercase at write (comparison in fusion uses `.to_lowercase()`).

3. **description**
   - Single string; no structural normalization required. Empty is allowed (Tantivy/embedding still get a value).

4. **tool_name**
   - Canonical form `skill_name.command_name` (e.g. `git.commit`). Indexer strips skill prefix from command name then rebuilds full id.

Implementations that **write** to the index (Python indexer, Rust writer) must apply the same rules so that **read** side (Tantivy query, fusion rerank) sees normalized values.

---

## 4. Algorithm alignment (per algorithm)

### 4.1 Semantic (vector) search

- **Input:** Query string → embedded to vector.
- **Stored value:** One blob per tool from canonical template: `COMMAND: {tool_name}\nDESCRIPTION: {description}\nINTENTS: {intents}`.
- **Implementation:** Python indexer builds `doc_content`; Rust stores it in Lance `content` and embeds it (or Python embeds and sends vectors).
- **Canonical:** `routing_search_canonical_v1.json` → `semantic.embedding_source.template` and `fields`.

### 4.2 Keyword (Tantivy) search

- **Input:** Query string run through BM25 query parser over indexed fields.
- **Stored values:** tool_name, description, category, keywords (routing_keywords joined), intents (joined with `|`).
- **Boosts:** Must match canonical: tool_name **5.0**, intents **4.0**, keywords **3.0**, description **1.0**; category stored but **not** in query parser.
- **Implementation:** Rust `keyword/index.rs` — `QueryParser::for_index` with the four fields and `set_field_boost`.
- **Canonical:** `routing_search_canonical_v1.json` → `keyword.fields` (name, boost, in_query_parser).

### 4.3 Intent (strategy + rerank)

- **Strategy:** exact → keyword_only; semantic → vector_only; hybrid → vector + keyword + RRF.
- **category_filter:** Applied when intent signals e.g. file_discovery; filters on `category = 'file_discovery'`.
- **Rerank:** After RRF, `metadata_alignment_boost` and (for file_discovery) `file_discovery_boost` use: routing_keywords, intents, description, category (all lowercased at match time).
- **Implementation:** Rust `agentic.rs` (strategy, category_filter); Rust `keyword/fusion.rs` (rerank).
- **Canonical:** `routing_search_canonical_v1.json` → `intent.strategies`, `category_filter_values`, `rerank_fields`.

---

## 5. Scenario validation

- **Canonical schema tests:** `packages/python/core/tests/units/test_router/test_routing_search_schema.py` — loads `routing_search_canonical_v1.json` and asserts keyword boosts (5, 4, 3, 1), category not in query parser, intent strategies, rerank fields, and semantic template placeholders. Keeps implementation and schema in sync.
- **Complex scenario test:** `TestRoutingSearchSchemaComplexScenario` in `test_route_hybrid_integration.py` runs multiple queries (exact, file-discovery, research/URL, hybrid) and asserts expected tool families in top N. Skips when the index has only placeholder vectors; run `omni sync` for full coverage.
- **Standardization:** Indexer and Rust writer both normalize keywords/intents (trim, drop empty, dedupe); any new writer must follow the same rules.

When adding or tuning a value (e.g. new field, new boost), update the canonical instance and the implementation; run scenario tests to confirm routing quality.
