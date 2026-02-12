# Keyword Backend Replacement Evidence (V4)

- Date: `2026-02-12`
- Offline snapshot: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap`
- Offline size: `120` queries
- Live LLM sample: `/tmp/keyword-llm-eval-v4-q40-r1.json` (`40` queries)

## Direct Conclusion

1. **Do not replace Tantivy with Lance FTS globally.**
2. **Set Tantivy as default backend.**
3. **Keep Lance FTS as optional backend for exact text-heavy paths only.**

## Statistical Evidence (Offline, N=120)

Global paired deltas (`Tantivy - Lance FTS`):

- `P@5`: `+0.0783` (win/loss/tie `38/0/82`, sign-test `p=0.0000`, 95% CI `[+0.0567, +0.1017]`)
- `R@5`: `+0.1472` (win/loss/tie `38/0/82`, sign-test `p=0.0000`, 95% CI `[+0.1056, +0.1917]`)
- `nDCG@5`: `+0.1115` (win/loss/tie `44/3/73`, sign-test `p=0.0000`, 95% CI `[+0.0706, +0.1564]`)

Interpretation:

- All three core metrics significantly favor Tantivy in this large scenario suite.
- This is sufficient evidence for **default selection**.

## Scenario Boundaries

Across all 10 scene types in v4, policy winner is Tantivy:

- `audit`
- `automation`
- `bilingual_mix`
- `exact_keyword`
- `intent_phrase`
- `ops_short`
- `planning`
- `tool_discovery`
- `troubleshooting`
- `workflow_ambiguous`

Practical routing policy:

1. Default route: Tantivy.
2. FTS route: only when caller explicitly requests exact phrase/substring matching.

## Live LLM Evidence (Current Reliability State)

From `40`-query live sample:

- `tantivy_wins=9`, `lance_fts_wins=2`, `ties=29`
- `reliable_samples=1`, `reliable_ratio=0.025`
- parse status: `coerced_non_json=38`, `tool_call_ok=1`, `structured_ok=1`

Interpretation:

- Directional preference also leans Tantivy.
- But LLM judge reliability is still below acceptance threshold, so live result remains secondary evidence.

## Replacement Gate Status

Replacement gate for switching default to Lance FTS:

1. Offline non-inferiority/superiority against Tantivy on large sample.
2. Live LLM reliable ratio >= `0.8`.
3. Production-like latency/throughput non-inferiority.

Current status:

- Gate 1: **not passed for Lance FTS**.
- Gate 2: **not passed**.
- Gate 3: **not evaluated in this run**.

Final decision for now: `TANTIVY_DEFAULT_WITH_FTS_OPTION`.
