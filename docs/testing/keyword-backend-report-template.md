# Keyword Backend Report Template (FTS vs Tantivy)

Use this template when generating or comparing keyword-backend evaluation reports. It ensures consistent structure across runs and documents the decision contract.

## When to Use

- After changing tokenizer, scoring, or dataset for router/tool discovery.
- When comparing Lance FTS vs Tantivy for default or optional backend.
- When re-running offline IR metrics or LLM duel pipelines.

## Report Structure

### 1. Header (required)

- **Generated at**: ISO 8601 timestamp (e.g. `2026-02-12T00:33:00Z`).
- **Offline source**: Snapshot or dataset path (e.g. `packages/rust/crates/omni-vector/tests/snapshots/...`).
- **Query count**: Number of evaluation queries.
- **Top-K**: Retrieval depth used for P@K / R@K / nDCG@K.

### 2. Offline Metrics (required)

Table: one row per backend (Tantivy, Lance FTS). Columns:

| Backend | P@5 | R@5 | MRR | nDCG@5 | Success@1 |
| ------- | --: | --: | --: | -----: | --------: |

- **P@5**: Precision at 5.
- **R@5**: Recall at 5.
- **MRR**: Mean reciprocal rank.
- **nDCG@5**: Normalized DCG at 5.
- **Success@1**: Fraction of queries with a correct hit at rank 1.

### 3. Recommendation (required)

- **Decision**: One of `TANTIVY_DEFAULT_WITH_FTS_OPTION`, `LANCE_FTS_DEFAULT`, or documented custom policy.
- **Evidence**: Bullet points citing metric deltas (e.g. Tantivy P@5 lead, recall lead).

### 4. LLM Duel Signals (optional but recommended)

- Tantivy wins / Lance FTS wins / Ties.
- Win rates and reliable/high-confidence sample counts.
- Note when LLM reliability is low; prefer offline IR metrics as primary evidence.

### 5. Rollout Policy (required)

- Default backend for router/tool discovery.
- When to use the non-default backend (e.g. Lance-native single data plane).
- When to re-run the report (e.g. tokenizer/scoring/dataset refresh).

## Decision Contract

- **Primary evidence**: Offline IR metrics (P@5, R@5, nDCG@5) from the snapshot/dataset.
- **Secondary**: LLM duel signals; use only when reliability ratio is sufficient.
- **No global replacement** unless metrics are consistently superior with non-overlapping practical CI margin (see statistical report).

## Reference Reports

- `keyword-backend-decision-report-v4.md` – Decision + LLM duel.
- `keyword-backend-statistical-report.md` – Global and scene-boundary statistics.
- `keyword-backend-detailed-comparison-v3.md` – Per-scenario breakdown.
