---
name: demo
description: Demonstrates UltraRAG-style execution tracing with LangGraph + YAML pipelines. Includes simple hello command, hot reload test, and comprehensive YAML pipeline tests.
metadata:
  author: omni-dev-fusion
  version: "1.1.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/demo"
  routing_keywords:
    - "demo"
    - "tracing"
    - "langgraph"
    - "yaml"
    - "pipeline"
    - "example"
    - "demo"
  intents:
    - "Demonstrate UltraRAG tracing"
    - "Run LangGraph pipeline example"
    - "Show execution with thinking"
    - "Test YAML pipeline"
---

# Demo Skill

Demonstrates UltraRAG-style execution tracing with LangGraph + YAML pipelines.

## Tools

### `hello`

Simple demo command for testing hot reload.

**Parameters**:

- `name` (string, optional): Name to greet (default: "Guest")

### `echo`

Echo back the input message.

**Parameters**:

- `message` (string, optional): Message to echo (default: "Hello!")

### `test_yaml_pipeline`

Test YAML pipeline compilation and execution with omni.tracer.

**Parameters**:

- `pipeline_type` (string, optional): Type of pipeline to test.
  - `"simple"`: Sequential pipeline (analyze → draft → finalize)
  - `"loop"`: Pipeline with iteration loop (analyze → evaluate → reflect)
  - `"branch"`: Pipeline with conditional branching
  - `"rag"`: Full RAG pipeline with retrieval

### `run_langgraph`

Execute packaged graphflow runtime with trace output and quality gates.

**Parameters**:

- `scenario` (string, optional): Scenario name (`"simple"` or `"complex"`)
- `quality_threshold` (string, optional): Draft/finalize quality threshold
- `quality_gate_novelty_threshold` (string, optional): Gate novelty threshold
- `quality_gate_coverage_threshold` (string, optional): Gate coverage threshold
- `quality_gate_min_evidence_count` (string, optional): Minimum evidence count
- `quality_gate_require_tradeoff` (string, optional): Require trade-off in output
- `quality_gate_max_fail_streak` (string, optional): Max gate-fail streak before force-draft

### `list_pipeline_examples`

List available YAML pipeline test examples.

**Returns**:

- Available pipeline types and their descriptions
- Usage instructions

## Pipeline Examples

The demo skill includes YAML pipeline files in `pipelines/` directory:

| File          | Description          | Features                            |
| ------------- | -------------------- | ----------------------------------- |
| `simple.yaml` | Sequential pipeline  | analyze → draft → finalize          |
| `loop.yaml`   | Iterative reflection | quality evaluation + loop           |
| `branch.yaml` | Conditional routing  | router-based branching              |
| `rag.yaml`    | Full RAG             | retrieval + generation + evaluation |

## YAML Pipeline Structure

```yaml
servers:
  generator: builtin

parameters:
  topic: "$topic"

pipeline:
  - generator.analyze
  - generator.draft
  - generator.finalize

runtime:
  checkpointer:
    kind: memory
  tracer:
    callback_dispatch_mode: inline
```

## UltraRAG Features

This demo showcases:

- **YAML pipelines** - Declarative workflow definitions
- **Loop control** - Iterative reflection with max_iterations
- **Conditional branching** - Router-based routing
- **Memory tracking** - Variables saved with history
- **Rich output** - Colored step-by-step tracing

## Usage

```bash
# Simple greeting
omni skill run demo.hello --name "World"

# Echo test
omni skill run demo.echo --message "Test message"

# List available pipeline examples
omni skill run demo.list_pipeline_examples

# Test YAML pipelines
omni skill run demo.test_yaml_pipeline --pipeline_type "simple"
omni skill run demo.test_yaml_pipeline --pipeline_type "loop"
omni skill run demo.test_yaml_pipeline --pipeline_type "branch"
omni skill run demo.test_yaml_pipeline --pipeline_type "rag"

# Run packaged graphflow runtime
omni skill run demo.run_langgraph --scenario "complex"
```
