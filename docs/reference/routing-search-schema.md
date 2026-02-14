# Routing Search Schema (Per-Value Algorithm)

> Explicit assignment: which **value** is used for **semantic (vector)**, **keyword**, and **intent** search. This contract is the reason the **router database** exists separately from the **skills database**.

See also: [Skills and Router Databases](skills-and-router-databases.md), [Vector/Router Schema Contract](vector-router-schema-contract.md), [Route Test Result Shape](route-test-result-shape.md).

---

## 1. Purpose

- **Skills DB** holds the full tool data (descriptions, embeddings, metadata). It is the single source of truth for **what** is indexed.
- **Router** uses a **routing search algorithm** that combines three search types. Each **value** (field/source) is assigned to one or more of:
  - **Semantic (vector) search** — embedding similarity.
  - **Keyword search** — BM25 over indexed text fields.
  - **Intent search** — strategy selection (exact / semantic / hybrid), category filter, and rerank alignment.

This document defines **which value drives which search type** so that router behaviour and router DB contents are implementable and auditable without ambiguity.

---

## 2. Per-value assignment

| Value / source                                                                                                     | Search type                       | Where used                                                                                                                                          | Notes                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------ | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Embedding text** (single blob per tool: `COMMAND: {skill}.{cmd}` + `DESCRIPTION: {desc}` + `INTENTS: {intents}`) | **Semantic (vector)**             | Lance table: column `content` is the text that was embedded; column `vector` is the embedding. Query is embedded and matched against these vectors. | One blob per tool; indexing in Python (`SkillIndexer`) builds this from command name, description, and intents.       |
| **tool_name**                                                                                                      | **Keyword**                       | Tantivy field `tool_name`; query parser boost **5.0**.                                                                                              | Literal / exact match; highest keyword weight.                                                                        |
| **intents** (list → joined string)                                                                                 | **Keyword**                       | Tantivy field `intents`; query parser boost **4.0**.                                                                                                | Also included in the embedding text.                                                                                  |
| **routing_keywords** (list → space-separated)                                                                      | **Keyword**                       | Tantivy field `keywords`; query parser boost **3.0**.                                                                                               | BM25 over keywords only; no legacy `keywords` field.                                                                  |
| **description**                                                                                                    | **Keyword**                       | Tantivy field `description`; query parser boost **1.0**.                                                                                            | Same text is the main part of the embedding blob.                                                                     |
| **category**                                                                                                       | **Keyword (stored)** / **Intent** | Tantivy: stored and available for filtering; **not** in the default BM25 query parser. Used for **intent**: category filter and rerank.             | Filtering: `category_filter` (e.g. `file_discovery`). Rerank: `metadata_alignment_boost`, `file_discovery_boost`.     |
| **Query → intent classification**                                                                                  | **Intent (strategy)**             | Python: `classify_tool_search_intent_full(query)` → `intent` (exact / semantic / hybrid) and optional `category_filter` (e.g. `file_discovery`).    | Decides which branch runs: **exact** = keyword-only, **semantic** = vector-only, **hybrid** = vector + keyword + RRF. |
| **routing_keywords, intents, description, category**                                                               | **Intent (rerank)**               | Rust: after RRF fusion, `metadata_alignment_boost` and (for file_discovery intent) `file_discovery_boost`.                                          | Rerank boosts scores using query terms vs. tool metadata; category and description participate.                       |

---

## 3. Keyword index (Tantivy) summary

- **Fields in schema:** `tool_name`, `description`, `category`, `keywords`, `intents`.
- **Fields used in the default BM25 query:** `tool_name`, `keywords`, `intents`, `description` (category is stored but not in the query parser).
- **Boosts:** tool_name 5.0, intents 4.0, keywords 3.0, description 1.0.

---

## 4. Semantic (vector) index summary

- **Source text for embedding (per tool):**  
  `COMMAND: {skill_name}.{command_name}\nDESCRIPTION: {description}\nINTENTS: {intents joined}`.
- **Stored in Lance:** `content` = that text; `vector` = embedding of that text; `metadata` = JSON with tool_name, skill_name, routing_keywords, intents, category, etc.
- **Semantic search:** query string is embedded; similarity is computed against the `vector` column. No direct use of description/keywords as separate columns in the vector branch.

---

## 5. Intent (strategy + rerank) summary

- **Strategy:** From query intent classification: **exact** → keyword-only; **semantic** → vector-only; **hybrid** → vector + keyword + weighted RRF.
- **Category filter:** Optional filter (e.g. `category = 'file_discovery'`) applied when intent signals a category (e.g. file discovery).
- **Rerank:** After fusion, tools are boosted by:
  - **metadata_alignment_boost:** query terms matched against description, routing_keywords, intents, category.
  - **file_discovery_boost:** applied when the query is file-discovery-like and the tool’s category (or description) indicates file_discovery.

---

## 6. Router DB vs skills DB (in terms of this schema)

| Aspect         | Skills DB                                                                                                   | Router DB                                                                                                 |
| -------------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Content**    | Full tool rows: vector, content, metadata (tool_name, description, routing_keywords, intents, category, …). | Only algorithm outputs: e.g. tool_id, vector_score, keyword_score, rrf_score, strategy, session/query id. |
| **Role**       | Source of truth for **values** in the table above (what gets semantic/keyword/intent).                      | Holds **scores and strategy** from the routing search algorithm; no tool content, no embeddings.          |
| **Population** | `omni sync` / reindex from `assets/skills/`.                                                                | Filled when routing runs (e.g. route test or MCP route); persistence is optional and non-fatal.           |

The **routing search schema** (this document) defines how **values** from the skills DB are used in the algorithm; the **router DB** stores only the **result** of that algorithm (scores and strategy), not the values themselves.

---

## 7. References

- **Indexing (Python):** `packages/python/core/src/omni/core/router/indexer.py` — builds `doc_content` and metadata for skills table and keyword index.
- **Keyword (Rust):** `packages/rust/crates/omni-vector/src/keyword/index.rs` — Tantivy schema and query parser boosts.
- **Fusion and rerank (Rust):** `packages/rust/crates/omni-vector/src/keyword/fusion.rs` — RRF and metadata_alignment_boost / file_discovery_boost.
- **Intent (Python):** `classify_tool_search_intent_full` — strategy and category_filter.
- **Agentic (Rust):** `packages/rust/crates/omni-vector/src/ops/agentic.rs` — category_filter and strategy application.
