# Keyword Backend Decision Report

- Generated at: `2026-02-12 00:33:00Z`
- Offline source: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap`
- Query count: `120`
- Top-K: `5`

## Offline Metrics

| Backend   |    P@5 |    R@5 |    MRR | nDCG@5 | Success@1 |
| --------- | -----: | -----: | -----: | -----: | --------: |
| Tantivy   | 0.3017 | 0.6583 | 1.0000 | 0.8980 |    1.0000 |
| Lance FTS | 0.2233 | 0.5111 | 0.9294 | 0.7865 |    0.9083 |

## Recommendation

- Decision: `TANTIVY_DEFAULT_WITH_FTS_OPTION`
- Evidence:
  - Tantivy precision lead detected (P@5 0.3017 vs 0.2233).
  - Tantivy recall lead detected (R@5 0.6583 vs 0.5111).

## LLM Duel Signals

- Tantivy wins: `9`
- Lance FTS wins: `2`
- Ties: `29`
- Tantivy win rate: `0.2250`
- Lance FTS win rate: `0.0500`
- Reliable samples: `1`
- Reliable ratio: `0.0250`
- High-confidence samples: `1`
- Avg vote agreement: `1.0000`

> Warning: LLM duel reliability is low. Use offline IR metrics as primary decision evidence.

## Rollout Policy

1. Keep `Tantivy` as default for router/tool discovery latency paths.
2. Enable `Lance FTS` for Lance-native workflows requiring single data plane.
3. Re-run report after any tokenizer/scoring change or dataset refresh.
