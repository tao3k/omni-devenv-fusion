# Keyword Backend Statistical Evidence

- Generated at: `2026-02-12`
- Offline datasets:
  - `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v1.snap`
  - `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v2.snap`
  - `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v3_skill_based.snap`
- Live LLM dataset:
  - `/tmp/keyword-llm-eval-v3-toolcall-full-r1.json`

## 1) Replacement Decision Evidence (Current)

Current evidence is **not sufficient** to justify replacing Tantivy with Lance FTS as global default.

- Offline signal: Tantivy has small but consistent lead on `P@5` and `R@5`.
- Offline `nDCG@5`: mixed (no significant overall winner).
- Live LLM duel signal: still low reliability, cannot be used as replacement proof.

## 2) Offline Paired Statistics (N=22 queries)

Metrics are paired by query (`tantivy - lance_fts`) across v1+v2+v3.

| Metric   | Tantivy Win / Loss / Tie | Mean Delta |     95% Bootstrap CI | Sign Test p-value |
| -------- | -----------------------: | ---------: | -------------------: | ----------------: |
| `P@5`    |             `2 / 0 / 20` |  `+0.0182` |  `[0.0000, +0.0455]` |          `0.5000` |
| `R@5`    |             `2 / 0 / 20` |  `+0.0379` |  `[0.0000, +0.0985]` |          `0.5000` |
| `nDCG@5` |             `3 / 2 / 11` |  `-0.0034` | `[-0.0549, +0.0385]` |          `1.0000` |

Interpretation:

- Differences are mostly ties due easy top1 hit coverage.
- There is no statistically significant global winner yet.
- On risk-sensitive retrieval, Tantivy remains safer due recall advantage and current production behavior.

## 3) Suite-Level Behavior

| Suite | Observation                                                                                     |
| ----- | ----------------------------------------------------------------------------------------------- |
| `v1`  | Fully tied on `P@5` / `R@5` (baseline easy intents).                                            |
| `v2`  | Tantivy better on `P@5`/`R@5`; Lance FTS better on `nDCG@5` in 2 ambiguous CI/workflow queries. |
| `v3`  | Tantivy better on `P@5`/`R@5` and also better `nDCG@5` overall.                                 |

Known FTS-favoring cases observed in v2:

- `testing_ci_pipeline` (`run tests in github actions pipeline`)
- `ambiguous_run_workflow` (`run workflow and tests`)

## 4) Live LLM Judge Reliability (Tool-Call Path)

From `/tmp/keyword-llm-eval-v3-toolcall-full-r1.json`:

- `queries_evaluated=8`
- `tantivy_wins=0`, `lance_fts_wins=2`, `ties=6`
- `reliable_samples=0`, `reliable_ratio=0.0`
- parse statuses: `coerced_non_json=6`, `tool_call_ok=1`, `structured_ok=1`

Interpretation:

- Tool-call contract started working, but only for a minority of samples.
- Reliable evidence threshold is not met.
- LLM duel is currently an auxiliary signal only.

## 5) Scenario Boundary (Operational Policy)

Use `Tantivy` by default for:

- multilingual or mixed-language intent queries (CN + EN)
- workflow/tool-discovery intents needing higher recall
- ambiguous user phrasing where missing one relevant tool is costly

Use `Lance FTS` first for:

- exact phrase / keyword-heavy lookup
- text-first Lance-native workflows that require single data plane
- deterministic substring-style matching tasks

## 6) Final Policy (Now)

Decision: `TANTIVY_DEFAULT_WITH_FTS_OPTION`

- Default backend: `Tantivy`
- Optional backend: `Lance FTS`
- Route to FTS only on explicit exact-match/text-first scenarios.

## 7) Replacement Gate (Must Pass Before Global Switch)

To switch default to Lance FTS, require all three:

1. Offline quality gate:
   - `N >= 100` graded scenario queries
   - `P@5` non-inferior to Tantivy (delta CI lower bound >= `-0.01`)
   - `nDCG@5` superiority CI lower bound > `0`
2. Live LLM gate:
   - `reliable_ratio >= 0.80`
   - `high_confidence_samples / N >= 0.60`
   - winner margin >= `+10%` over Tantivy
3. Performance gate:
   - p95 query latency non-inferior (or better) in production-like load

Until these pass, keep current hybrid policy.
