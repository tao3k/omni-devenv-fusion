# Shared Schemas and Routing Standards

This directory is the **single source of truth** for:

1. **Routing algorithm and payloads** — JSON schemas and canonical instances that define how routing search works and what shape the data has.
2. **Skill routing value standard** — How skill authors should write `routing_keywords`, `intents`, and `description` so that routing is accurate and unambiguous.

Together they form the **bidirectional enforcement** contract: schema + standard are applied from both sides (algorithm/implementation and skill content), then validated by tests.

## Contract Freeze Lock

- A0 freeze gate lock: `packages/shared/schemas/contract-freeze.lock.json`
- Verifier/update tool: `scripts/contract_freeze_lock.py`
- CI/local gate entrypoint: `scripts/ci-contract-freeze.sh` (`just test-contract-freeze`)

When a contract change is intentional, regenerate the lock:

```bash
python3 scripts/contract_freeze_lock.py --update
```

---

## Schemas

| File                                                             | Role                                                                                                                                                                         |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `omni.router.search_config.v1.schema.json`                       | Router search **configuration** (weights, thresholds, adaptive retry). Used by OmniRouter; resolved by default from here.                                                    |
| `omni.router.route_test.v1.schema.json`                          | Contract for `omni route test --json` output shape.                                                                                                                          |
| `omni.router.routing_search.v1.schema.json`                      | Meta-schema for the routing search algorithm (semantic, keyword, intent).                                                                                                    |
| `snapshots/routing_search_canonical_v1.json`                     | Canonical algorithm v1: per-value assignment, keyword boosts, strategies, rerank fields. **Edit this** to change algorithm behaviour; implementations and tests align to it. |
| `snapshots/route_test_canonical_v1.json`                         | Canonical route test output example.                                                                                                                                         |
| `omni.vector.tool_search.v1.schema.json`                         | Tool search result payload (name, routing_keywords, scores, etc.).                                                                                                           |
| `omni.link_graph.record.v1.schema.json`                          | Legacy cross-runtime LinkGraph record contract (`hit`, `neighbor`, `metadata`) for existing Python boundary payloads.                                                        |
| `omni.link_graph.search_options.v2.schema.json`                  | Legacy cross-runtime LinkGraph search options contract (`match_strategy`, `sort`, `case_sensitive`, graph filters, temporal filters).                                        |
| `omni.link_graph.retrieval_plan.v1.schema.json`                  | Legacy cross-runtime LinkGraph policy plan contract (selected mode, confidence, and budget fields).                                                                          |
| `xiuxian_wendao.link_graph.valkey_cache_snapshot.v1.schema.json` | LinkGraph Valkey cache snapshot contract for xiuxian-wendao index cache payload (`schema_version`, fingerprint, docs, sections, adjacency maps).                             |
| `xiuxian_wendao.link_graph.stats.cache.v1.schema.json`           | LinkGraph persistent stats cache contract used by `xiuxian-wendao` runtime (`schema`, `source_key`, `updated_at_unix`, `stats`).                                             |
| `xiuxian_wendao.link_graph.saliency.v1.schema.json`              | LinkGraph GraphMem saliency contract persisted in Valkey (`saliency_base`, `decay_rate`, `activation_count`, `current_saliency`).                                            |
| `xiuxian_wendao.hmas.task.v1.schema.json`                        | HMAS blackboard task payload contract (`requirement_id`, `objective`, `hard_constraints`).                                                                                   |
| `xiuxian_wendao.hmas.evidence.v1.schema.json`                    | HMAS blackboard evidence payload contract (`requirement_id`, `evidence`, optional `source_nodes_accessed`).                                                                  |
| `xiuxian_wendao.hmas.conclusion.v1.schema.json`                  | HMAS blackboard conclusion payload contract (`requirement_id`, `summary`, `confidence_score`, `hard_constraints_checked`).                                                   |
| `xiuxian_wendao.hmas.digital_thread.v1.schema.json`              | HMAS digital thread payload contract (audit trail with sources, checked constraints, and confidence).                                                                        |
| `omni.discover.match.v1.schema.json`                             | Canonical discover match row contract (`tool`, `usage`, `score/final_score`, `confidence`, `ranking_reason`, `input_schema_digest`).                                         |
| `omni.memory.gate_event.v1.schema.json`                          | 3-in-1 memory gate lifecycle event contract (retain/obsolete/promote decision envelope).                                                                                     |
| `omni.agent.route_trace.v1.schema.json`                          | Turn-level route trace contract for Omega route selection, fallback, and injection stats.                                                                                    |
| `omni.skills_monitor.signals.v1.schema.json`                     | Skills monitor machine-readable signal contract (`retrieval_signals`, `link_graph_signals`) used by verbose runtime observability output.                                    |

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
