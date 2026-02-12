# Keyword Backend Decision Report

- Generated at: `2026-02-12 00:10:16Z`
- Offline source: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v3_skill_based.snap`
- Query count: `8`
- Top-K: `5`

## Offline Metrics

| Backend   |    P@5 |    R@5 |    MRR | nDCG@5 | Success@1 |
| --------- | -----: | -----: | -----: | -----: | --------: |
| Tantivy   | 0.2500 | 0.6875 | 1.0000 | 0.9045 |    1.0000 |
| Lance FTS | 0.2250 | 0.6458 | 1.0000 | 0.8717 |    1.0000 |

## Recommendation

- Decision: `TANTIVY_DEFAULT_WITH_FTS_OPTION`
- Evidence:
  - Tantivy precision lead detected (P@5 0.2500 vs 0.2250).
  - Tantivy recall lead detected (R@5 0.6875 vs 0.6458).

## LLM Duel Signals

- Tantivy wins: `0`
- Lance FTS wins: `2`
- Ties: `6`
- Tantivy win rate: `0.0000`
- Lance FTS win rate: `0.2500`
- Reliable samples: `0`
- Reliable ratio: `0.0000`
- High-confidence samples: `0`
- Avg vote agreement: `1.0000`

> Warning: LLM duel reliability is low. Use offline IR metrics as primary decision evidence.

## Rollout Policy

1. Keep `Tantivy` as default for router/tool discovery latency paths.
2. Enable `Lance FTS` for Lance-native workflows requiring single data plane.
3. Re-run report after any tokenizer/scoring change or dataset refresh.
