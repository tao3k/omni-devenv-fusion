# Keyword Backend LLM Reliability Batch Report

- Date: `2026-02-12`
- Snapshot: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap`
- Eval config:
  - `vote_rounds=1`
  - `max_api_attempts_per_round=2`
  - `per_query_timeout_seconds=60` for first two 20-query batches
  - `per_query_timeout_seconds=30` for split batches (`10+10`) used to complete batches 3 and 4

## Batch Results (4 x 20)

| Batch                             | Queries | Tantivy Wins | Lance FTS Wins | Ties | Reliable Samples | Reliable Ratio |
| --------------------------------- | ------: | -----------: | -------------: | ---: | ---------------: | -------------: |
| `b0` (`start=0`)                  |      20 |            6 |              1 |   13 |                1 |         0.0500 |
| `b1` (`start=20`)                 |      20 |            4 |              2 |   14 |                3 |         0.1500 |
| `b2` (`start=40`, merged `10+10`) |      20 |            7 |              0 |   13 |                3 |         0.1500 |
| `b3` (`start=60`, merged `10+10`) |      20 |            1 |              5 |   14 |                2 |         0.1000 |

## Aggregate (80 Queries)

- Tantivy wins: `18`
- Lance FTS wins: `8`
- Ties: `54`
- Tantivy win rate: `0.2250`
- Lance FTS win rate: `0.1000`
- Reliable samples: `9`
- Reliable ratio: `0.1125`
- High-confidence samples: `8`

Parse-status distribution:

- `coerced_non_json`: `58`
- `structured_ok`: `11`
- `structured_retry_ok`: `7`
- `tool_call_ok`: `4`

## Conclusion

1. Reliability improved versus early runs (from ~`0.00` to ~`0.11` aggregate), but is still far below production-confidence target (`>=0.80`).
2. Live LLM signal remains secondary evidence.
3. Offline statistical evidence still dominates decision: keep `Tantivy` default, keep `Lance FTS` optional.
