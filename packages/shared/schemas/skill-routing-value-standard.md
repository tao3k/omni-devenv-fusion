# Skill Routing Value Standard (canonical)

**Canonical location:** `packages/shared/schemas/skill-routing-value-standard.md`  
**With:** `omni.router.routing_search.v1.schema.json` + `snapshots/routing_search_canonical_v1.json` = **bidirectional enforcement**: schema defines algorithm and payloads; this standard defines how skill authors fill routing values so that algorithm and search tests can validate precision.

Skills conform to this standard → `omni sync` → run algorithm and search tests → adjust schema or algorithm based on results.

---

## 1. Purpose

- **routing_keywords** and **intents** are used by the hybrid/agentic search (Tantivy BM25, embedding blob, rerank). Vague or overlapping values cause wrong tool selection or ties.
- **description** (SKILL.md and `@skill_command` decorator) is the main text embedded and indexed; it must clearly signal "when to use this tool" for both the model and the algorithm.
- This standard defines **rules and examples** so that authors can write values that improve precision; audits and scenario tests validate alignment.

---

## 2. routing_keywords

### 2.1 Goals

- **Accuracy**: Terms that users actually say when they want this skill (e.g. "commit", "save changes", "git commit").
- **Discrimination**: Prefer terms that distinguish this skill from others. Avoid single generic words that many skills use (e.g. "search" alone is ambiguous across code, advanced_tools, knowledge).
- **No semantic clash**: If two skills share a term (e.g. "research"), add **compound or context terms** so the router can prefer the right one (e.g. researcher: "research", "analyze_repo", "repository"; crawl4ai: "crawl", "research url", "analyze page").

### 2.2 Rules

| Rule                                                                     | Example                                                                                                                                       |
| ------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Include **user phrasings** (phrases users type or say)                   | "commit code", "save changes", "pull request", "research url"                                                                                 |
| Prefer **2–3 discriminative terms** per skill that others don’t use      | crawl4ai: "crawl", "scrape", "web crawl"; researcher: "deep_research", "sharded_analysis"                                                     |
| Limit **generic single tokens** that appear in many skills               | "search" appears in code, advanced_tools, knowledge — pair with "code search", "file find", "knowledge search" or rely on intents/description |
| Total per skill: **~5–20**; more is OK only if most are discriminative   | git has many phrases; advanced_tools has "find", "fd", "ripgrep", "rg" for clarity                                                            |
| Normalize: **lowercase**, **trim**, **no empty** (handled at index time) | —                                                                                                                                             |

### 2.3 Examples (do / avoid)

- **Good**: crawl4ai uses "research url", "analyze page", "web crawl" so "research a URL" routes to crawl4ai when appropriate; researcher uses "analyze_repo", "repository_map" so "analyze repo" stays with researcher.
- **Avoid**: Relying only on "search" or "find" for a skill that has multiple competitors; add at least one skill-specific or compound term.

---

## 3. intents

### 3.1 Goals

- **User-goal oriented**: Each intent = "When the user wants to …" (short phrase). The algorithm and the model match queries to these phrases.
- **Unambiguous**: Intents should separate this skill from others. Prefer "Research a repository from URL" vs "Crawl a URL and extract content" so researcher vs crawl4ai are distinct.
- **Cover common phrasings**: Include natural variants (e.g. "Commit code", "Save my changes"). Non-English (e.g. "帮我研究一下") can be in intents or in description; if in intents, keep short.

### 3.2 Rules

| Rule                                                                  | Example                                                                                                   |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **One short phrase per intent** (≤ ~12 words)                         | "Find files by name, extension, or glob pattern"                                                          |
| **Start with a verb or goal** (Find, Research, Commit, Search, Crawl) | "Research repository", "Crawl a web page"                                                                 |
| **Avoid internal jargon**; use wording users would use                | Prefer "Search for text in files" over "Execute ripgrep over codebase"                                    |
| **No duplicate meaning** within the same skill                        | Don’t add "Search code" and "Search in code" if they mean the same                                        |
| **Overlap across skills**: Make the difference explicit in the phrase | researcher: "Analyze git repo or link"; crawl4ai: "Research a URL or link", "Help me research a web page" |

### 3.3 Examples (do / avoid)

- **Good**: advanced_tools intents clearly separate "Find files by name/extension/glob" vs "Search for text or regex in code content". Git intents list concrete actions: "Commit code", "Stash changes", "Check git status".
- **Avoid**: Very long intents (full sentences with multiple clauses); or intents that could apply to several skills without a distinguishing phrase.

---

## 4. description (SKILL.md and @skill_command)

### 4.1 Goals

- **First sentence = primary signal** for routing and embedding: what the tool/skill does and **when to use it**. The algorithm embeds this; put the most discriminative part first.
- **Model-friendly**: Use terms that appear in user queries and in routing_keywords/intents so that semantic and keyword branches agree.
- **Stable one-liner**: For decorators, the first line (or first sentence) should stand alone as a routing summary; optional Args/Returns below for docs.

### 4.2 Rules

| Rule                                                                                                  | Example                                                                                                              |
| ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **SKILL.md `description`**: Start with "Use when …" or "Use for …" and list 2–4 concrete use cases    | "Use when crawling web pages, extracting markdown, or when the user provides a URL to fetch or crawl."               |
| **Decorator `description`**: First sentence = one-liner (what + when); multi-line OK for Args/Returns | "Crawl a web page with intelligent chunking." vs long docblock after                                                 |
| **Avoid leading with internal names** (e.g. "Uses LangGraph to …") unless the user would say that     | Prefer "Research a repository and produce an index" over "Runs the Sharded Deep Research Workflow" as the first line |
| **Match vocabulary** to routing_keywords and intents                                                  | If intents say "Research a URL or link", description should use "URL", "link", "research"                            |

### 4.3 Examples (do / avoid)

- **Good**: crawl4ai SKILL.md: "Use when crawling web pages, extracting markdown … or when the user provides a URL or link to fetch or crawl." researcher: "Use when analyzing repositories, conducting deep research … or when the user wants to research or analyze a git repo, a GitHub link, or a repository URL."
- **Avoid**: Putting the most discriminative "when to use" in the second paragraph; or a first sentence that only names the implementation (e.g. "Execute the packaged graphflow runtime") without the user goal.

---

## 5. Conformance flow (bidirectional enforcement)

1. **Skills conform** to this standard (routing_keywords, intents, description). First adopters: researcher, crawl4ai; then extend to other skills.
2. **Sync**: Run `omni sync` so the index reflects skill metadata.
3. **Algorithm and search tests**: Run routing scenario tests (e.g. `TestRoutingSearchSchemaComplexScenario`), parametrized intent queries, and `omni route test "user phrasing"` with real phrasings (e.g. "帮我研究一下 <url>", "find \*.py files").
4. **Evaluate**: Confirm expected tools in top N; use `--explain` to inspect vector/keyword contribution.
5. **Adjust**: If ranking or precision is off, either (a) **refine skill values** (more discriminative keywords/intents/description), or (b) **adjust schema/algorithm** (e.g. `routing_search_canonical_v1.json` boosts, rerank fields, or new value flows). Then repeat from step 2.

---

## 6. Validation

- **Scenario tests**: `TestRoutingSearchSchemaComplexScenario` and parametrized intent queries assert expected tools in top N. Run after changing any skill’s routing values and `omni sync`.
- **Route test**: `omni route test "user phrasing"` with real phrasings (including non-English). Use `--explain` to inspect scores.
- **Audit overlap**: List per-skill `routing_keywords` and `intents`; flag tokens that appear in 3+ skills and ensure each skill has discriminative terms.

---

## 7. Checklist for new or updated skills

- [ ] **routing_keywords**: At least 2–3 terms that other skills don’t use; include user phrasings; no heavy reliance on a single generic token.
- [ ] **intents**: Short user-goal phrases (≤ ~12 words); distinct from other skills; no duplicate meaning within the skill.
- [ ] **SKILL.md description**: Starts with "Use when …" and concrete use cases; vocabulary aligned with keywords/intents.
- [ ] **Decorator description**: First sentence = one-liner for routing; optional Args/Returns below.
- [ ] After changes: `omni sync` and run scenario/route tests to validate.
