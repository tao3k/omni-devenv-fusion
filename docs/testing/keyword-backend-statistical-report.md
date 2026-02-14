# Keyword Backend Statistical Report

- Generated at: `2026-02-12 19:30:07Z`
- Snapshot: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap`
- Query count: `120`

## Global Statistics (Tantivy - Lance FTS)

| Metric | Win/Loss/Tie | Mean Delta |             95% CI | Sign-Test p |
| ------ | -----------: | ---------: | -----------------: | ----------: |
| P@5    |      35/0/85 |    +0.0733 | [+0.0517, +0.0967] |      0.0000 |
| R@5    |      35/0/85 |    +0.1389 | [+0.0986, +0.1833] |      0.0000 |
| nDCG@5 |      40/7/73 |    +0.0930 | [+0.0529, +0.1380] |      0.0000 |

## Scene Boundaries

| Scene              | Queries |    ΔP@5 |    ΔR@5 | ΔnDCG@5 | Policy Winner |
| ------------------ | ------: | ------: | ------: | ------: | ------------- |
| audit              |      12 | +0.2667 | +0.5556 | +0.2826 | tantivy       |
| automation         |      12 | +0.0333 | +0.0556 | +0.0189 | tantivy       |
| bilingual_mix      |      12 | +0.1167 | +0.2222 | +0.2347 | tantivy       |
| exact_keyword      |      12 | +0.0333 | +0.0556 | +0.0189 | tantivy       |
| intent_phrase      |      12 | +0.0167 | +0.0278 | +0.0886 | tantivy       |
| ops_short          |      12 | +0.0333 | +0.0556 | +0.0189 | tantivy       |
| planning           |      12 | +0.0500 | +0.0833 | +0.1060 | tantivy       |
| tool_discovery     |      12 | +0.0833 | +0.1528 | -0.0118 | split         |
| troubleshooting    |      12 | +0.0667 | +0.1250 | +0.1208 | tantivy       |
| workflow_ambiguous |      12 | +0.0333 | +0.0556 | +0.0523 | tantivy       |

## Decision

- Default backend: `Tantivy`
- Use scene winner for overrides where `Policy Winner` is not the default.
- Do not perform global replacement unless all global metrics are consistently superior with non-overlapping practical CI margin.
