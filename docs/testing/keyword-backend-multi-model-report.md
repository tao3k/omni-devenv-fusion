# Keyword Backend Multi-Model Report

- Generated at: `2026-02-12 04:14:53Z`
- Source JSON: `/tmp/keyword-llm-eval-v4-multimodel-q3-v3.json`
- Snapshot: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap`
- Models: `MiniMax-M2.1, MiniMax-M2.5`
- Evaluated models: `MiniMax-M2.1`
- Best model by reliability: `MiniMax-M2.1`

## Per-Model Summary

| Model        | Queries | Tantivy Win Rate | Lance FTS Win Rate | Reliable Ratio | High-Conf | Fallback Usage |
| ------------ | ------: | ---------------: | -----------------: | -------------: | --------: | -------------: |
| MiniMax-M2.1 |       3 |           0.6667 |             0.0000 |         0.0000 |         0 |         0.0000 |

## Recommendation

- Keep `MiniMax-M2.1` as primary judge model for now.
- Keep offline IR metrics as primary replacement evidence when reliable ratio is low.
- Use fallback model only for parse-recovery, not for changing business verdict policy.

## Skipped Models

- `MiniMax-M2.5`: `probe_failed_or_empty_response`
