# Testing Documentation

This folder holds testing-related docs: evaluation reports, decision records, and guides.

## Canonical references

| Document                                                                     | Use                                                                                                           |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| [Keyword Backend Decision](keyword-backend-decision.md)                      | **Canonical** — Tantivy vs Lance FTS decision, when to use which, how to regenerate reports.                  |
| [Keyword Backend Usage Guide](keyword-backend-usage-guide.md)                | How to use the keyword backend in tests and CLI.                                                              |
| [Omni-Agent Live Multi-Group Runbook](omni-agent-live-multigroup-runbook.md) | Canonical live validation flow for `Test1/Test2/Test3` session isolation + memory evolution + trace evidence. |

## Reports (historical or one-off)

The following are evaluation reports, statistical evidence, or one-off comparisons used to produce the decision above. Kept for traceability; for current behavior use the canonical docs and [Testing Guide](../developer/testing.md).

- `keyword-backend-decision-report.md`, `keyword-backend-decision-report-v4.md` — Decision reports
- `keyword-backend-statistical-report.md`, `keyword-backend-statistical-evidence.md` — Statistical evidence
- `keyword-backend-multi-model-report.md`, `keyword-backend-llm-reliability-batch-report.md` — Multi-model / LLM runs
- `keyword-backend-replacement-evidence-v4.md`, `keyword-backend-detailed-comparison-v3.md` — Evidence and comparisons
- `keyword-backend-report-template.md` — Template for generating reports
- `keyword-eval-model-profiles.md` — Eval model profiles
- `routing-quality-analysis.md`, `router-file-discovery-intent-report.md` — Routing quality and intent reports
- `llm_comprehension_test.md`, `graphflow_modularization.md`, `test_kit_modernization.md`, `scenario-test-driven-autofix-loop.md` — Test design and modernization notes

## Main testing guide

For how to run tests, write tests, and use the test kit: [Developer Testing Guide](../developer/testing.md) and [Test Kit](../reference/test-kit.md).

## Performance Regression Utilities

- `scripts/benchmark_wendao_search.py` — local latency benchmark for `wendao search`.

Recommended usage:

```bash
# just wrapper (defaults: architecture, runs=5, warm_runs=2, debug, no-build)
just benchmark-wendao-search

# direct script wrapper in scripts/ (query runs warm_runs profile build_mode)
bash scripts/benchmark_wendao_search.sh architecture 5 2 debug no-build

# quick local sanity check (uses existing target/debug/wendao when present)
python scripts/benchmark_wendao_search.py --root . --query architecture --runs 5 --warm-runs 2 --no-build

# release-profile benchmark (recommended for performance review)
python scripts/benchmark_wendao_search.py --root . --query architecture --runs 5 --warm-runs 2 --release --no-build

# CI-style gate (fails on threshold breach)
python scripts/benchmark_wendao_search.py \
  --root . \
  --query architecture \
  --runs 7 \
  --warm-runs 2 \
  --no-build \
  --max-p95-ms 1500 \
  --max-avg-ms 1000
```

Developer-mode rule:

- Only rebuild Rust Python bindings when related code changes:
  `uv sync --reinstall-package omni-core-rs`
