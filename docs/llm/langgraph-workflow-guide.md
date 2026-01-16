# LLM Guide: Writing LangGraph Workflows

> How to construct effective workflows using DynamicGraphBuilder. Read `langgraph-builder.md` first.

## Overview

When building workflows for agents, think in terms of:

1. **What operations are needed?** → Map to skill nodes
2. **What decisions need to be made?** → Map to function/command nodes
3. **Where should humans approve?** → Map to interrupt nodes
4. **What is the flow?** → Define edges between nodes

## Core Principle

```
Skill Commands (atomic operations) → Function Nodes (logic) → Edges (flow)
```

## Pattern 1: Linear Pipeline

Use when tasks must execute in sequence.

```python
builder = DynamicGraphBuilder(skill_manager)

# Each step builds on the previous
builder.add_skill_node("fetch", "filesystem", "read_file")
builder.add_skill_node("parse", "parser", "parse_code")
builder.add_skill_node("analyze", "code_insight", "analyze")
builder.add_skill_node("report", "writer", "write_report")

builder.add_sequence("fetch", "parse", "analyze", "report")
builder.set_entry_point("fetch")
```

**When to use:**

- File read → process → write
- API call → transform → store
- Any sequential dependency

## Pattern 2: Conditional Branching

Use when different paths based on state.

```python
def route_by_result(state):
    if state.get("has_errors"):
        return "error_handler"
    elif state.get("needs_review"):
        return "human_review"
    return "proceed"

builder.add_conditional_edges(
    "analyze",
    route_by_result,
    {
        "error_handler": "error_handler",
        "human_review": "human_review",
        "proceed": "execute"
    }
)
```

**Key insight:** The routing function receives the full state and returns a key that maps to a node.

## Pattern 3: Human-in-the-Loop

Use for approval checkpoints on destructive/important operations.

```python
# Always checkpoint when using interrupts
builder = DynamicGraphBuilder(skill_manager, checkpoint=True)

builder.add_skill_node("prepare", "git", "stage_all")
builder.add_interrupt_node(
    "review",
    "Please review these changes before committing",
    resume_key="approval"
)
builder.add_skill_node("commit", "git", "commit")

builder.add_sequence("prepare", "review", "commit")
```

**How to resume:**

```python
# When interrupted, user provides approval
command = graph.resume("approved")  # or "rejected"
async for chunk in graph.stream(command, config):
    print(chunk)
```

## Pattern 4: Parallel Execution (Fan-out/Fan-in)

Use when multiple independent tasks can run concurrently.

```python
def spawn_analysis(state):
    files = state.get("files_to_analyze", [])
    return [
        Send("analyze_file", {"path": f, "result": None})
        for f in files
    ]

builder.add_skill_node("list_files", "filesystem", "list_files")
builder.add_skill_node("analyze_file", "code_insight", "analyze")
builder.add_function_node("aggregate", aggregate_results)

builder.add_send_branch("list_files", ["analyze_file"], spawn_analysis)
builder.add_edge("analyze_file", "aggregate")
```

**State schema with reducer:**

```python
from agent.core.orchestrator.state_utils import create_reducer_state_schema
import operator

# Allows parallel nodes to append to results
state_schema = create_reducer_state_schema(
    GraphState,
    {"results": operator.add}
)
```

## Pattern 5: Dynamic Routing with Command

Use when you need to:

- Jump to any node (not just predefined edges)
- Update state before continuing
- Handle complex conditional logic

```python
from langgraph.types import Command

async def intelligent_router(state):
    # Analyze state and decide
    if state.get("security_risk") > 0.8:
        return Command(update={"alert": "high"}, goto="security_review")
    elif state.get("complexity") == "high":
        return Command(update={"priority": "normal"}, goto="detailed_analysis")
    else:
        return Command(update={"priority": "high"}, goto="quick_action")

builder.add_command_node("router", intelligent_router)
```

## Pattern 6: Retry with State Update

Use command nodes to retry failed operations with updated state.

```python
async def retry_logic(state):
    attempts = state.get("retry_attempts", 0)
    if attempts >= 3:
        return Command(update={"status": "failed"}, goto=END)

    if state.get("last_error"):
        return Command(
            update={"retry_attempts": attempts + 1},
            goto="retry_operation"
        )
    return Command(update={"status": "success"}, goto="next")

builder.add_command_node("handle_result", retry_logic)
```

## State Design

### Good State Design

```python
# Input state
{"root_dir": "/project"}

# After fetch
{"root_dir": "/project", "file_content": "...", "scratchpad": [...]}

# After analyze
{"root_content": "...", "analysis": {...}, "scratchpad": [..., {...}]}
```

### Bad State Design

```python
# Don't do this - too many intermediate variables
{"temp1": "...", "temp2": "...", "temp3": "...", "final_result": "..."}

# Instead - use scratchpad for debugging, focus state on outputs
{"result": "...", "scratchpad": [{"temp": "..."}]}
```

### State Output Mapping

```python
# Direct mapping - skill output key -> state key
builder.add_skill_node(
    "read",
    "filesystem",
    "read_file",
    state_output={"content": "file_content"}  # output.content -> state.file_content
)

# Multiple mappings
state_output={
    "files": "staged_files",
    "diff": "diff_content",
    "issues": "security_issues"
}
```

## Node Naming Convention

| Pattern     | Example                            | Use For              |
| ----------- | ---------------------------------- | -------------------- |
| `verb_noun` | `fetch_file`, `analyze_code`       | Skill nodes          |
| `verb_noun` | `check_status`, `validate_input`   | Function nodes       |
| `verb_noun` | `review_changes`, `approve_commit` | Interrupt nodes      |
| `verb_noun` | `route_request`, `decide_action`   | Command/router nodes |

## Common Mistakes to Avoid

### Mistake 1: Forgetting Entry Point

```python
# Wrong - graph has no entry point
builder.add_skill_node("a", "skill", "cmd")
builder.add_skill_node("b", "skill", "cmd")
builder.add_edge("a", "b")
# graph.compile() will fail!

# Correct
builder.set_entry_point("a")
```

### Mistake 2: Missing State Schema for Parallel Writes

```python
# Wrong - parallel nodes overwrite each other
builder.add_skill_node("task1", "skill", "cmd")  # Writes to "results"
builder.add_skill_node("task2", "skill", "cmd")  # Overwrites "results"!

# Correct - use reducer
from agent.core.orchestrator.state_utils import create_reducer_state_schema
import operator

schema = create_reducer_state_schema(GraphState, {"results": operator.add})
builder = DynamicGraphBuilder(skill_manager, state_schema=schema)
```

### Mistake 3: No Interrupt for Destructive Operations

```python
# Wrong - commits directly
builder.add_skill_node("commit", "git", "commit")

# Correct - pauses for approval
builder.add_interrupt_node("approve", "Approve this commit?")
builder.add_sequence("approve", "commit")
graph.compile(interrupt_before=["commit"])
```

### Mistake 4: Complex Logic in Routing Function

```python
# Wrong - too complex
def route(state):
    if (state.get("a") and not state.get("b")) or \
       (state.get("c") and state.get("d")) or \
       state.get("e") == "special":
        return "path1"
    # ... 50 more lines

# Correct - use command node with async function
async def smart_router(state):
    # Can use async, call other skills, etc.
    result = await analyze_state(state)
    return Command(goto=result["next_node"])
```

## Complete Example: Smart Commit Workflow

```python
from agent.core.orchestrator.builder import DynamicGraphBuilder
from langgraph.graph import END

builder = DynamicGraphBuilder(skill_manager, checkpoint=True)

# === Stage 1: Prepare ===
builder.add_skill_node(
    "prepare",
    "git",
    "stage_and_scan",
    state_output={
        "staged_files": "staged_files",
        "security_issues": "security_issues",
        "diff": "diff_content",
    }
)

# === Stage 2: Route based on scan ===
async def route_prepare(state):
    if state.get("security_issues"):
        return {"status": "security_violation"}
    if not state.get("staged_files"):
        return {"status": "empty"}
    return {"status": "prepared"}

builder.add_function_node("route_prepare", route_prepare)

# === Stage 3: Format for human ===
async def format_review(state):
    status = state.get("status")
    if status == "prepared":
        count = len(state.get("staged_files", []))
        return {"review_card": f"**{count} files ready to commit**"}
    return {"review_card": f"**Status**: {status}"}

builder.add_function_node("format_review", format_review)

# === Stage 4: Human interrupt ===
builder.add_interrupt_node(
    "approve",
    "Please review and approve the commit",
    resume_key="approval"
)

# === Stage 5: Commit (after approval) ===
builder.add_skill_node("commit", "git", "commit")

# === Edges ===
builder.add_sequence("prepare", "route_prepare", "format_review", "approve")
builder.add_conditional_edges(
    "route_prepare",
    lambda s: "approve" if s.get("status") == "prepared" else END,
    {"approve": "approve", END: END}
)
builder.add_edge("commit", END)
builder.set_entry_point("prepare")

# === Compile ===
graph = builder.compile(interrupt_before=["commit"])
```

## Decision Flowchart

```
Start building a workflow →

What type of operation?
├── Atomic skill command? → Use add_skill_node()
├── Custom logic? → Use add_function_node()
├── Need human approval? → Add interrupt_node()
└── Dynamic routing? → Use add_command_node()

What's the flow?
├── One after another? → add_sequence()
├── Branch based on result? → add_conditional_edges()
└── Run in parallel? → add_send_branch()

Need state persistence?
├── Yes (long workflow) → checkpoint=True
└── No (simple) → checkpoint=False

Need human approval?
├── Yes → compile(interrupt_before=["node"])
└── No → compile()
```

## Quick Reference

| Need            | Method                    |
| --------------- | ------------------------- |
| Execute skill   | `add_skill_node()`        |
| Custom logic    | `add_function_node()`     |
| Pause for human | `add_interrupt_node()`    |
| Dynamic routing | `add_command_node()`      |
| Connect nodes   | `add_edge()`              |
| Linear flow     | `add_sequence()`          |
| Branching       | `add_conditional_edges()` |
| Parallel        | `add_send_branch()`       |
| Start point     | `set_entry_point()`       |
| Build graph     | `compile()`               |
| Show graph      | `visualize()`             |
