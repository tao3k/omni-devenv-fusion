# Tantivy vs Lance FTS: Decision (Canonical)

This document is the **single source of truth** for the keyword search backend choice: default strategy, when to use the alternative, fallback conditions, and how to re-run the evaluation loop.

## Fixed evaluation set

- **Rust test**: `packages/rust/crates/omni-vector/tests/test_keyword_backend_quality.rs`
- **Scenarios**: v1 (minimal), v2, v3 (skill-based), **v4_large** (120 queries, 10 scene layers)
- **Output**: Insta snapshots under `packages/rust/crates/omni-vector/tests/snapshots/`:
  - `test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap` (primary for decision)
  - v1/v2/v3 snapshots used for regression and smaller runs

Each scenario runs the same query set against **Tantivy** and **Lance FTS** and records P@5, R@5, MRR, nDCG@5, Success@1; v4 includes a `scene` field per query for per-layer analysis.

## Default and fallback

| Aspect              | Policy                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Default backend** | **Tantivy** for router/tool discovery and latency-sensitive paths                                                    |
| **Use Lance FTS**   | When a Lance-native workflow needs a single data plane (vector + FTS in one store)                                   |
| **Fallback**        | If Tantivy is unavailable or disabled, Lance FTS can be selected via configuration; no automatic failover by default |

Decision label: **`TANTIVY_DEFAULT_WITH_FTS_OPTION`**. See Rollout Policy in the generated report.

**→ When to use which engine (boundaries and indicators):** [Keyword Backend Usage Guide](./keyword-backend-usage-guide.md) — Hybrid vs vector-only vs keyword-only, Tantivy vs Lance FTS, per-scene conclusions and quick reference.

## Regenerating the decision loop

1. **Refresh snapshots** (after tokenizer, scoring, or dataset changes):

   ```bash
   cargo test -p omni-vector --test test_keyword_backend_quality
   ```

   Update any intended snapshot with `cargo insta review` (or accept current output).

2. **Regenerate the decision report** from the v4 snapshot:

   ```bash
   just keyword-backend-report
   ```

   Or explicitly:

   ```bash
   uv run python scripts/generate_keyword_backend_decision_report.py \
     --snapshot packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap \
     --output docs/testing/keyword-backend-decision-report.md
   ```

   Optional: pass `--llm-report /path/to/llm-eval.json` if you have run the LLM duel pipeline.

3. **Regenerate statistical comparison** (bootstrap CI, sign test, per-scene policy winner):

   ```bash
   just keyword-backend-statistical
   ```

   Output: `docs/testing/keyword-backend-statistical-report.md`.

4. **When to re-run**
   - Tokenizer or scoring changes in `omni-vector`
   - Skill/tool set or relevance labels change (e.g. new scenarios or v4 query set)
   - Before switching default backend or changing rollout policy

## Generated artifacts

- **`docs/testing/keyword-backend-usage-guide.md`** – **Usage guide**: When to use which engine (Hybrid/vector/keyword), Tantivy vs Lance FTS boundaries and decision indicators (including per-scene table and quick reference).
- **`docs/testing/keyword-backend-decision-report.md`** – Generated report (metrics, recommendation, per-scene summary, rollout policy). Overwritten by `just keyword-backend-report`.
- **`docs/testing/keyword-backend-statistical-report.md`** – Statistical evidence (bootstrap CI, sign test, scene boundaries). Overwritten by `just keyword-backend-statistical`.
- **`docs/testing/keyword-backend-decision-report-v4.md`** – Historical v4 report with LLM duel (if kept).
- **`docs/testing/keyword-backend-report-template.md`** – Structure and decision contract for reports.
- **`docs/testing/keyword-backend-*.md`** – Other comparison docs; reference when needed.

## Per-scene (v4) summary

The generated report includes a **Per-scene (v4) summary** table: which scene layers (e.g. exact_keyword, intent_phrase, bilingual_mix) favor Tantivy, which favor Lance FTS, and which are tie. Use it to interpret tradeoffs by use case; aggregate metrics remain the primary decision evidence.

## Code references

- Default backend: `packages/rust/crates/omni-vector/src/ops/core.rs` (`KeywordSearchBackend::Tantivy`).
- Report script: `scripts/generate_keyword_backend_decision_report.py` (default snapshot: v4_large; `--no-per-scene` for v1/v2).
