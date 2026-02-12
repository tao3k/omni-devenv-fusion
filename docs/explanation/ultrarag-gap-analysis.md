# UltraRAG Gap Analysis & Improvement Plan

> Comparing our UltraRAG-style tracer with the original UltraRAG implementation

## Overview

Based on deep analysis of [UltraRAG source code](../.data/harvested/OpenBMB/UltraRAG/index.md), this document identifies gaps between our implementation and UltraRAG's execution tracing system.

---

## Architecture Comparison

| Component                 | UltraRAG                        | Our Implementation    | Status                 |
| ------------------------- | ------------------------------- | --------------------- | ---------------------- |
| **Pipeline Data Manager** | `UltraData`                     | `ExecutionTracer`     | ✅ Equivalent          |
| **Memory Pool**           | `memory_*` variables            | `MemoryPool`          | ✅ Enhanced            |
| **Memory Serialization**  | `write_memory_output()`         | `TraceStorage.save()` | ✅ Equivalent          |
| **Stream Callbacks**      | `stream_callback`               | `StreamCallback`      | ✅ Implemented         |
| **Branch State**          | Complex branching support       | Partial (YAML config) | ✅ YAML Pipeline       |
| **Context Variables**     | `contextvars` for thread safety | `ContextVar`          | ✅ Implemented         |
| **YAML Pipeline Config**  | Declarative pipelines           | `PipelineConfig`      | ✅ LangGraph Generator |
| **Server Modules**        | Retriever/Reranker/Generator    | Not implemented       | ⚪ Future              |
| **State Machine**         | SurveyCPM workflows             | Not implemented       | ⚪ Future              |

---

## Implementation Status

### ✅ Completed This Sprint

1. **Memory Variable Convention**
   - `$variable`: Parameters (read-only)
   - `variable`: Global variables
   - `memory_*`: History-tracked variables

2. **Context Variables (Thread-Safe)**
   - `ContextVar` for step/trace tracking
   - No global state contamination

3. **Stream Callbacks (Real-time)**
   - `enable_stream_callback` parameter
   - Async listeners for live updates
   - Events: step_start, step_end, thinking, memory_save, trace_end

4. **YAML Pipeline Generator**
   - `PipelineConfig` from YAML
   - `LangGraphPipelineBuilder`
   - `create_langgraph_from_pipeline()`
   - Variable interpolation (`$var`, `memory_*`)

### ⚪ Future Enhancements

- Branch state management (parallel execution)
- Server module architecture
- State machine workflows (SurveyCPM style)

---

## Key Differences from UltraRAG

### Our Approach: LangGraph + YAML

We use LangGraph as the workflow engine, with YAML configuration generating LangGraph at runtime:

```
YAML Pipeline → PipelineConfig → LangGraphPipelineBuilder → LangGraph App
                                                              ↓
ExecutionTracer ← TracingCallbackHandler ← astream_events()
```

### UltraRAG Approach: Custom Pipeline Engine

UltraRAG uses a custom Python-based pipeline execution engine:

```
YAML Pipeline → UltraData → Custom Executors → write_memory_output()
```

### Why LangGraph?

| Aspect               | LangGraph                   | UltraRAG Custom      |
| -------------------- | --------------------------- | -------------------- |
| **State Management** | TypedDict + CheckpointSaver | Custom global_vars   |
| **Streaming**        | astream_events              | Custom callbacks     |
| **Checkpoints**      | Built-in                    | Custom serialization |
| **Visualization**    | Mermaid integration         | Custom UI            |
| **Tool Integration** | MCP native                  | MCP wrappers         |

---

## Usage Comparison

### Our Implementation

```python
# YAML pipeline.yaml
servers:
  retriever: path/to/server
  generator: path/to/server

pipeline:
  - retriever.search:
      input:
        query: "$query"
      output:
        - docs
  - generator.generate:
      input:
        context: "$docs"
        question: "$query"
      output:
        - answer
```

```python
from omni.tracer import create_langgraph_from_pipeline, ExecutionTracer

tracer = ExecutionTracer(trace_id="run1", enable_stream_callback=True)

# Build LangGraph from YAML
config = PipelineConfig.from_yaml("pipeline.yaml")
app = create_langgraph_from_pipeline(config, tracer=tracer)

# Execute with full tracing
async for event in app.astream_events(initial_state):
    # Events automatically tracked
    ...
```

### UltraRAG Equivalent

```python
# UltraRAG style
from ultrarag import UltraData

data = UltraData(pipeline_yaml_path, server_configs, parameter_file)

# Execute pipeline
result = await data.run()

# Memory snapshot
data.write_memory_output("pipeline_name", timestamp)
```

---

## Memory Management Comparison

### UltraRAG

```python
# Parameters (from parameter.yaml)
$query = "What is RAG?"
$top_k = 5

# Global vars
global_vars["result"] = computed_value

# Memory (history tracked)
memory_search_results = [result1, result2, result3]
memory_plan = [plan1, plan2]
```

### Our Implementation

```python
tracer = ExecutionTracer()

# Parameters
tracer.set_param("$query", "What is RAG?")
tracer.set_param("$top_k", 5)

# Global vars
tracer.set_global("result", computed_value)

# Memory (full history)
tracer.save_to_memory("memory_search_results", result1, step_id)
tracer.save_to_memory("memory_search_results", result2, step_id)
tracer.save_to_memory("memory_search_results", result3, step_id)

# Get history
history = tracer.get_memory_history("memory_search_results")
# [(timestamp1, result1, step_id1), ...]
```

---

## Streaming Comparison

### UltraRAG

```python
def stream_callback(event_type, data):
    print(f"[{event_type}] {data}")

# Callback passed during execution
result = await data.run(stream_callback=stream_callback)
```

### Our Implementation

```python
async def my_listener(event: str, data: dict):
    print(f"[{event}] {data}")

tracer = ExecutionTracer(enable_stream_callback=True)
tracer.add_stream_listener(my_listener)

# Events streamed automatically
# [step_start] {'step_id': '...', 'name': 'plan'}
# [thinking] {'content': 'Analyzing...'}
# [memory_save] {'var_name': 'memory_result', 'value': {...}}
# [step_end] {'step_id': '...', 'status': 'completed'}
```

---

## Future Enhancements

### Phase 2: Branch State Management

```python
# YAML with branches
pipeline:
  - branch:
      router: decision_router
      branches:
        simple:
          - retriever.search
          - generator.generate
        complex:
          - retriever.search
          - reasoner.analyze
          - retriever.search
          - generator.generate
```

### Phase 3: Server Modules

Integrate UltraRAG-style server modules:

- Retriever server with multiple backends (FAISS, Milvus)
- Reranker server with cross-encoder support
- Generator server (local vLLM + remote API)

### Phase 4: State Machine Workflows

Implement SurveyCPM-style workflows:

```python
# Custom pipeline with state machine
custom_pipeline = {
    "workflow": "survey_generation",
    "states": ["search", "plan", "write", "extend"],
    "transitions": {
        "search": {"plan": "documents_found"},
        "plan": {"write": "plan_approved"},
        "write": {"extend": "wrote_content"},
        "extend": {"done": "finalized", "search": "needs_more"}
    }
}
```

---

## References

- [UltraRAG Source](https://github.com/OpenBMB/UltraRAG)
- [UltraRAG Core Framework Analysis](../.data/harvested/OpenBMB/UltraRAG/shards/01_core_framework_&_api_layer.md)
- [UltraRAG Server Architecture](../.data/harvested/OpenBMB/UltraRAG/shards/02_server_module_architecture.md)
- [Tracer Documentation](../reference/tracer.md)
