# Shared Schemas and Routing Standards

This directory is the **single source of truth** for:

1. **Routing algorithm and payloads** — JSON schemas and canonical instances that define how routing search works and what shape the data has.
2. **Skill routing value standard** — How skill authors should write `routing_keywords`, `intents`, and `description` so that routing is accurate and unambiguous.

Together they form the **bidirectional enforcement** contract: schema + standard are applied from both sides (algorithm/implementation and skill content), then validated by tests.

---

## Schemas

| File                                         | Role                                                                                                                                                                         |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `omni.router.search_config.v1.schema.json`   | Router search **configuration** (weights, thresholds, adaptive retry). Used by OmniRouter; resolved by default from here.                                                    |
| `omni.router.route_test.v1.schema.json`      | Contract for `omni route test --json` output shape.                                                                                                                          |
| `omni.router.routing_search.v1.schema.json`  | Meta-schema for the routing search algorithm (semantic, keyword, intent).                                                                                                    |
| `snapshots/routing_search_canonical_v1.json` | Canonical algorithm v1: per-value assignment, keyword boosts, strategies, rerank fields. **Edit this** to change algorithm behaviour; implementations and tests align to it. |
| `snapshots/route_test_canonical_v1.json`     | Canonical route test output example.                                                                                                                                         |
| `omni.vector.tool_search.v1.schema.json`     | Tool search result payload (name, routing_keywords, scores, etc.).                                                                                                           |

---

## Standard

| File                              | Role                                                                                                                                                           |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `skill-routing-value-standard.md` | **Canonical** standard for `routing_keywords`, `intents`, and `description`. Skills conform to this so that algorithm and search tests can validate precision. |

---

## Flow: conform → test → adjust

1. **Skills conform** to `skill-routing-value-standard.md` (starting with researcher, crawl4ai, then others).
2. **Sync**: `omni sync` to refresh the index.
3. **Algorithm and search tests**: Run routing scenario tests and `omni route test "user phrasing"` with real phrasings.
4. **Evaluate**: Check expected tools in top N; use `--explain` for score breakdown.
5. **Adjust**: If needed, either (a) refine skill values (keywords/intents/description), or (b) adjust `routing_search_canonical_v1.json` or algorithm (boosts, rerank, new value flows). Then repeat from step 2.

See `skill-routing-value-standard.md` §5 and §6 for details.
