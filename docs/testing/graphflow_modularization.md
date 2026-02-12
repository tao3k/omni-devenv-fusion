# Graphflow Modularization

## Goal

Move LangGraph graphflow logic into `packages/python` as a first-class feature, while keeping `demo` skill as a thin user-facing entrypoint.

## New Package Structure

- `packages/python/foundation/src/omni/tracer/graphflow/__init__.py`
  - Public API surface (`run_graphflow_pipeline` and core types)
- `packages/python/foundation/src/omni/tracer/graphflow/runtime.py`
  - Graph assembly, node routing, scenario execution
- `packages/python/foundation/src/omni/tracer/graphflow/nodes.py`
  - Node business logic (`analyze/evaluate/reflect/draft/finalize`)
- `packages/python/foundation/src/omni/tracer/graphflow/builders.py`
  - Scenario defaults, runtime override application, graph wiring, initial state factory
- `packages/python/foundation/src/omni/tracer/graphflow/types.py`
  - `DemoState`, `StepType`, `ExecutionStep`, `ExecutionTrace`
- `packages/python/foundation/src/omni/tracer/graphflow/tracer.py`
  - `LangGraphTracer` and memory snapshot persistence
- `packages/python/foundation/src/omni/tracer/graphflow/llm_service.py`
  - LLM orchestration, fallback handling, meta-commentary guard
- `packages/python/foundation/src/omni/tracer/graphflow/evaluation.py`
  - XML helpers, similarity checks, quality/evaluation utilities
- `packages/python/foundation/src/omni/tracer/graphflow/ui.py`
  - Rich output rendering helpers

## Skill Boundary

- `assets/skills/demo/scripts/tracer.py` remains a thin command wrapper.
- The skill command delegates execution to `omni.tracer.graphflow.run_graphflow_pipeline`.
- No graphflow core business logic remains in the skill wrapper file.

## Why This Is Better

- Clear namespace: `graphflow` is a product feature, not a demo artifact.
- Better modularity: state, tracing, LLM, evaluation, UI, and runtime are isolated.
- Better testability: helper modules can be tested without invoking the full runtime.
- Cleaner extension path: new evaluators/nodes can be added without growing a monolith.

## Tests Added

- `assets/skills/demo/tests/test_tracer_command_wrapper.py`
  - Verifies command wrapper delegates to package runtime.
- `packages/python/foundation/tests/unit/tracer/test_graphflow_package.py`
  - Verifies graphflow package API and internal module imports.
- `packages/python/foundation/tests/unit/tracer/test_graphflow_builders.py`
  - Verifies scenario defaults, override behavior, and initial state creation.
