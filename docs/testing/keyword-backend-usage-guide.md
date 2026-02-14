# Keyword and Retrieval Engine Usage Guide: Scenario Boundaries and Decision Indicators

Based on the decision loop (v4_large evaluation set and statistical reports), this document defines **when to use which engine or hybrid mode** with clear boundaries and indicators. It is intended for configuration, technology selection, and troubleshooting.

---

## 1. Summary

| Use case                                                             | Recommendation                                                     | Boundary / indicator                                                                                                                                                                                                                  |
| -------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Routing / skill discovery** (natural language query → select tool) | **Hybrid (vector + keyword)** with **Tantivy** on the keyword side | Default when there are no special constraints. Vector side uses **description** semantics; keyword side uses **routing_keywords** for exact match. See [Router field split](../architecture/router.md#field-split-keyword-vs-vector). |
| **Keyword-only retrieval** (exact terms, phrases, code symbols)      | **Tantivy**                                                        | Global P@5 / R@5 / nDCG@5 all favor Tantivy over Lance FTS with no losses.                                                                                                                                                            |
| **Must share storage with Lance** (vector + FTS in one data plane)   | **Lance FTS**                                                      | Use only when the architecture requires a single data plane.                                                                                                                                                                          |
| **Vector-only retrieval** (embedding only, no query text)            | **Vector-only** (no keyword path)                                  | Semantic similarity; path that only uses embedding.                                                                                                                                                                                   |

**In short:** Use **Tantivy + Hybrid** by default. Switch the keyword engine to Lance FTS only when a single Lance data plane is required. For retrieval shape: use **Hybrid** when there is natural language and tool/document discovery; use **Vector-only** when only semantic similarity is needed.

---

## 2. Retrieval Mode Boundaries (Hybrid vs vector-only vs keyword-only)

“Mode” here means: **Hybrid (vector + keyword)**, **vector-only**, **keyword-only**. This is independent of whether the keyword backend is Tantivy or Lance FTS.

| Mode             | When to use                                                                                                          | Indicator                                                                                                                                   |
| ---------------- | -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hybrid**       | User input is natural language or short phrase; need both semantics and keywords for routing / skill discovery / RAG | Query text present + need to recall tools/documents/snippets; `omni route test`, skill index search, and RAG retrieval use this by default. |
| **Vector-only**  | Only embedding, no query text; or explicitly semantic similarity only                                                | Input is embedding only; or API only exposes `vector_search`.                                                                               |
| **Keyword-only** | Explicitly need full-text/symbol match (e.g. code symbols, exact IDs, fixed phrases)                                 | No semantics needed; only term/phrase match; can use Tantivy or Lance FTS (see next section).                                               |

**Decision tree:**

- Is there a **natural language query** and a need for **tool/document discovery**? → **Yes** → use **Hybrid** (keyword engine default: Tantivy).
- Is it **semantic similarity only** with no text retrieval? → **Yes** → use **Vector-only**.
- Is it **keyword/symbol match only**? → **Yes** → use **keyword retrieval** with Tantivy (unless Lance single-data-plane constraint applies).

---

## 3. Keyword Engine Boundaries (Tantivy vs Lance FTS)

The keyword engine only affects the **keyword branch of Hybrid** and **keyword-only retrieval**. Choice: Tantivy or Lance FTS.

### 3.1 Default and only recommended exception

| Condition                                                           | Engine        | Rationale                                                                                                        |
| ------------------------------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------- |
| **No special constraint**                                           | **Tantivy**   | v4_large: P@5, R@5, nDCG@5 all favor Tantivy; sign test p≈0; no losses (35 wins, 0 losses, 85 ties for P@5/R@5). |
| **Single data plane required** (vector and FTS in same Lance store) | **Lance FTS** | Architecture/ops constraint; quality slightly below Tantivy but acceptable.                                      |

**Do not:** Switch globally to Lance FTS because “Lance is slightly better in one scenario.” Current statistics do not support “Lance FTS globally better.”

### 3.2 Per-scene boundaries and indicators

v4_large statistics for the 10 scenes are below. **Policy Winner** comes from the statistical report; **Recommendation** reflects whether using Lance FTS is acceptable.

| Scene                  | Meaning (typical query)        | ΔP@5  | ΔR@5  | ΔnDCG@5   | Winner  | Recommendation                                                                                                            |
| ---------------------- | ------------------------------ | ----- | ----- | --------- | ------- | ------------------------------------------------------------------------------------------------------------------------- |
| **audit**              | Audit/compliance-style queries | +0.27 | +0.56 | +0.28     | Tantivy | **Strongly prefer Tantivy**; large gap.                                                                                   |
| **bilingual_mix**      | Mixed-language (e.g. EN+ZH)    | +0.12 | +0.22 | +0.23     | Tantivy | **Prefer Tantivy**.                                                                                                       |
| **intent_phrase**      | Intent phrases                 | +0.02 | +0.03 | +0.09     | Tantivy | Tantivy                                                                                                                   |
| **planning**           | Planning/step-style            | +0.05 | +0.08 | +0.11     | Tantivy | Tantivy                                                                                                                   |
| **troubleshooting**    | Troubleshooting                | +0.07 | +0.13 | +0.12     | Tantivy | Tantivy                                                                                                                   |
| **workflow_ambiguous** | Ambiguous workflow             | +0.03 | +0.06 | +0.05     | Tantivy | Tantivy                                                                                                                   |
| **automation**         | Automation-related             | +0.03 | +0.06 | +0.02     | Tantivy | Tantivy                                                                                                                   |
| **exact_keyword**      | Exact keyword                  | +0.03 | +0.06 | +0.02     | Tantivy | Tantivy                                                                                                                   |
| **ops_short**          | Short ops commands             | +0.03 | +0.06 | +0.02     | Tantivy | Tantivy                                                                                                                   |
| **tool_discovery**     | Tool discovery                 | +0.08 | +0.15 | **−0.01** | split   | Only scene with slightly worse nDCG; still **default Tantivy** (P/R clearly better); consider A/B if ranking is critical. |

**Boundary conclusions:**

- **Every scene** has Tantivy ≥ Lance FTS on P@5 and R@5 (no losses).
- **Only tool_discovery** is slightly worse on nDCG@5 by 0.01 (split); all other scenes favor Tantivy.
- **No default “per-scene switch to Lance FTS”**; if in the future a scene shows “Lance clearly better than Tantivy” and the product strongly depends on that scene, consider a scene-level override (re-run evaluation and update this doc).

### 3.3 When Lance FTS is allowed or required

- **Allowed:** Architecture or ops requires **vector and FTS in the same Lance store** (single data plane, simpler deployment).
- **Not recommended:** Changing the default to Lance FTS only because “one metric is slightly better” or “fewer dependencies”; current evidence does not support it.
- **Re-evaluate:** If you change tokenizer, scoring, or skill set, re-run `just keyword-backend-report` and `just keyword-backend-statistical`, then update the table above from the new reports.

---

## 4. Decision indicators quick reference

| Question                                     | Indicator / boundary                                | Conclusion                                   |
| -------------------------------------------- | --------------------------------------------------- | -------------------------------------------- |
| Which retrieval for routing/skill discovery? | Natural language + need to discover tools/documents | **Hybrid**                                   |
| Which keyword engine inside Hybrid?          | No single-data-plane constraint                     | **Tantivy**                                  |
| When is Lance FTS acceptable?                | Lance single data plane required                    | **Only then** choose Lance FTS               |
| Should a scene use Lance?                    | v4 stats: no scene recommends Lance                 | **No**; default all Tantivy                  |
| Pure semantics, no text?                     | Embedding only / similarity only                    | **Vector-only**; keyword engine not involved |

---

## 5. Relation to decision loop docs

- **Data source:** `keyword-backend-decision-report.md` (decision report), `keyword-backend-statistical-report.md` (statistics and scene boundaries).
- **Policy and regeneration:** `keyword-backend-decision.md` (default policy, fallback, how to re-run evaluation and reports).
- **This doc:** A **usage guide** on top of those conclusions, fixing “scenario → engine/mode” boundaries and indicators for direct reference during selection and troubleshooting.

### Multi-language routing (non-English queries)

**SKILL.md and all indexed content are English-only.** We do not know the user’s language, so the pipeline uses **English as the common language**. The **translation layer is on by default**: non-English queries are translated to English before routing so that keyword matching works. This layer is part of the search pipeline and also supports a stronger search (e.g. catalog enrichment).

- **Default**: Translation is enabled by default (`router.translation.enabled: true`). Set to `false` only if all queries are known to be English.
- **Flow**: `HybridSearch.search()` calls `translate_query_to_english(query)`; the result is used for both embedding and keyword search. See [Router architecture](../architecture/router.md#query-translation-non-english--english).
- **No non-English in SKILL.md**: Keep all content in English; the translation layer handles non-English user input.
