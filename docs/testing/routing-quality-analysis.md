# Routing Quality Analysis: Why "research + URL" Ranks crawl4ai Above researcher

## Observed Result

Query: `help me to analzye/research https://github.com/nickel-lang/tf-ncl/...`

| Rank | Tool                        | Score | Confidence |
| ---- | --------------------------- | ----- | ---------- |
| 1    | crawl4ai.crawl_url          | 1.271 | high       |
| 2    | researcher.git_repo_analyer | 0.982 | high       |

Expected: researcher (e.g. `run_research_graph`) should rank first for "analyze/research + GitHub URL". Instead crawl4ai.crawl_url ranks first.

## Pipeline (No Hardcode)

1. **Query normalization** — URL → `github url`; no built-in typo list (`analzye` stays).
2. **Embedding** — Query embedded as-is.
3. **Rust hybrid search** — Vector (LanceDB) + Keyword (Tantivy BM25) with weighted RRF.
4. **Field boosting (Rust)** — Name token match (+0.5 per term in tool name), metadata alignment (routing_keywords +0.08, intents +0.09, description +0.03).
5. **Python intent-overlap boost** — Query terms in `router.search.intent_vocab` (or default: research, analyze, crawl, …) matched to result `routing_keywords`/`intents`; boost per hit.
6. **Relationship rerank** — Boost tools related to top results (same-skill, shared-refs, keyword overlap).
7. **Confidence** — Attribute overlap (query terms in keywords/intents) can promote medium → high.

## Root Causes (Data + Algorithm)

### 1. Query term "url" favors crawl4ai

- **Normalized query tokens:** `help`, `me`, `to`, `analzye`, `research`, `github`, `url`.
- **crawl4ai** has `url`, `link`, `research`, `research url`, `analyze page` in routing_keywords.
- **researcher** has `research`, `analyze`, `github`, `repo`, `link` but **no "url"** in routing_keywords.

So:

- BM25 (Tantivy) and Rust metadata_alignment_boost both give crawl4ai an extra signal for **"url"**; researcher gets nothing for "url".
- **Name token boost:** `crawl4ai.crawl_url` contains the token **"url"** → +0.5 in Rust fusion. researcher tools (`run_research_graph`, `git_repo_analyer`) do not have "url" in the tool name → no name boost for "url".

So crawl4ai gets: research + url (keywords + name). Researcher gets: research + github (keywords only). That gap explains a large part of the score difference.

### 2. Typo "analzye" does not match "analyze"

- We use config-only typos; no built-in list. So "analzye" is not corrected.
- routing_keywords use "analyze"; BM25 and metadata boost do not see a match for "analzye".
- Semantic (embedding) can still relate "analzye" to "analyze", but keyword/rerank do not. Correct approach for robust behavior: model + semantic or model + XML Q&A normalization, not expanding a static typo map.

### 3. run_research_graph vs git_repo_analyer

- Top result for researcher is `git_repo_analyer`, not `run_research_graph`.
- Both are under the same skill; relationship graph gives same-skill edges. So if one is in top-N, the other can get a small boost.
- Why run_research_graph might rank lower: vector/BM25 might favor git_repo_analyer’s description or keyword set for this query, or run_research_graph’s index content (description + keywords from skill + reference) may not stress "url" / "github url" enough.

## Why “omni sync” seemed to have no effect

Route test was using a **different store path** than reindex:

- **Reindex** (and `omni sync`) writes to `get_database_path("skills")` = `.cache/omni-vector/skills.lance`. The Tantivy keyword index is at `skills.lance/keyword_index`.
- **HybridSearch** (used by `omni route test`) was using `get_vector_db_path()` = `.cache/omni-vector` (base dir). The store then uses a **separate** keyword index at `.cache/omni-vector/keyword_index`, which sync never updates.

So the vector table (LanceDB) was the same, but the **keyword index** used at route test was stale. Fix: HybridSearch now defaults to `get_database_path("skills")` so it uses the same store and keyword index that reindex updates. After this fix, run `omni sync` once; then `omni route test "..."` will use the updated keywords/intents.

## Data-Only Fix (Recommended)

Improve ranking by **data**, not by hardcoding skill names in code:

1. **researcher SKILL.md**  
   Add to `routing_keywords`: `url`, `github url`, `repository url`, (and keep existing e.g. `research`, `analyze`, `github`, `repo`).  
   Then BM25 and metadata_alignment_boost will match the token **"url"** for researcher tools as well, and "github url" can match when the normalizer produces that phrase.

2. **researcher reference run_research_graph.md**  
   Add to `routing_keywords`: `url`, `github url`, `repo url`, `research url`.  
   So the tool that is the best fit for "research + GitHub URL" gets stronger keyword and metadata signal.

3. **Reindex**  
   Run `omni sync` (or reindex skills) so Tantivy and LanceDB see the new keywords. Relationship graph will be rebuilt from the updated index.

No algorithm or hardcoded skill names are required; scaling to more skills stays data-driven.

## Algorithm / Pipeline Notes (For Future)

- **Name token boost** in Rust gives a fixed +0.5 per query term that appears in the **tool name**. So `crawl_url` naturally wins on "url". Alternatives (e.g. boosting when query terms appear in routing_keywords with higher weight than name-only) could be considered later; the data fix above already balances the signal.
- **Intent vocab** and **intent-overlap boost** are already data-driven (config + result metadata); no change needed for this case.
- For **typos and paraphrasing**: use model + semantic search or model + XML Q&A–style normalization instead of a large static typo map.
