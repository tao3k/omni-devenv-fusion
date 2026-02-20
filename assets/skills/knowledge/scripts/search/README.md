# Knowledge Search Package

Unified search for the knowledge skill. Single entry: `run_search(query, mode=...)`.

## Modes (completeness)

| Mode         | Component          | Returns                                                                                                             |
| ------------ | ------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `hybrid`     | LinkGraph + vector | `success`, `query`, `link_graph_total`, `vector_total`, `merged`, `merged_total`, `graph_stats`, `graph_stats_meta` |
| `keyword`    | ripgrep            | `query`, `count`, `results`, `scope`                                                                                |
| `link_graph` | LinkGraph only     | `success`, `query`, `parsed_query`, `search_options`, `total`, `results`, `graph_stats`, `graph_stats_meta`         |
| `vector`     | recall             | `success`, `query`, plus recall payload                                                                             |

Every response includes at least `query`. Async modes include `success: True`.
`graph_stats` now always returns canonical keys:
`total_notes`, `orphans`, `links_in_graph`, `nodes_in_graph` (zero fallback on cold miss).
`graph_stats_meta` indicates stats provenance and freshness (`source`, `cache_hit`,
`fresh`, `age_ms`, `refresh_scheduled`).
`link_graph` mode also returns:

- `parsed_query`: residual free-text query after directive extraction.
- normalized `search_options`: effective options after Rust planner parsing.
  Input uses strict schema v2 payload under `search_options`, for example:
  `{"schema":"omni.link_graph.search_options.v2","match_strategy":"fts","sort_terms":[{"field":"score","order":"desc"}],"filters":{"link_to":{"seeds":["note-a"]}}}`.
  Graph filters live under `search_options.filters`:
  `include_paths`, `exclude_paths`, `tags`, `link_to`, `linked_by`, `related`,
  `mentions_of`, `mentioned_by_notes`, `orphan`, `tagless`, `missing_backlink`.
  Temporal filters remain top-level in `search_options`:
  `created_after`, `created_before`, `modified_after`, `modified_before`.

## Layout

- `__init__.py` – `run_search`, `SEARCH_MODES`, re-exports
- `keyword.py` – ripgrep over docs/references/skills/harvested
- `link_graph.py` – LinkGraph reasoning
- `vector.py` – semantic search via recall
- `hybrid.py` – LinkGraph + vector fusion

## Tests

See `tests/test_search_completeness.py` for the completeness contract and mode verification.
