# Skill Routing Value Standard (reference)

**Canonical standard:** `packages/shared/schemas/skill-routing-value-standard.md`

The standard lives in **packages/shared/schemas/** together with the routing schemas so that **schema + standard** form the **bidirectional enforcement** contract:

- **Schema** (`omni.router.routing_search.v1`, `routing_search_canonical_v1.json`): defines the algorithm (which value uses semantic/keyword/intent) and payload shape.
- **Standard** (`skill-routing-value-standard.md`): defines how skill authors write `routing_keywords`, `intents`, and `description` for accuracy and no ambiguity.

Skills conform to the standard → `omni sync` → run **algorithm and search tests** → evaluate results → **adjust schema or algorithm** (e.g. canonical boosts, rerank fields) or refine skill values as needed.

---

## Flow: conform → test → adjust

1. **Conform skills** to the standard (researcher, crawl4ai, git, advanced_tools have been updated first; extend to others).
2. **Sync**: `omni sync` to refresh the index.
3. **Run tests**: Routing scenario tests (e.g. `TestRoutingSearchSchemaComplexScenario`), parametrized intent queries, and `omni route test "user phrasing"` (e.g. "帮我研究一下 <url>", "find \*.py files").
4. **Evaluate**: Confirm expected tools in top N; use `omni route test --explain` to inspect vector/keyword contribution.
5. **Adjust**: If ranking or precision is off, either (a) **refine skill values** (more discriminative keywords/intents/description), or (b) **adjust schema/algorithm** (`packages/shared/schemas/snapshots/routing_search_canonical_v1.json` or implementation). Then repeat from step 2.

---

## Where to read the full standard

Open **`packages/shared/schemas/skill-routing-value-standard.md`** for the full rules (routing_keywords, intents, description), examples, checklist, and validation notes. See also **`packages/shared/schemas/README.md`** for the list of schemas and the standard and how they work together.
