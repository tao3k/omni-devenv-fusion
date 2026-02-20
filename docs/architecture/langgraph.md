# LangGraph Architecture - Omni-Dev-Fusion

> Cognitive State Machine for Agent Workflows
> Last Updated: 2026-02-18

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
   - [GraphState](#graphstate)
   - [StateCheckpointer](#statecheckpointer)
4. [OmniGraph](#omnigraph)
   - [Plan Node](#plan-node)
   - [Execute Node](#execute-node)
   - [Reflect Node](#reflect-node)
5. [DynamicGraphBuilder](#dynamicgraphbuilder)
6. [CompiledGraph](#compiledgraph)
7. [GraphSkill](#graphskill)
8. [Usage Examples](#usage-examples)
9. [API Reference](#api-reference)

---

## Overview

The **LangGraph System** provides a cognitive state machine for Omni Agent, implementing the ReAct (Reasoning + Acting) pattern with LangGraph. It enables:

- **Plan → Execute → Reflect** cognitive cycle
- **Checkpoint persistence** across sessions
- **Dynamic graph construction** at runtime
- **Human-in-the-Loop** interrupt capabilities
- **Composable subgraphs** via GraphSkill

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│           OmniGraph                 │
│   ┌─────────┐  ┌─────────┐  ┌────┐ │
│   │  Plan   │─▶│ Execute │─▶│Refl│ │
│   └─────────┘  └─────────┘  └────┘ │
│         │            │         │    │
│         ▼            ▼         ▼    │
│      ┌──────────────────────────┐  │
│      │    StateCheckpointer     │◀─┘
│      │ (Rust CheckpointStore)   │
│      └──────────────────────────┘
└─────────────────────────────────────┘
```

---

## Architecture

```
packages/python/agent/src/omni/langgraph/
├── __init__.py              # Main exports
├── graph.py                 # OmniGraph cognitive state machine
├── state.py                 # GraphState + StateCheckpointer
├── orchestrator/
│   ├── __init__.py
│   ├── builder.py           # DynamicGraphBuilder
│   ├── compiled.py          # CompiledGraph wrapper
│   └── dispatch.py          # dispatch_graph_mode
└── skills/
    ├── __init__.py
    └── graph_skill.py       # GraphSkill base class
```

### Component Mapping

| Component                | Purpose                          | Location                      |
| ------------------------ | -------------------------------- | ----------------------------- |
| `OmniGraph`              | Cognitive state machine          | `omni.langgraph.graph`        |
| `GraphState`             | ReAct state definition           | `omni.langgraph.state`        |
| `StateCheckpointer`      | Rust LanceDB persistence         | `omni.langgraph.state`        |
| `DynamicGraphBuilder`    | Runtime graph construction       | `omni.langgraph.orchestrator` |
| `CompiledGraph`          | Graph execution wrapper          | `omni.langgraph.orchestrator` |
| `GraphSkill`             | Composable subgraph base         | `omni.langgraph.skills`       |
| `build_execution_levels` | Level-based shard scheduling     | `omni.langgraph.parallel`     |
| `run_parallel_levels`    | Parallel execution within levels | `omni.langgraph.parallel`     |

---

## Core Components

### GraphState

`GraphState` is a TypedDict defining the complete state for ReAct workflow:

```python
from omni.langgraph.state import GraphState

state: GraphState = {
    "messages": [{"role": "user", "content": "Fix the bug"}],  # Chat history
    "context_ids": ["ctx-001", "ctx-002"],                    # Memory references
    "current_plan": "Analyze error logs and fix",            # Current task plan
    "error_count": 0,                                         # Reflexion counter
    "workflow_state": {                                       # Custom workflow data
        "target_agent": "coder",
        "constraints": [],
    },
}
```

#### State Fields

| Field            | Type                   | Description                               |
| ---------------- | ---------------------- | ----------------------------------------- |
| `messages`       | `list[dict[str, Any]]` | Chat history with role/content            |
| `context_ids`    | `list[str]`            | Neural Matrix memory references           |
| `current_plan`   | `str`                  | Current task plan for multi-step          |
| `error_count`    | `int`                  | Error count for Reflexion self-correction |
| `workflow_state` | `dict[str, Any]`       | Additional workflow metadata              |

### StateCheckpointer

Rust-backed checkpoint system for state persistence:

```python
from omni.langgraph.state import get_checkpointer

checkpointer = get_checkpointer()

# Save checkpoint
checkpointer.put("session-123", state, metadata={"source": "user_query"})

# Load checkpoint
saved = checkpointer.get("session-123")
if saved:
    state = saved  # Resume from checkpoint
```

#### Checkpointer Features

- **Thread-safe** access via locks
- **Automatic history** with parent links
- **Configurable checkpoint intervals**
- **Efficient JSON storage**

---

## OmniGraph

`OmniGraph` implements the ReAct pattern with Plan → Execute → Reflect cycle:

```python
from omni.langgraph.graph import OmniGraph, get_graph

graph = OmniGraph(
    inference_client=llm_client,
    skill_runner=kernel,
    router=router,
)

result = await graph.run(
    user_query="Fix the bug in main.py",
    thread_id="session-123",
)
```

### Plan Node

The Plan node routes user queries to appropriate agents/workflows:

```python
async def plan_node(state: GraphState) -> Dict[str, Any]:
    # Use router or LLM to determine task approach
    route = await router.route(user_content)
    return {
        "current_plan": route.get("task_brief"),
        "workflow_state": {
            "target_agent": route.get("target_agent"),
            "route_confidence": route.get("confidence"),
        },
    }
```

### Execute Node

The Execute node runs the planned task:

```python
async def execute_node(state: GraphState) -> Dict[str, Any]:
    # Execute via skill runner or LLM
    result = await skill_runner.run(skill_name, command, args)
    return {
        "messages": [{"role": "assistant", "content": result}],
        "workflow_state": {**workflow, "last_result": {...}},
    }
```

### Reflect Node

The Reflect node evaluates execution quality:

```python
async def reflect_node(state: GraphState) -> Dict[str, Any]:
    # Use LLM to evaluate response
    review = await llm.evaluate(task=task, response=response)
    return {
        "workflow_state": {
            **workflow,
            "approved": review.approved,
            "audit_confidence": review.confidence,
        },
    }
```

### Flow Control

```python
def should_continue(state: GraphState) -> Literal["reflect", "execute", "__end__"]:
    """Decide next step after planning."""
    if not has_assistant_response:
        return "execute"  # First run, go to execute
    return "reflect"  # After execution, reflect

def audit_decision(state: GraphState) -> Literal["execute", "__end__"]:
    """Decide retry or end after reflection."""
    if workflow.get("approved"):
        return "__end__"  # Success, end
    if error_count >= max_retries:
        return "__end__"  # Max retries, give up
    return "execute"  # Retry
```

---

## DynamicGraphBuilder

Fluent API for constructing LangGraph graphs at runtime:

```python
from omni.langgraph.orchestrator import DynamicGraphBuilder

builder = DynamicGraphBuilder(skill_runner=kernel)

# Add skill nodes
builder.add_skill_node(
    "read_file", "filesystem", "read_file",
    fixed_args={"path": "main.py"},
)
builder.add_skill_node("analyze", "code_insight", "analyze")

# Add conditional edges
builder.add_conditional_edges(
    "analyze",
    lambda s: "fix" if s["needs_fix"] else END,
    {"fix": "fix_node", "__end__": END},
)

# Set entry and compile
builder.set_entry_point("read_file")
graph = builder.compile()
```

### Node Types

#### Skill Node

```python
builder.add_skill_node(
    node_name="read_file",
    skill_name="filesystem",
    command_name="read_file",
    fixed_args={"path": "main.py"},           # Static args
    state_input={"file_path": "path"},         # Dynamic from state
    state_output={"content": "file_content"},  # Map result to state
)
```

#### LLM Node

```python
builder.add_llm_node(
    node_name="analyze_code",
    prompt_template="Analyze this code: {{file_content}}",
    model="claude-sonnet",
    state_output="analysis_result",
)
```

#### Interrupt Node (Human-in-the-Loop)

```python
builder.add_interrupt_node(
    node_name="human_review",
    prompt="Please review the changes and approve",
    resume_key="approval",
)

# Compile with interrupt
graph = builder.compile(interrupt_before=["commit"])

# Resume from interrupt
for chunk in graph.stream(Command(resume="approved"), config):
    print(chunk)
```

#### Command Node

```python
async def conditional_commit(state):
    if state["approved"]:
        return Command(update={"status": "committed"}, goto=END)
    return Command(update={"status": "skipped"}, goto=END)

builder.add_command_node("execute_commit", conditional_commit)
```

### Edge Types

```python
# Direct edge
builder.add_edge("step1", "step2")

# Sequence (shortcut for multiple edges)
builder.add_sequence("step1", "step2", "step3", "step4")

# Conditional branching
builder.add_conditional_edges(
    source_node="analyze",
    condition_func=lambda s: "fix" if s["needs_fix"] else END,
    path_map={"fix": "fix_node", "__end__": END},
)
```

---

## CompiledGraph

Wrapper around compiled LangGraph with convenience methods:

```python
from omni.langgraph.orchestrator import CompiledGraph

# Configuration
config = graph.get_config(thread_id="workflow-123")

# State management
snapshot = graph.get_state()
if snapshot and snapshot.tasks:
    print(f"Waiting at: {snapshot.tasks[0].name}")

# Interrupt handling
if graph.has_interrupt():
    prompt = graph.get_interrupt_value()
    print(f"Interrupt: {prompt}")

# Resume from interrupt
command = graph.resume("approved", update={"note": "LGTM"})
async for chunk in graph.stream(command, thread_id="workflow-123"):
    print(chunk)
```

### Methods

| Method                             | Description                  |
| ---------------------------------- | ---------------------------- |
| `get_config(thread_id)`            | Get LangGraph config dict    |
| `get_state(thread_id)`             | Get current state snapshot   |
| `update_state(values, thread_id)`  | Update state for resume      |
| `has_interrupt(thread_id)`         | Check if paused at interrupt |
| `get_interrupt_value(thread_id)`   | Get interrupt prompt value   |
| `invoke(input_state, thread_id)`   | Synchronous invoke           |
| `ainvoke(input_state, thread_id)`  | Async invoke                 |
| `stream(input_state, thread_id)`   | Stream output                |
| `resume(value, thread_id, update)` | Create resume Command        |
| `goto(node, thread_id, update)`    | Create goto Command          |

---

## GraphSkill

Base class for composable subgraphs (Agent calling Agent):

```python
from omni.langgraph.skills import GraphSkill

class AnalyzeAndFix(GraphSkill):
    name = "analyze_and_fix"
    description = "Analyze code and fix issues"

    def build_graph(self, builder: DynamicGraphBuilder) -> None:
        builder.add_skill_node("analyze", "code_insight", "analyze")
        builder.add_skill_node("fix", "omni_edit", "apply_fix")
        builder.add_edge("analyze", "fix")
        builder.set_entry_point("analyze")

# Use the skill
skill = AnalyzeAndFix(skill_runner=kernel)
compiled = skill.compile()
result = await skill.run({"task": "Fix bug in main.py"})
```

### GraphSkill with Validation

```python
class MyGraphSkill(GraphSkill):
    name = "my_skill"
    description = "A skill with validation"

    input_schema = {
        "type": "object",
        "required": ["task"],
        "properties": {"task": {"type": "string"}},
    }

    output_schema = {
        "type": "object",
        "required": ["result"],
        "properties": {"result": {"type": "string"}},
    }

    def build_graph(self, builder):
        builder.add_skill_node("do_task", "skill1", "cmd1")
        builder.set_entry_point("do_task")

# Validate
skill = MyGraphSkill()
skill.validate_input({"task": "do something"})  # True/False
skill.validate_output({"result": "done"})        # True/False
```

---

## Usage Examples

### Basic Graph Execution

```python
from omni.langgraph.graph import get_graph

graph = get_graph()
result = await graph.run(
    user_query="Analyze the codebase structure",
    thread_id="session-001",
)

print(f"Success: {result.success}")
print(f"Content: {result.content}")
print(f"Confidence: {result.confidence}")
print(f"Iterations: {result.iterations}")
```

### Dynamic Graph with Human-in-the-Loop

```python
from omni.langgraph.orchestrator import DynamicGraphBuilder
from langgraph.types import Command

builder = DynamicGraphBuilder(skill_runner=kernel, checkpoint=True)

builder.add_skill_node("prepare", "git", "prepare_changes")
builder.add_interrupt_node("review", "Please review the commit message")
builder.add_skill_node("commit", "git", "commit")

builder.add_sequence("prepare", "review", "commit")
builder.set_entry_point("prepare")

# Compile with interrupt before commit
graph = builder.compile(interrupt_before=["commit"])

# Execute until interrupt
async for chunk in graph.stream(initial_state, config):
    print(chunk)

# Check for interrupt
if graph.has_interrupt(config):
    user_input = input(graph.get_interrupt_value(config))

    # Resume with approval
    command = graph.resume(user_input)
    async for chunk in graph.stream(command, config):
        print(chunk)
```

### Dispatch Graph Mode

```python
from omni.langgraph.orchestrator import dispatch_graph_mode

# In orchestrator
result = await dispatch_graph_mode(
    orchestrator=self,
    user_query="Fix the bug",
    history=[],
    context={"file": "main.py"},
)
```

---

## API Reference

### omni.langgraph

```python
from omni.langgraph import (
    # Graph
    OmniGraph,
    get_graph,
    reset_graph,
    plan_node,
    execute_node,
    reflect_node,
    GraphInput,
    GraphOutput,
    # State
    GraphState,
    StateCheckpointer,
    get_checkpointer,
    create_initial_state,
    merge_state,
    # Orchestrator
    DynamicGraphBuilder,
    NodeMetadata,
    CompiledGraph,
    dispatch_graph_mode,
)
```

### omni.langgraph.graph

| Function         | Description                  |
| ---------------- | ---------------------------- |
| `OmniGraph()`    | Create cognitive graph       |
| `get_graph()`    | Get global graph instance    |
| `reset_graph()`  | Reset global graph (testing) |
| `plan_node()`    | Planning node function       |
| `execute_node()` | Execution node function      |
| `reflect_node()` | Reflection node function     |

### omni.langgraph.state

| Function                 | Description                  |
| ------------------------ | ---------------------------- |
| `GraphState`             | TypedDict for ReAct state    |
| `StateCheckpointer`      | Rust checkpoint system       |
| `get_checkpointer()`     | Get global checkpointer      |
| `create_initial_state()` | Create initial state utility |
| `merge_state()`          | Merge state updates utility  |

### omni.langgraph.orchestrator

| Class                   | Description              |
| ----------------------- | ------------------------ |
| `DynamicGraphBuilder`   | Fluent graph builder     |
| `CompiledGraph`         | Compiled graph wrapper   |
| `dispatch_graph_mode()` | Orchestrator integration |

### omni.langgraph.skills

| Class                                 | Description                 |
| ------------------------------------- | --------------------------- |
| `GraphSkill`                          | Base class for graph skills |
| `create_graph_skill_from_blueprint()` | Factory from blueprint      |

---

## See Also

- [Router Architecture](router.md) - Semantic routing system
- [Kernel Architecture](kernel.md) - Core execution kernel
- [Skills Architecture](skills.md) - Skill system overview
- [MCP Server](mcp-server.md) - MCP server integration
