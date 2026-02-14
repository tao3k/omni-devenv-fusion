# Skills and Router Databases

> Two separate LanceDB stores: **skills** = full tool/skill data; **router** = search-algorithm scores only. No content duplication.

See also: [Vector/Router Schema Contract](vector-router-schema-contract.md), [Routing Search Schema](routing-search-schema.md) (per-value semantic/keyword/intent assignment), [Router Architecture](../architecture/router.md).

---

## 1. Database roles

| Database   | Path           | Purpose                                                                                                                                                                       |
| ---------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **skills** | `skills.lance` | Single source of truth for skill/tool metadata and content. Used for discovery and hybrid search (vector + keyword over this table).                                          |
| **router** | `router.lance` | Routing-only data: search-algorithm scores (e.g. `vector_score`, `keyword_score`, `rrf_score`). No duplication of skills content. Used for score cache and routing decisions. |

- **Skills DB**: populated by `omni sync` / reindex from `assets/skills/`; contains full tool rows (name, description, routing_keywords, embeddings, etc.).
- **Router DB**: populated when the routing layer runs search and persists scores (e.g. per query/session, tool_id, component scores). It does **not** store tool descriptions, keywords, or embeddings; it only stores data derived from the search algorithm.

---

## 2. No redundancy

- Skills content (tools, references, metadata) lives **only** in the skills database.
- The router database must **not** replicate tool rows or skill metadata. It may store:
  - Score rows: e.g. `(tool_id, vector_score, keyword_score, rrf_score, query_id/session_id, timestamp)`
  - Or a minimal routing index that **references** tools by id and holds only scores.
- Hybrid search and discovery always read tool data from the **skills** table; the router DB is optional for caching or tuning routing behaviour.

---

## 3. Config and paths

Paths are defined in `omni.foundation.config.database`:

- `get_database_paths()` returns `skills`, `router`, `knowledge`, `memory`.
- `get_database_path(name)` accepts `"skills"` or `"router"` (among others).

- **Sync**: Full sync (`omni sync`) initializes the router DB (creates `router.lance` and the `scores` table) after skills sync; init is non-fatal so sync still succeeds if router init fails.
- **Route test**: `omni route test "<query>"` persists score rows to the router DB after each search (tool_id, vector_score, keyword_score, etc.); persistence is non-fatal and does not change the command output.
