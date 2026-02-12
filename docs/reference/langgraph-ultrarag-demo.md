# LangGraph UltraRAG Demo (Skill: `demo.run_langgraph`)

> Reference for the iterative analyze/reflect/evaluate workflow implemented in `assets/skills/demo/scripts/tracer.py`.

## Overview

The demo implements a model-agnostic iterative quality loop:

1. `analyzer.analyze` produces structured analysis XML.
2. `evaluator.evaluate` computes deterministic quality signals and routing decisions.
3. `reflector.reflect` produces typed critique XML.
4. Routing continues until quality is acceptable or fail-fast triggers.
5. `drafter.draft` and `drafter.finalize` produce final output.

The core design goal is to prevent "fake improvement" where quality rises without measurable content change.

## XML Contracts

### Analyze output contract

`analyzer.analyze` is normalized to:

```xml
<analysis_contract>
  <thesis>...</thesis>
  <evidence>...</evidence>
  <examples>...</examples>
  <tradeoffs>...</tradeoffs>
  <changes_from_prev>...</changes_from_prev>
</analysis_contract>
```

### Reflect output contract

`reflector.reflect` stores evaluation labels with typed issues:

```xml
<evaluation iteration="N">
  <meta_commentary>false</meta_commentary>
  <duplicate similarity_to_prev_max="0.11">false</duplicate>
  <quality score="0.57" delta="+0.00"/>
  <issue type="specificity" severity="high">...</issue>
  <new_critique>...</new_critique>
  <decision_hint>continue_reflect</decision_hint>
</evaluation>
```

`issue.type` taxonomy:

- `evidence`
- `specificity`
- `tradeoff`
- `completeness`

`issue.severity` taxonomy:

- `low`
- `medium`
- `high`

## Deterministic Quality Gates

The evaluator computes and logs:

- `analysis_similarity`
- `novelty_ratio`
- `coverage` (critique-address coverage)
- `evidence_count`
- `tradeoff_present`
- `gates_passed`
- `gate_fail_streak`

Quality is not allowed to increase when gates fail.

## Fail-Fast Behavior

The workflow now supports two hard-stop mechanisms:

- `no_analysis_improvement`: If analysis is effectively unchanged, a one-time forced rewrite is attempted.
- `improvement_failed`: If quality gates fail for `quality_gate_max_fail_streak` consecutive evaluations, the loop terminates early.

This prevents long low-value loops.

## Runtime Parameters

`run_langgraph` supports scenario selection and optional gate overrides:

```python
await run_langgraph(
    scenario="complex",
    quality_threshold=0.8,
    quality_gate_novelty_threshold=0.20,
    quality_gate_coverage_threshold=0.80,
    quality_gate_min_evidence_count=1,
    quality_gate_require_tradeoff=True,
    quality_gate_max_fail_streak=2,
)
```

### Scenario defaults

- `simple`: lower novelty/coverage thresholds and shorter fail-streak.
- `loop`: medium thresholds.
- `complex`: strict thresholds.

Runtime overrides always take precedence over scenario defaults.

## Command Usage

From Omni skill runtime:

```bash
omni skill run demo.run_langgraph '{"scenario":"complex"}'
```

With custom gates:

```bash
omni skill run demo.run_langgraph '{
  "scenario":"complex",
  "quality_gate_max_fail_streak": 1,
  "quality_gate_novelty_threshold": 0.25
}'
```

## Outputs

The command returns:

- execution metadata (`trace_id`, `steps_count`, duration)
- memory pool summary
- routing reason
- `memory_output_path` JSON snapshot

Memory snapshots are written under:

`.artifacts/ultrarag/<trace_id>_memory.json`

## Known Operational Note

If your environment blocks outbound DNS/network access, provider calls can fail with connection errors and the demo will use fallback outputs. This does not invalidate routing/gate logic, but it limits true LLM-driven content variation.
