# Keyword Eval Model Profiles

This document defines how keyword-backend LLM evaluation supports flexible model switching and multi-model runs.

## Goals

1. Keep evaluator logic provider-agnostic.
2. Support quick model swaps without code changes.
3. Support fallback model and multi-model comparison.

## Judge Profiles

Judge profiles are currently defined in code:
`packages/python/foundation/src/omni/foundation/services/keyword_eval.py`
(`DEFAULT_JUDGE_PROFILES`).

- `fast`
  - `max_api_attempts_per_round=1`
  - `per_query_timeout_seconds=45`
- `balanced` (default)
  - `max_api_attempts_per_round=2`
  - `per_query_timeout_seconds=90`
- `strict`
  - `max_api_attempts_per_round=3`
  - `per_query_timeout_seconds=120`

Default behavior uses the built-in `balanced` profile.
For experiment scripts, select another built-in profile with `--model-profile`.

Note:

- This is separate from router confidence profiles (`router.search.*` in settings: system packages/conf/settings.yaml, user $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml),
  which are used by `omni route test`.

## CLI Usage

Probe supported models first:

```bash
uv run python scripts/probe_llm_models.py \
  --models "MiniMax-M2.1,MiniMax-M2.5" \
  --timeout-seconds 15 \
  --output /tmp/llm-model-probe.json
```

Single model with fallback:

```bash
uv run python scripts/run_keyword_backend_llm_eval.py \
  --snapshot packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap \
  --model primary-model \
  --fallback-model backup-model \
  --model-profile balanced \
  --max-queries 20 \
  --output /tmp/keyword-llm-eval-single.json
```

Multi-model run:

```bash
uv run python scripts/run_keyword_backend_llm_eval.py \
  --snapshot packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap \
  --multi-model "model-a,model-b,model-c" \
  --skip-unsupported-models \
  --model-profile strict \
  --max-queries 20 \
  --output /tmp/keyword-llm-eval-multi.json
```

Batched multi-model run (recommended for stability):

```bash
uv run python scripts/run_keyword_backend_multi_model_batches.py \
  --snapshot packages/rust/crates/omni-vector/tests/snapshots/test_keyword_backend_quality__keyword_backend_quality_scenarios_v4_large.snap \
  --models "MiniMax-M2.1,MiniMax-M2.5" \
  --skip-unsupported-models \
  --model-profile balanced \
  --batch-size 10 \
  --num-batches 4 \
  --output /tmp/keyword-llm-eval-multi-batched.json
```

## Output Structure

Single-model output contains:

- `judge_profile`
- `primary_model`
- `fallback_model`
- `llm_duel_summary`
- `llm_duel_details[*].judge_model`

Multi-model output contains:

- `models`
- `best_model_by_reliability`
- `model_reliability`
- `evaluated_models`
- `skipped_models`
- `reports` (per model full single-model report)

## Reliability Guidance

Treat LLM duel as secondary evidence unless:

1. `reliable_ratio >= 0.80`
2. `high_confidence_samples / queries >= 0.60`
3. Cross-model direction is stable (no conflicting winner trend)
