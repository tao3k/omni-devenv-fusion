# Knowledge and ZK Search: Why "Project Progress" Was Missing and What We Improved

## What We Observed

When searching for "project progress" or "current project status":

- **knowledge.recall** (vector search on `knowledge_chunks`): **0 results** — collection was empty or had no docs content.
- **knowledge.search** (ripgrep over docs/references/skills): **0 results** — no line contained the exact phrase.
- **ZK** (zk_search / zk_hybrid_search): ZK has notes but project progress lives in `docs/` (milestones, plan); ZK content is separate, so ZK may not cover that vocabulary. Hybrid’s vector fallback also returned nothing because the vector store had no docs.

The actual project progress content exists in `docs/index.md`, `docs/milestones/*.md`, and `docs/plan/` but was not findable by the current pipelines.

---

## Root Causes

### 1. Vector store (`knowledge_chunks`) has no docs content

- **`omni sync knowledge`** only indexes paths listed in **`knowledge_dirs`** in references.yaml (system default: **`packages/conf/references.yaml`**; user override: `$PRJ_CONFIG_HOME/omni-dev-fusion/references.yaml`).
- Only **`assets/knowledge`** was active; **`docs/`** was commented out. So `docs/milestones`, `docs/plan`, `docs/reference` were never ingested.
- Result: `knowledge.recall` and the vector leg of `zk_hybrid_search` return nothing for doc-based queries.

### 2. Text search (ripgrep) is phrase-only

- **knowledge.search** runs ripgrep with the **entire user query as a single pattern** (case-insensitive).
- A query like "project progress current status" only matches lines that contain that **exact phrase**. No line in the repo does, so we got 0 matches.
- Users expect at least some hits when words like "progress", "milestone", "roadmap" appear in docs.

### 3. ZK and docs are separate content sets

- ZK notes (e.g. in `.zk` or `assets/knowledge`) and `docs/` are different trees. If "project progress" is only described in `docs/`, ZK-only or ZK-first search won’t find it unless we also search docs or ingest docs into the vector store (which ZK hybrid then uses as fallback).

---

## Improvements Made

### 0. Same DB for sync and recall (path alignment)

**Root cause:** `omni sync knowledge` writes to `get_database_path("knowledge")` = `.../omni-vector/knowledge.lance`. The foundation `VectorStoreClient` (used by `knowledge.recall`, `knowledge.stats`, and ZK hybrid vector fallback) used the **base** path `.../omni-vector`, so it was reading a different Lance DB and saw 0 documents.

**Change:** In `packages/python/foundation/src/omni/foundation/services/vector.py`, `VectorStoreClient` now has a dedicated store for the knowledge DB: when the collection is `"knowledge_chunks"`, all operations (search, add, count, delete, create_index, etc.) use a store opened on `get_database_path("knowledge")`. So sync and recall/stats/ingest/clear use the same DB. No reconnect or hot reload needed beyond loading the updated code.

### 1. Include `docs/` in knowledge sync (references.yaml)

- **Add** a `knowledge_dirs` entry for `docs/` (e.g. `path: "docs"`, `globs: ["**/*.md"]`) in **`packages/conf/references.yaml`** (or in your user override) so `omni sync knowledge` indexes documentation.
- After running **`omni sync knowledge`**, `knowledge_chunks` will contain chunks from `docs/milestones`, `docs/plan`, `docs/reference`, etc., so **knowledge.recall** and **zk_hybrid_search** vector fallback can return project progress–related content.

### 2. Multi-word / OR behavior for knowledge.search (search.py)

- For **multi-word queries**, build an **OR pattern** from words (e.g. "project progress" → `project|progress`) so ripgrep matches any line containing **any** of the words.
- Words are escaped for regex safety. Single-word queries keep current phrase behavior.
- This makes queries like "project progress", "roadmap milestone status" return useful matches even when the exact phrase does not appear.

### 3. When to use which tool (for agents and docs)

- **knowledge.recall**: Best when the vector store is populated (after sync including docs). Use for semantic queries like "project progress" or "current milestones".
- **knowledge.search**: Good for literal and multi-word keyword search over docs/references/skills; now improved for multi-word OR.
- **zk_hybrid_search**: Combines ZK reasoning with vector fallback; once docs are in the vector store, hybrid will also surface doc content for "project progress" type questions.
- For "project status / progress / roadmap" we can recommend: run **`omni sync knowledge`** (with docs in knowledge_dirs), then use **knowledge.recall** or **zk_hybrid_search**; for quick keyword scan use **knowledge.search** with scope `"docs"` or `"all"`.

---

## Summary

| Issue                                   | Cause                                                   | Change                                                 |
| --------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------ |
| recall returns 0 for project progress   | docs/ not in knowledge_dirs; vector store empty of docs | Add docs/ to knowledge_dirs; run `omni sync knowledge` |
| search returns 0 for "project progress" | Ripgrep phrase-only; no line has exact phrase           | Multi-word query → OR of words in search.py            |
| ZK/hybrid don’t surface docs            | ZK content ≠ docs/; vector fallback empty               | Same as recall: index docs and rely on vector + hybrid |

These changes improve both **knowledge** and **ZK** search so that project progress and similar doc-based queries are findable and the system can be further tuned (e.g. more knowledge_dirs, or adding a text-search fallback in ZK hybrid) as needed.

---

## Precision Improvements (Recall)

To improve relevance of **knowledge.recall** results:

### 1. Section-aware chunking (ingestion)

- **Location:** `packages/python/core/src/omni/core/knowledge/ingestion.py`
- For markdown in auto mode, chunks are now built by **section** (split on `##` / `###`), one chunk per section (or sub-split if a section is very long). This avoids one giant “index” chunk per file and yields section-level chunks that match queries like “git commit format” or “embedding dimension” more precisely.
- **Takes effect after:** Run **`omni sync knowledge`** again so the vector store is re-indexed with the new chunks. Until then, existing chunks remain the old style.

### 2. TOC / index chunk filtering (recall)

- **Location:** `assets/skills/knowledge/scripts/recall.py`
- Chunks that look like a **table of contents or doc index** (e.g. “| Document |” / “| Description |” with many table rows, or ≥8 rows with markdown links) are **demoted**: they are only used to fill the result list after substantive chunks. So the top results are real sections, not index tables.
- Unit tests: `assets/skills/knowledge/tests/test_recall_filter.py` (`_is_toc_or_index_chunk`, `_filter_and_rank_recall`).

### 3. Minimum score threshold (recall)

- **knowledge.recall** accepts **`min_score`** (float 0–1). Results with score below this value are dropped. Use e.g. `min_score=0.5` or `0.6` for stricter precision when you want fewer but more relevant hits.
- MCP call example: `knowledge.recall` with `query`, `limit`, `min_score` (optional).

### 4. Optional keywords for technical queries

- Passing **`keywords`** (e.g. terms extracted from the query) to **knowledge.recall** enables hybrid search and can improve precision for technical queries (e.g. “embedding dimension truncate” with `keywords=["embedding","dimension","truncate"]`). Document this in skill descriptions or usage guides where helpful.
