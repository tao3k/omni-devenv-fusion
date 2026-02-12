# LLM Guide: Writing LangGraph Workflows

> Omni-Dev-Fusion System Layering - Workflow Implementation Guide

## Overview

This guide teaches LLMs how to write **LangGraph workflows** using the standard Omni-Dev-Fusion pattern. All workflows should:

1. Use `StateGraph` for graph construction
2. Use `RustCheckpointSaver` for state persistence (LanceDB)
3. Use `get_logger()` for observability
4. Export via `@skill_command` decorator

## Standard Pattern

```python
"""
skill/scripts/workflow.py - Workflow Name

Uses unified Rust LanceDB CheckpointStore for persistent state:
- State persists across skill reloads
- Supports workflow_id-based retrieval
- Centralized at path from settings (default: .data/checkpoints.lance)

Workflow Type: my_workflow
"""

from typing import Any
from langgraph.graph import END, StateGraph

from omni.core.skills.state import GraphState
from omni.foundation.checkpoint import load_workflow_state, save_workflow_state
from omni.foundation.config.logging import get_logger
from omni.langgraph.checkpoint.saver import RustCheckpointSaver

logger = get_logger("skill.workflow")

# Import Rust checkpoint saver
try:
    from omni.langgraph.checkpoint.saver import RustCheckpointSaver as _RustCheckpointSaver
    _CHECKPOINT_AVAILABLE = True
    logger.info("RustCheckpointSaver imported successfully")
except ImportError as e:
    _CHECKPOINT_AVAILABLE = False
    _RustCheckpointSaver = None  # type: ignore
    logger.warning(f"RustCheckpointSaver import failed: {e}")

# Workflow type identifier for checkpoint table
_WORKFLOW_TYPE = "my_workflow"


# =============================================================================
# State Definition
# =============================================================================

class MyWorkflowState(TypedDict):
    """State for My Workflow."""
    request: str              # User's input
    result: str               # Processing result
    steps: int                # Step counter
    messages: Annotated[list[dict], operator.add]  # Message history
    error: str | None         # Error state


# =============================================================================
# Node Functions
# =============================================================================

async def node_process(state: MyWorkflowState) -> dict:
    """Process input and return result."""
    logger.info("[Graph] Processing...", request=state["request"])

    try:
        # ... processing logic ...
        return {"result": "...", "steps": state["steps"] + 1}
    except Exception as e:
        logger.error("[Graph] Processing failed", error=str(e))
        return {"error": f"Failed: {e}", "steps": state["steps"] + 1}


# =============================================================================
# Router Functions
# =============================================================================

def router_check(state: MyWorkflowState) -> str:
    """Route based on state."""
    if state.get("error"):
        return "error_handler"
    return "next_node"


# =============================================================================
# Graph Construction
# =============================================================================

def _build_workflow() -> StateGraph:
    """Build the workflow StateGraph."""
    workflow = StateGraph(MyWorkflowState)

    # Add nodes
    workflow.add_node("process", node_process)

    # Set entry point
    workflow.set_entry_point("process")

    # Add edges
    workflow.add_edge("process", END)

    return workflow


# =============================================================================
# LangGraph Compilation with Rust Checkpoint
# =============================================================================

# Compile with Rust checkpoint for state persistence (LanceDB)
if _CHECKPOINT_AVAILABLE and _RustCheckpointSaver:
    try:
        _memory = _RustCheckpointSaver()
        logger.info(f"RustCheckpointSaver initialized: {_memory}")
    except Exception as e:
        logger.error(f"RustCheckpointSaver init failed: {e}")
        _memory = None
else:
    _memory = None
    logger.warning("Checkpointer not available, using None")

_app = _build_workflow().compile(checkpointer=_memory)
logger.info(f"Compiled workflow checkpointer: {_app.checkpointer}")


# =============================================================================
# Skill Command (Entry Point)
# =============================================================================

from omni.foundation.api.decorators import skill_command


@skill_command(
    name="my_workflow",
    category="workflow",
    description="My workflow description",
)
async def my_workflow(request: str = "") -> str:
    """Execute the workflow."""
    logger.info("Running workflow", request=request)

    initial_state = MyWorkflowState(
        request=request,
        result="",
        steps=0,
        messages=[],
        error=None,
    )

    try:
        config = {"configurable": {"thread_id": f"workflow-{hash(request) % 10000}"}}
        result = await _app.ainvoke(initial_state, config=config)

        # Save final state
        save_workflow_state(_WORKFLOW_TYPE, config["configurable"]["thread_id"], dict(result))

        return result.get("result", "Done")
    except Exception as e:
        logger.error("Workflow failed", error=str(e))
        return f"Error: {e}"


__all__ = ["my_workflow", "MyWorkflowState"]
```

## Key Components

### 1. Logger

```python
from omni.foundation.config.logging import get_logger

logger = get_logger("skill.workflow")
```

**Always use logger** - Never `print()` or `console.log()`.

### 2. RustCheckpointSaver

```python
try:
    from omni.langgraph.checkpoint.saver import RustCheckpointSaver as _RustCheckpointSaver
    _CHECKPOINT_AVAILABLE = True
except ImportError as e:
    _CHECKPOINT_AVAILABLE = False
    _RustCheckpointSaver = None
    logger.warning(f"RustCheckpointSaver import failed: {e}")
```

**Import with alias** (`_RustCheckpointSaver`) to avoid shadowing.

### 3. Checkpoint Compilation

```python
if _CHECKPOINT_AVAILABLE and _RustCheckpointSaver:
    try:
        _memory = _RustCheckpointSaver()
    except Exception as e:
        logger.error(f"RustCheckpointSaver init failed: {e}")
        _memory = None
else:
    _memory = None

_app = _build_workflow().compile(checkpointer=_memory)
```

**Compile at module level** - Not inside the skill command.

### 4. State Persistence

```python
from omni.foundation.checkpoint import load_workflow_state, save_workflow_state

# Save state
save_workflow_state(_WORKFLOW_TYPE, workflow_id, dict(state))

# Load state
saved = load_workflow_state(_WORKFLOW_TYPE, workflow_id)
```

Use `omni.foundation.checkpoint` - not direct SQLite or custom stores.

### 5. TypedDict State

```python
from typing import TypedDict, Annotated, Any
import operator

class MyState(TypedDict):
    request: str
    result: str
    steps: int
    messages: Annotated[list[dict], operator.add]  # Append reducer
    error: str | None
```

**Use TypedDict** for type safety and LangGraph compatibility.

## Pattern 1: Linear Pipeline

```python
def create_pipeline() -> StateGraph:
    workflow = StateGraph(MyState)

    workflow.add_node("fetch", node_fetch)
    workflow.add_node("process", node_process)
    workflow.add_node("save", node_save)

    workflow.set_entry_point("fetch")
    workflow.add_edge("fetch", "process")
    workflow.add_edge("process", "save")
    workflow.add_edge("save", END)

    return workflow
```

## Pattern 2: Conditional Branching

```python
def router_decide(state: MyState) -> str:
    if state.get("has_errors"):
        return "error_handler"
    elif state.get("needs_approval"):
        return "approval_node"
    return "continue"

workflow.add_conditional_edges(
    "process",
    router_decide,
    {
        "error_handler": "error_handler",
        "approval_node": "approval_node",
        "continue": "save",
    },
)
```

## Pattern 3: Loop (for processing multiple items)

```python
def router_has_items(state: MyState) -> str:
    if state.get("items_remaining"):
        return "process_item"
    return "complete"

workflow.add_conditional_edges(
    "process_item",
    router_has_items,
    {"process_item": "process_item", "complete": "complete"},
)
```

## Pattern 4: Multi-Stage Workflow

```python
async def node_setup(state: ResearchState) -> dict:
    """Setup: Initialize resources."""
    return {"repo_path": "...", "steps": 0}

async def node_process(state: ResearchState) -> dict:
    """Process: Do the work."""
    return {"result": "...", "steps": state["steps"] + 1}

async def node_finalize(state: ResearchState) -> dict:
    """Finalize: Clean up and return."""
    return {"output": "...", "steps": state["steps"] + 1}

def create_research_graph() -> StateGraph:
    workflow = StateGraph(ResearchState)

    workflow.add_node("setup", node_setup)
    workflow.add_node("process", node_process)
    workflow.add_node("finalize", node_finalize)

    workflow.set_entry_point("setup")
    workflow.add_edge("setup", "process")
    workflow.add_edge("process", "finalize")
    workflow.add_edge("finalize", END)

    return workflow
```

## Complete Example: Research Workflow

See `assets/skills/researcher/scripts/research_graph.py` for a production example:

```python
# Key patterns from research_graph.py:
# 1. Uses _WORKFLOW_TYPE = "research"
# 2. Implements _build_system_prompt() with orchestrator
# 3. Caches system_prompt in state for loop efficiency
# 4. Uses load_workflow_state/save_workflow_state for persistence
# 5. Compiles graph at module level with RustCheckpointSaver
```

## Complete Example: Smart Commit Workflow

See `assets/skills/git/scripts/smart_commit_workflow.py` for a production example:

```python
# Key patterns from smart_commit_workflow.py:
# 1. Uses _WORKFLOW_TYPE = "smart_commit"
# 2. Implements action-based routing (start/approve/reject/status)
# 3. Uses workflow_id for state persistence
# 4. Compiles graph at module level with RustCheckpointSaver
# 5. Exports via @skill_command decorator
```

## Decision Flowchart

```
Start building a workflow →

What type of workflow?
├── Single action? → Simple StateGraph with 1-2 nodes
├── Multi-phase? → Linear pipeline (setup → process → finalize)
├── Conditional? → Use add_conditional_edges with router
└── Loop? → Use conditional edge back to processing node

Need state persistence?
├── Yes → Use RustCheckpointSaver + checkpoint module
└── No → Use None for checkpointer

Need logging?
├── Yes → Use get_logger("skill.workflow")
└── No → Don't (always use logger)

Need to handle errors?
├── Yes → Add error node + conditional edge from process
└── No → Simple edge to END

Export as skill command?
├── Yes → Use @skill_command decorator
└── No → Export function directly
```

## Quick Reference

| Need             | Pattern                                                                    |
| ---------------- | -------------------------------------------------------------------------- |
| Logger           | `logger = get_logger("skill.workflow")`                                    |
| State definition | `class MyState(TypedDict): ...`                                            |
| Build graph      | `workflow = StateGraph(MyState)`                                           |
| Add node         | `workflow.add_node("name", node_function)`                                 |
| Set entry        | `workflow.set_entry_point("first")`                                        |
| Linear edge      | `workflow.add_edge("a", "b")`                                              |
| Conditional      | `workflow.add_conditional_edges("node", router, {...})`                    |
| Checkpointer     | `RustCheckpointSaver()` or `None`                                          |
| Compile          | `_app = workflow.compile(checkpointer=_memory)`                            |
| Execute          | `await _app.ainvoke(state, config={"configurable": {"thread_id": "..."}})` |
| Save state       | `save_workflow_state(type, id, state)`                                     |
| Load state       | `load_workflow_state(type, id)`                                            |
| Skill export     | `@skill_command(name="...", category="...")`                               |

## Common Mistakes to Avoid

### ❌ Don't: Import RustCheckpointSaver directly

```python
from omni.langgraph.checkpoint.saver import RustCheckpointSaver
_memory = RustCheckpointSaver()  # Shadowing risk!
```

### ✅ Do: Import with alias

```python
from omni.langgraph.checkpoint.saver import RustCheckpointSaver as _RustCheckpointSaver
_memory = _RustCheckpointSaver()
```

### ❌ Don't: Compile inside skill command

```python
@skill_command
async def my_workflow():
    workflow = StateGraph(State)
    app = workflow.compile()  # Recompile every call!
```

### ✅ Do: Compile at module level

```python
# At module level
_app = _build_workflow().compile(checkpointer=_memory)

@skill_command
async def my_workflow():
    await _app.ainvoke(state)  # Reuse compiled graph
```

### ❌ Don't: Use print() for debugging

```python
print(f"State: {state}")  # Won't show in logs
```

### ✅ Do: Use logger

```python
logger.info("Processing state", state=dict(state))
```

### ❌ Don't: Skip error handling

```python
async def node_process(state):
    return {"result": risky_operation()}  # May crash graph
```

### ✅ Do: Handle errors gracefully

```python
async def node_process(state):
    try:
        return {"result": risky_operation()}
    except Exception as e:
        logger.error("Failed", error=str(e))
        return {"error": str(e), "steps": state["steps"] + 1}
```

## File Structure

```
skills/skill_name/scripts/
├── __init__.py              # Package marker
├── workflow.py              # Main workflow (StateGraph + RustCheckpointSaver)
├── node_functions.py        # Node implementations (optional)
├── state.py                 # State definitions (optional)
└── rendering.py             # Jinja2 templates (optional)

skills/skill_name/tests/
└── test_workflow.py         # Tests
```

## Testing

```python
# test_workflow.py
import pytest

class TestWorkflow:
    def test_workflow_imports(self):
        from skill.scripts.workflow import my_workflow, _app
        assert my_workflow is not None
        assert _app is not None

    def test_graph_compiled(self):
        from skill.scripts.workflow import _app
        assert _app.checkpointer is not None  # Or None if unavailable

    @pytest.mark.asyncio
    async def test_workflow_runs(self):
        from skill.scripts.workflow import my_workflow
        result = await my_workflow(request="test")
        assert "result" in result or "error" in result
```
