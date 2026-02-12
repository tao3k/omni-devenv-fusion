# Execution Tracing System (UltraRAG Style)

> Fine-grained execution tracing for LangGraph + MCP agents

See also: [LangGraph UltraRAG Demo](./langgraph-ultrarag-demo.md) for the skill-level iterative analyze/reflect/evaluate workflow, XML contracts, and quality-gate routing. See also: [Retrieval Namespace](./retrieval-namespace.md) for retrieval backends, factory, node factory, and runtime backend defaults.

## Overview

The tracer system provides comprehensive visibility into agent execution by capturing:

- **Step-by-step execution path** through the cognitive graph
- **LLM thinking process** including streaming tokens
- **Tool calls and their results**
- **Memory pool** for tracking variable state changes
- **Execution timing** and duration metrics

This is inspired by UltraRAG's approach to making agent execution transparent and debuggable.

## Architecture

```
omni/tracer/
├── interfaces.py        # Type definitions (StepType, ExecutionStep, ExecutionTrace)
├── engine.py            # ExecutionTracer core implementation
├── callbacks.py         # Callback system (TracingCallback, CallbackManager)
├── langgraph.py         # LangGraph integration (TracingCallbackHandler)
├── pipeline_schema.py   # Pipeline dataclasses + YAML validation
├── pipeline_builder.py  # Pipeline compiler (steps/loops/branches -> graph definition)
├── pipeline_runtime.py  # LangGraph assembly + executor/runtime APIs
└── storage.py           # Trace persistence (TraceStorage)
```

Architecture guardrails are enforced with unit tests under `packages/python/foundation/tests/unit/tracer/`:

- `test_pipeline_architecture_rules.py`
- `test_invoker_architecture_rules.py`
- `test_pipeline_modularity.py`

### Guardrail Execution

Run architecture guardrails locally:

```bash
uv run pytest -m architecture packages/python/foundation/tests/unit/tracer
```

Run specific tracer architecture rule files:

```bash
uv run pytest \
  packages/python/foundation/tests/unit/tracer/test_pipeline_architecture_rules.py \
  packages/python/foundation/tests/unit/tracer/test_invoker_architecture_rules.py
```

CI enforcement:

- GitHub Actions workflow `ci.yaml` includes required job `architecture-gate`.
- Job command:
  `pytest -q -m architecture packages/python/foundation/tests/unit/tracer packages/python/foundation/tests/unit/rag`.
- Any failure blocks merge.

### Runtime YAML Options

`PipelineConfig` supports an optional `runtime` block:

```yaml
runtime:
  checkpointer:
    type: memory # memory | none
  invoker:
    include_retrieval: true
  retrieval:
    default_backend: lance # lance | hybrid
  tracer:
    callback_dispatch_mode: inline # inline | background
  state:
    schema: builtins:dict # optional module:Type
  tool_contracts:
    retriever.index:
      required_input_keys: [documents]
```

Use `create_langgraph_from_yaml(path, ...)` to apply these runtime defaults
automatically when building the graph.

Validation uses two layers:

1. Semantic validation in `pipeline_schema.py` for precise domain errors.
2. JSON Schema validation in `pipeline_json_schema.py` for structural constraints and unknown keys.
3. Tool contract validation in `pipeline_json_schema.py` for known step requirements.
   Built-in contracts are versioned in `contracts/contracts.v1.json`, and you can
   extend contracts with `runtime.tool_contracts` (new tools only; overriding
   built-in contracts is rejected).

Runtime override precedence:

1. Explicit function arguments (for example `retrieval_default_backend="hybrid"`)
2. YAML `runtime.*` defaults
3. Built-in defaults

## UltraRAG Memory Conventions

The tracer supports UltraRAG-style variable naming conventions:

| Prefix      | Type      | Description                        | Storage    |
| ----------- | --------- | ---------------------------------- | ---------- |
| `$variable` | Parameter | Read-only parameters (from config) | `_params`  |
| `variable`  | Global    | Mutable global variables           | `_globals` |
| `memory_*`  | Memory    | History-tracked variables          | `_memory`  |

### Usage

```python
tracer = ExecutionTracer(trace_id="session-123")

# Parameters ($variable)
tracer.set_param("$query", "What is RAG?")
tracer.get_param("query")  # Returns: "What is RAG?"

# Global variables
tracer.set_global("result", computed_value)
tracer.get_global("result")  # Returns: computed_value

# Memory variables (history-tracked)
tracer.save_to_memory("memory_search_results", results, step_id)
tracer.save_to_memory("memory_plan", plan, step_id)

# Get memory history
history = tracer.get_memory_history("memory_search_results")
# Returns: [(timestamp, value, source_step), ...]

# Get memory summary
summary = tracer.get_memory_summary()
# Returns: {"params": 1, "globals": 1, "memory": {"memory_search_results": 1}}
```

### Benefits

- **Parameters**: Clear distinction between read-only inputs and mutable state
- **Memory**: Full history for debugging and replay
- **Convention**: Self-documenting code

## Context Variables (Thread-Safe)

The tracer uses Python's `contextvars` for thread-safe execution tracking:

```python
class ExecutionTracer:
    # Thread-safe context variables
    _current_step_id: ContextVar[str | None] = ContextVar("_current_step_id", default=None)
    _current_trace_id: ContextVar[str | None] = ContextVar("_current_trace_id", default=None)

    @property
    def current_step_id(self) -> str | None:
        """Get current step ID (thread-safe)."""
        return ExecutionTracer._current_step_id.get()

    @property
    def current_trace_id(self) -> str | None:
        """Get current trace ID (thread-safe)."""
        return ExecutionTracer._current_trace_id.get()
```

Benefits:

- Safe for concurrent/async execution
- No global state contamination
- Works with nested async calls

## Stream Callbacks (Real-time)

Enable real-time event streaming during execution:

```python
async def stream_handler(event: str, data: dict):
    print(f"[{event}] {data}")

tracer = ExecutionTracer(
    trace_id="session",
    enable_stream_callback=True
)

# Add stream listener
tracer.add_stream_listener(stream_handler)

# Events are streamed in real-time:
# [step_start] {'step_id': '...', 'name': 'plan', 'step_type': 'node_start'}
# [thinking] {'step_id': '...', 'content': 'Analyzing...'}
# [step_end] {'step_id': '...', 'name': 'plan', 'status': 'completed'}
# [memory_save] {'var_name': 'memory_result', 'source_step': '...'}
# [trace_end] {'trace_id': '...', 'success': True, 'step_count': 5}
```

## YAML Pipeline to LangGraph Generator

Declaratively define workflows with YAML, generate LangGraph at runtime.

### Pipeline YAML Format

```yaml
# pipeline.yaml
servers:
  retriever: path/to/retriever/server
  generator: path/to/generator/server

parameters:
  query: "What is RAG?"
  top_k: 5

pipeline:
  # Simple step
  - retriever.search

  # Step with parameters
  - retriever.search:
      input:
        query: "$query"
        top_k: "$top_k"
      output:
        - docs
        - scores

  # Generator with context
  - generator.generate:
      input:
        context: "$docs"
        question: "$query"
      output:
        - answer
```

### Usage

```python
from omni.tracer import load_pipeline, create_pipeline_executor, ExecutionTracer

# Create tracer
tracer = ExecutionTracer(trace_id="pipeline_run", enable_stream_callback=True)

# Load and execute pipeline
executor = create_pipeline_executor("pipeline.yaml", tracer=tracer)
results = await executor.run(parameters={"query": "New question"})

# Or build LangGraph directly
from omni.tracer import create_langgraph_from_pipeline, PipelineConfig

config = PipelineConfig.from_yaml("pipeline.yaml")
app = create_langgraph_from_pipeline(config, tracer=tracer)
```

### Pipeline Features

| Feature                     | Description                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Top-level Validation        | `pipeline` must contain at least one step                                                                                                                                                                                                                                                                                                                                                                                                     |
| Server Namespace Validation | `servers` keys must match identifier pattern `[A-Za-z_][A-Za-z0-9_]*`, and values must be non-empty strings                                                                                                                                                                                                                                                                                                                                   |
| Sequential                  | Linear step execution                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Parameters                  | `$variable` syntax for inputs                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Variables                   | `$var` references to previous outputs                                                                                                                                                                                                                                                                                                                                                                                                         |
| Namespace Validation        | When `servers` is declared, every `server.tool` step must use a declared server key                                                                                                                                                                                                                                                                                                                                                           |
| Step Config Validation      | Tool steps accept only `input` (mapping) and `output` (list of non-empty strings)                                                                                                                                                                                                                                                                                                                                                             |
| Loop Validation             | `loop.max_iterations` must be integer `>= 1`, and `loop.steps` must contain at least one step                                                                                                                                                                                                                                                                                                                                                 |
| Branch Validation           | `branch.branches` must contain at least one branch and each branch must contain at least one step; `branch.router` and `branch.field` must be non-empty strings; `branch.router` can be logical name or `server.tool` (when dotted, server must be declared); `value_map` keys must be declared branch names and values must be lists of non-empty strings; routing tokens must be unique within a branch and cannot map to multiple branches |
| Loops                       | `{"loop": {"steps": [...], "max_iterations": 3}}`                                                                                                                                                                                                                                                                                                                                                                                             |
| Branches                    | `{"branch": {"router": "...", "branches": {...}}}`                                                                                                                                                                                                                                                                                                                                                                                            |

### Python API

```python
from omni.tracer import (
    PipelineConfig,
    PipelineExecutor,
    LangGraphPipelineBuilder,
)

# Load from YAML
config = PipelineConfig.from_yaml("pipeline.yaml")

# Build graph definition
builder = LangGraphPipelineBuilder(config)
graph_def = builder.build()

# graph_def contains:
# - nodes: {node_name: {server, tool, input_mapping, output_mapping}}
# - edges: [(from_node, to_node), ...]
# - servers: {name: path, ...}
# - parameters: {...}
```

## Core Concepts

### StepType Enum

Represents different types of steps in the execution trace:

| StepType                               | Description                                |
| -------------------------------------- | ------------------------------------------ |
| `CHAIN_START` / `CHAIN_END`            | Lifecycle boundaries                       |
| `LLM_START` / `LLM_END` / `LLM_STREAM` | LLM operations (streaming tokens captured) |
| `TOOL_START` / `TOOL_END`              | Tool invocations                           |
| `RETRIEVAL`                            | Knowledge retrieval operations             |
| `REASONING`                            | Explicit reasoning steps                   |
| `NODE_START` / `NODE_END`              | Graph node boundaries                      |
| `ERROR`                                | Error conditions                           |

### ExecutionStep

A single step in the execution trace:

```python
@dataclass
class ExecutionStep:
    step_id: str              # Unique identifier
    step_type: StepType       # Type of step
    name: str                 # Node/tool name
    parent_id: str | None     # Hierarchical parent
    input_data: dict | None   # Input to the step
    output_data: dict | None  # Output from the step
    reasoning_content: str    # Thinking process
    timestamp: datetime       # When step started
    duration_ms: float        # Execution time
    status: str              # pending/running/completed/error
```

### MemoryPool

Tracks variable state changes over time (UltraRAG concept):

```python
# Save a variable
pool.save("result", computed_value, source_step_id)

# Get latest value
latest = pool.get_latest("result")

# Get full history
history = pool.get_history("result")  # [(timestamp, value, source_step), ...]
```

### ExecutionTrace

Complete execution trace:

```python
@dataclass
class ExecutionTrace:
    trace_id: str              # Unique trace ID
    root_step_id: str | None   # Entry point
    steps: dict[str, ExecutionStep]
    memory_pool: MemoryPool
    global_vars: dict[str, Any]
    start_time: datetime
    end_time: datetime | None
    user_query: str | None
    thread_id: str | None
    success: bool
```

## Usage

### Basic Tracing

```python
from omni.tracer import ExecutionTracer, StepType

# Create tracer
tracer = ExecutionTracer(
    trace_id="session_123",
    user_query="Analyze this code",
    thread_id="workflow_1"
)

# Start trace
tracer.start_trace()

# Start a step
step_id = tracer.start_step(
    name="plan",
    step_type=StepType.NODE_START,
    input_data={"query": "Analyze this code"}
)

# Record thinking
tracer.record_thinking(step_id, "First, I need to understand...")
tracer.record_thinking(step_id, "Then, I should identify patterns...")

# Save to memory
tracer.save_to_memory("plan_result", {"steps": [...]}, step_id)

# End step
tracer.end_step(step_id, output_data={"status": "completed"})

# End trace
trace = tracer.end_trace(success=True)

# Access results
print(f"Steps: {trace.step_count()}")
print(f"Thinking: {trace.thinking_step_count()}")
```

### LangGraph Integration

```python
from omni.langgraph.graph import OmniGraph
from omni.tracer import TracingCallbackHandler

# Create graph with tracing
graph = OmniGraph(enable_tracing=True)

# Run with trace
output, trace = await graph.run_with_trace(
    user_query="Fix the bug",
    thread_id="session_123"
)

print(f"Trace ID: {trace.trace_id}")
print(f"Steps: {trace.step_count()}")
print(f"Thinking steps: {trace.thinking_step_count()}")
```

### Manual Event Handling

```python
from omni.tracer import ExecutionTracer, TracingCallbackHandler

tracer = ExecutionTracer(trace_id="manual_trace")
handler = TracingCallbackHandler(tracer)

# Process LangGraph events manually
async for event in app.astream_events(initial_state, config=config):
    handler.handle_event(event)
```

### Callbacks

```python
from omni.tracer import TracingCallback, ExecutionTrace, ExecutionStep

class MyCallback(TracingCallback):
    async def on_step_start(self, trace: ExecutionTrace, step: ExecutionStep):
        print(f"Started: {step.name}")

    async def on_step_end(self, trace: ExecutionTrace, step: ExecutionStep):
        print(f"Finished: {step.name} ({step.duration_ms}ms)")

    async def on_thinking(self, trace: ExecutionTrace, step: ExecutionStep, content: str):
        print(f"Thinking: {content[:50]}...")

    async def on_retrieval(self, trace: ExecutionTrace, step: ExecutionStep, query: str, results):
        print(f"Retrieved {len(results)} results for: {query}")

    async def on_memory_save(self, trace: ExecutionTrace, var_name: str, value, source_step):
        print(f"Saved {var_name} from {source_step}")

    async def on_trace_end(self, trace: ExecutionTrace):
        print(f"Trace complete: {trace.step_count()} steps")

# Register callback
tracer.add_callback(MyCallback())
```

## MCP Tools

Available via the Agent MCP Server:

### run_agent_with_trace

Run agent with full execution tracing.

**Arguments:**

- `query` (required): User query to process
- `thread_id`: Session ID (auto-generated if not provided)
- `enable_thinking`: Capture LLM thinking (default: true)

**Returns:**

```json
{
  "result": "Final response",
  "success": true,
  "thinking": [{ "step": "plan", "type": "node_start", "reasoning": "..." }],
  "steps": [
    {
      "name": "plan",
      "type": "node_start",
      "status": "completed",
      "duration_ms": 123.4
    }
  ],
  "trace_summary": {
    "trace_id": "trace_...",
    "step_count": 5,
    "thinking_step_count": 2,
    "duration_ms": 500.0
  },
  "memory_pool": { "result": 1, "plan": 2 }
}
```

### get_execution_trace

Retrieve historical trace details.

**Arguments:**

- `trace_id` (required): Trace ID to retrieve
- `include_memory`: Include memory pool (default: false)
- `include_steps`: Include step details (default: true)

### list_traces

List available traces.

**Arguments:**

- `limit`: Maximum traces (default: 20)
- `offset`: Skip this many traces

### search_traces

Search traces by criteria.

**Arguments:**

- `query`: Search in queries and step names
- `step_type`: Filter by step type (e.g., "llm_start", "tool_end")
- `min_duration_ms` / `max_duration_ms`: Duration filter
- `success`: Filter by success status
- `limit`: Maximum results

### delete_trace

Delete a trace.

**Arguments:**

- `trace_id` (required): Trace ID to delete

## Storage

### TraceStorage

JSON file-based storage:

```python
from omni.tracer import TraceStorage, ExecutionTrace

storage = TraceStorage()  # Uses PRJ_DATA/traces

# Save trace
trace_id = storage.save(trace)

# Load trace
trace = storage.load(trace_id)

# List traces
traces = storage.list_traces(limit=100)

# Search
results = storage.search(
    query="bug fix",
    step_type=StepType.TOOL_START,
    min_duration_ms=100,
    success=True
)

# Cleanup old traces
deleted = storage.cleanup(keep_count=100)
```

### InMemoryTraceStorage

For testing:

```python
from omni.tracer import InMemoryTraceStorage

storage = InMemoryTraceStorage()
storage.save(trace)
# Does not persist to disk
```

## Integration with Existing Systems

### TraceCollector Integration

The new tracer integrates with the legacy TraceCollector for harvester compatibility:

```python
from omni.agent.core.evolution.tracer import TraceCollector
from omni.tracer import ExecutionTrace

collector = TraceCollector()

# Record detailed trace
trace = ExecutionTrace(trace_id="...", ...)
await collector.record_detailed(trace)
```

### OmniGraph Enhancement

```python
from omni.langgraph.graph import OmniGraph, get_graph

# Get traced graph
graph = get_graph(enable_tracing=True)

# Run with trace
output, trace = await graph.run_with_trace(
    user_query="Your request",
    thread_id="session"
)

# Get tracer
tracer = graph.get_tracer()
```

## Best Practices

### 1. Use for Debugging

When agent behavior is unexpected:

```python
graph = OmniGraph(enable_tracing=True)
output, trace = await graph.run_with_trace(...)
```

### 2. Memory Pool Naming

Use descriptive names for memory entries:

```python
tracer.save_to_memory("final_plan", plan, step_id)
tracer.save_to_memory("search_results", results, step_id)
```

### 3. Thinking Content

Capture LLM reasoning for transparency:

```python
# Automatic via TracingCallbackHandler
# Or manual:
tracer.record_thinking(step_id, "Analyzing the requirements...")
```

### 4. Trace Analysis

```python
# Get execution path
path = trace.get_execution_path()

# Get thinking steps
thinking = trace.get_thinking_steps()

# Memory history
history = trace.memory_pool.get_history("variable_name")
```

## Configuration

### Directory

Traces are stored in `PRJ_DATA/traces/` by default:

```python
from omni.tracer import TraceStorage

# Custom directory
storage = TraceStorage(storage_dir="/path/to/traces")
```

### Logging

Callback events are logged to `omni.tracer.*`:

```
2024-01-21 10:30:45 [INFO    ] omni.tracer.engine: tracer_initialized trace_id=...
2024-01-21 10:30:45 [DEBUG   ] omni.tracer.engine: step_started step_id=... name=plan
2024-01-21 10:30:46 [DEBUG   ] omni.tracer.engine: step_ended step_id=... duration_ms=123.4
2024-01-21 10:30:46 [INFO    ] omni.tracer.engine: trace_completed step_count=5
```

## API Reference

### Core Classes

| Class             | Description                        |
| ----------------- | ---------------------------------- |
| `ExecutionTracer` | Main tracer for tracking execution |
| `ExecutionTrace`  | Complete execution trace           |
| `ExecutionStep`   | Single step in trace               |
| `MemoryPool`      | Variable history tracking          |
| `StepType`        | Enum of step types                 |

### Callback Classes

| Class             | Description                 |
| ----------------- | --------------------------- |
| `TracingCallback` | Abstract base for callbacks |
| `LoggingCallback` | Built-in logging callback   |
| `CallbackManager` | Manages callback dispatch   |

### LangGraph Classes

| Class                    | Description             |
| ------------------------ | ----------------------- |
| `TracingCallbackHandler` | LangGraph event handler |

### Pipeline Classes

| Class                      | Description                                                                 |
| -------------------------- | --------------------------------------------------------------------------- |
| `PipelineConfig`           | YAML pipeline configuration                                                 |
| `PipelineRuntimeConfig`    | Runtime options (`checkpointer`, `invoker`, `retrieval`, `tracer`, `state`) |
| `PipelineExecutor`         | Executes pipelines with tracing                                             |
| `LangGraphPipelineBuilder` | Builds LangGraph from config                                                |
| `PipelineState`            | TypedDict for pipeline state                                                |

### Checkpoint Utilities

| Function                                                     | Description                                   |
| ------------------------------------------------------------ | --------------------------------------------- |
| `create_in_memory_checkpointer()`                            | Create LangGraph `MemorySaver` when available |
| `compile_workflow(workflow, checkpointer, use_memory_saver)` | Compile with optional checkpointer injection  |

### Storage Classes

| Class                  | Description              |
| ---------------------- | ------------------------ |
| `TraceStorage`         | File-based trace storage |
| `InMemoryTraceStorage` | In-memory for testing    |

### Convenience Functions

| Function                                         | Description                                     |
| ------------------------------------------------ | ----------------------------------------------- |
| `load_pipeline(path)`                            | Load PipelineConfig from YAML                   |
| `create_pipeline_executor(path, tracer)`         | Create PipelineExecutor                         |
| `create_langgraph_from_pipeline(config, tracer)` | Generate LangGraph app                          |
| `create_langgraph_from_yaml(path, ...)`          | Build LangGraph and apply YAML runtime defaults |

### Tracer Memory Output

| Method                                           | Description                                 |
| ------------------------------------------------ | ------------------------------------------- |
| `record_memory(var_name, value, step, metadata)` | Save memory with optional metadata envelope |
| `serialize_memory_pool()`                        | Export structured memory JSON payload       |
| `write_memory_output(output_dir, file_name)`     | Persist serialized memory payload to disk   |

### Callback Dispatch Controls

| Option/Method               | Description                                                        |
| --------------------------- | ------------------------------------------------------------------ |
| `callback_dispatch_mode`    | `inline` (default) or `background` for callback dispatch policy    |
| `drain_pending_callbacks()` | Await in-loop pending callback tasks for deterministic async tests |

### Retrieval Runtime Controls

| Option                              | Description                                                      |
| ----------------------------------- | ---------------------------------------------------------------- |
| `runtime.retrieval.default_backend` | Default backend for retrieval tools (`lance`, `hybrid`)          |
| `retrieval_default_backend`         | Function-level override that takes precedence over YAML defaults |

Retrieval tool set includes `retriever.search`, `retriever.hybrid_search`,
`retriever.index` and `retriever.get_stats`.

## File Locations

- **Source**: `packages/python/foundation/src/omni/tracer/`
- **Tests**: `packages/python/foundation/tests/unit/tracer/`
- **MCP Tools**: `packages/python/agent/src/omni/agent/mcp_server/tools/tracer.py`
