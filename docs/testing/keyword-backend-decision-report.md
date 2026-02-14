# Keyword Backend Decision Report

- Generated at: `2026-02-12 19:30:07Z`
- Offline source: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap`
- Query count: `120`
- Top-K: `5`

## Offline Metrics

| Backend   |    P@5 |    R@5 |    MRR | nDCG@5 | Success@1 |
| --------- | -----: | -----: | -----: | -----: | --------: |
| Tantivy   | 0.2967 | 0.6500 | 0.9958 | 0.8795 |    0.9917 |
| Lance FTS | 0.2233 | 0.5111 | 0.9294 | 0.7865 |    0.9083 |

## Recommendation

- Decision: `TANTIVY_DEFAULT_WITH_FTS_OPTION`
- Evidence:
  - Tantivy precision lead detected (P@5 0.2967 vs 0.2233).
  - Tantivy recall lead detected (R@5 0.6500 vs 0.5111).

## LLM Duel Signals

- Not provided. Run live LLM eval and regenerate this report:

```bash
uv run python scripts/run_keyword_backend_llm_eval.py --output /tmp/keyword-llm-eval.json
uv run python scripts/generate_keyword_backend_decision_report.py --llm-report /tmp/keyword-llm-eval.json
```

## Per-scene (v4) summary

| Scene layer | Tantivy better                                                                     | Lance FTS better | Tie                                                  |
| ----------- | ---------------------------------------------------------------------------------- | ---------------- | ---------------------------------------------------- |
| v4 scenes   | audit, bilingual_mix, intent_phrase, planning, troubleshooting, workflow_ambiguous | —                | automation, exact_keyword, ops_short, tool_discovery |

## Rollout Policy

1. Keep `Tantivy` as default for router/tool discovery latency paths.
2. Enable `Lance FTS` for Lance-native workflows requiring single data plane.
3. Re-run report after any tokenizer/scoring change or dataset refresh.
