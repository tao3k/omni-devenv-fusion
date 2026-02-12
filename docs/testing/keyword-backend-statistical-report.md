# Keyword Backend Statistical Report

- Generated at: `2026-02-12 00:14:48Z`
- Snapshot: `packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap`
- Query count: `120`

## Global Statistics (Tantivy - Lance FTS)

| Metric | Win/Loss/Tie | Mean Delta |             95% CI | Sign-Test p |
| ------ | -----------: | ---------: | -----------------: | ----------: |
| P@5    |      38/0/82 |    +0.0783 | [+0.0567, +0.1017] |      0.0000 |
| R@5    |      38/0/82 |    +0.1472 | [+0.1056, +0.1917] |      0.0000 |
| nDCG@5 |      44/3/73 |    +0.1115 | [+0.0706, +0.1564] |      0.0000 |

## Scene Boundaries

| Scene              | Queries |    ΔP@5 |    ΔR@5 | ΔnDCG@5 | Policy Winner |
| ------------------ | ------: | ------: | ------: | ------: | ------------- |
| audit              |      12 | +0.2667 | +0.5556 | +0.2856 | tantivy       |
| automation         |      12 | +0.0333 | +0.0556 | +0.0189 | tantivy       |
| bilingual_mix      |      12 | +0.1167 | +0.2222 | +0.2377 | tantivy       |
| exact_keyword      |      12 | +0.0500 | +0.0833 | +0.0357 | tantivy       |
| intent_phrase      |      12 | +0.0333 | +0.0556 | +0.1019 | tantivy       |
| ops_short          |      12 | +0.0333 | +0.0556 | +0.0189 | tantivy       |
| planning           |      12 | +0.0500 | +0.0833 | +0.1095 | tantivy       |
| tool_discovery     |      12 | +0.1000 | +0.1806 | +0.1098 | tantivy       |
| troubleshooting    |      12 | +0.0833 | +0.1528 | +0.1570 | tantivy       |
| workflow_ambiguous |      12 | +0.0167 | +0.0278 | +0.0398 | tantivy       |

## Decision

- Default backend: `Tantivy`
- Use scene winner for overrides where `Policy Winner` is not the default.
- Do not perform global replacement unless all global metrics are consistently superior with non-overlapping practical CI margin.
