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
builder.add_skill_node("analyze", "code_tools", "find_tools")
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
builder.add_skill_node("analyze_file", "code_tools", "find_tools")
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

## Pattern 7: SQLite State Persistence (Workflow Tracking)

Use when you need state to persist across skill module reloads.

```python
import sqlite3
import uuid
from pathlib import Path

_DB_PATH = Path.home() / ".cache" / "project" / "workflows.db"

def _get_state_db() -> sqlite3.Connection:
    """Get or create SQLite connection for workflow state."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_states (
            workflow_id TEXT PRIMARY KEY,
            state TEXT,
            updated_at REAL
        )
    """)
    return conn

def _save_workflow_state(workflow_id: str, state: dict) -> None:
    """Save workflow state to SQLite."""
    import json
    conn = _get_state_db()
    state_json = json.dumps(state)
    updated_at = __import__("time").time()
    conn.execute(
        "REPLACE INTO workflow_states (workflow_id, state, updated_at) VALUES (?, ?, ?)",
        (workflow_id, state_json, updated_at)
    )
    conn.commit()
    conn.close()

def _get_workflow_state(workflow_id: str) -> Optional[dict]:
    """Retrieve workflow state from SQLite."""
    import json
    conn = _get_state_db()
    cursor = conn.execute(
        "SELECT state FROM workflow_states WHERE workflow_id = ?",
        (workflow_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None
```

**Usage in workflow:**

```python
async def _start_workflow_async() -> Dict[str, Any]:
    wf_id = str(uuid.uuid4())[:8]
    state = {"workflow_id": wf_id, "status": "prepared"}
    _save_workflow_state(wf_id, state)
    return state

async def _get_status_async(workflow_id: str) -> Optional[Dict[str, Any]]:
    return _get_workflow_state(workflow_id)
```

## Pattern 8: Template-Based Output Rendering

Use Jinja2 templates for consistent, structured output formatting.

**Template file** (`skills/git/templates/prepare_result.j2`):

```jinja2
### Commit Analysis

| Field           | Value               |
| --------------- | ------------------- |
| **Type**        | `{{ commit_type }}` |
| **Scope**       | `{{ commit_scope }}`{% if scope_warning %} ⚠️{% endif %} |

#### Files to commit ({{ staged_file_count }})

{%- for f in staged_files[:20] %}
- `{{ f }}`
{%- endfor %}

#### Message

{{ message }}

---
*Generated with Claude Code*
```

**Rendering function** (`skills/git/scripts/rendering.py`):

```python
from functools import lru_cache
import jinja2
from common.skills_path import SKILLS_DIR
from common.config.settings import get_setting

@lru_cache(maxsize=1)
def _get_jinja_env() -> jinja2.Environment:
    search_paths = [
        SKILLS_DIR("git", path="templates"),  # Skill default
        get_setting("assets.templates_dir") / "git",  # User override
    ]
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader([p for p in search_paths if p.exists()]),
        autoescape=False,
        trim_blocks=True,
    )

def render_template(template_name: str, **context) -> str:
    """Render any Jinja2 template with cascading support."""
    env = _get_jinja_env()
    template = env.get_template(template_name)
    return template.render(**context)
```

**Usage in workflow:**

```python
from .rendering import render_template

async def start_commit_workflow() -> str:
    return render_template(
        "prepare_result.j2",
        commit_type="feat",
        commit_scope="git-workflow",
        commit_description="Smart Commit workflow",
        has_staged=True,
        staged_files=["file1.py", "file2.py"],
        staged_file_count=2,
        message="Ready to commit"
    )
```

**Cascading template pattern:**

```
User Override: assets/templates/git/prepare_result.j2  (highest priority)
Skill Default: assets/skills/git/templates/prepare_result.j2  (fallback)
```

## Pattern 9: Scope Validation with cog.toml

Validate commit scopes against project configuration.

```python
from pathlib import Path
import re

def _get_cog_scopes(project_root: Path) -> List[str]:
    """Read allowed scopes from cog.toml."""
    cog_path = project_root / "cog.toml"
    if cog_path.exists():
        content = cog_path.read_text()
        match = re.search(r"scopes\s*=\s*\[([^\]]+)\]", content, re.DOTALL)
        if match:
            scopes_str = match.group(1)
            return re.findall(r'"([^"]+)"', scopes_str)
    return []

def _validate_scope(scope: str, valid_scopes: List[str]) -> tuple:
    """Validate scope and suggest fixes."""
    scope_lower = scope.lower()
    if scope_lower in [s.lower() for s in valid_scopes]:
        return True, scope, []

    # Find close matches
    from difflib import get_close_matches
    matches = get_close_matches(scope_lower, [s.lower() for s in valid_scopes], n=1, cutoff=0.6)
    if matches:
        original_casing = valid_scopes[[s.lower() for s in valid_scopes].index(matches[0])]
        return True, original_casing, [f"Auto-fixed to '{original_casing}'"]
    return False, scope, [f"Scope not in cog.toml. Allowed: {', '.join(valid_scopes)}"]

# Usage
valid_scopes = _get_cog_scopes(root)
is_valid, fixed_scope, warnings = _validate_scope("git-workflow", valid_scopes)
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

## Complete Example: Template-Based Smart Commit (No LangGraph)

For simpler workflows, use direct template rendering with SQLite state:

```python
# skills/git/scripts/graph_workflow.py
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

from .rendering import render_template, render_commit_message
from .prepare import _get_cog_scopes

_DB_PATH = Path.home() / ".cache" / "omni-dev-fusion" / "workflows.db"

def _get_state_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_states (
            workflow_id TEXT PRIMARY KEY,
            state TEXT,
            updated_at REAL
        )
    """)
    return conn

def _save_workflow_state(workflow_id: str, state: Dict[str, Any]) -> None:
    import json
    conn = _get_state_db()
    conn.execute(
        "REPLACE INTO workflow_states VALUES (?, ?, ?)",
        (workflow_id, json.dumps(state), __import__("time").time())
    )
    conn.commit()
    conn.close()

def _get_workflow_state(workflow_id: str) -> Optional[Dict[str, Any]]:
    import json
    conn = _get_state_db()
    row = conn.execute(
        "SELECT state FROM workflow_states WHERE workflow_id = ?",
        (workflow_id,)
    ).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None

async def _start_smart_commit_async() -> Dict[str, Any]:
    from agent.core.skill_runtime import get_skill_context
    context = get_skill_context()
    wf_id = str(uuid.uuid4())[:8]

    # Run stage_and_scan
    result = await context.run("git", "stage_and_scan", {})
    staged_files = result.get("staged_files", [])
    diff = result.get("diff", "")

    # Scope validation
    valid_scopes = _get_cog_scopes(Path("."))
    scope_warning = f"Valid scopes: {', '.join(valid_scopes)}" if valid_scopes else ""

    state = {
        "workflow_id": wf_id,
        "staged_files": staged_files,
        "diff_content": diff,
        "status": "prepared" if staged_files else "empty",
        "scope_warning": scope_warning,
    }
    _save_workflow_state(wf_id, state)
    return state

async def _approve_smart_commit_async(message: str, workflow_id: str) -> Dict[str, Any]:
    from agent.core.skill_runtime import get_skill_context
    context = get_skill_context()

    # Execute commit
    result = await context.run("git", "git_commit", {"message": message})

    _save_workflow_state(workflow_id, {"status": "approved", "final_message": message})

    return {"status": "committed", "final_message": message}

# Skill command with template rendering
from agent.skills.decorators import skill_command

@skill_command(name="smart_commit", category="workflow")
async def smart_commit(action: str = "start", workflow_id: str = "", message: str = "") -> str:
    if action == "start":
        result = await _start_smart_commit_async()
        return render_template(
            "prepare_result.j2",
            commit_type="feat",
            commit_scope="git-workflow",
            commit_description="Smart Commit workflow",
            has_staged=bool(result["staged_files"]),
            staged_files=result["staged_files"],
            staged_file_count=len(result["staged_files"]),
            scope_warning=result.get("scope_warning", ""),
            lefthook_report="",
            message=f"**Workflow ID**: `{result['workflow_id']}`\n\nReady to approve.",
        )
    elif action == "approve":
        result = await _approve_smart_commit_async(message, workflow_id)
        return render_commit_message(
            subject=message,
            status="committed",
            workflow_id=workflow_id,
        )
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

Need structured output?
├── Yes → Use Jinja2 templates with render_template()
└── No → Return raw string

Need cross-reload persistence?
├── Yes → Use SQLite state store
└── No → Use in-memory dict
```

## Quick Reference

| Need               | Method/Pattern                                     |
| ------------------ | -------------------------------------------------- |
| Execute skill      | `add_skill_node()`                                 |
| Custom logic       | `add_function_node()`                              |
| Pause for human    | `add_interrupt_node()`                             |
| Dynamic routing    | `add_command_node()`                               |
| Connect nodes      | `add_edge()`                                       |
| Linear flow        | `add_sequence()`                                   |
| Branching          | `add_conditional_edges()`                          |
| Parallel           | `add_send_branch()`                                |
| Start point        | `set_entry_point()`                                |
| Build graph        | `compile()`                                        |
| Show graph         | `visualize()`                                      |
| Template rendering | `render_template()`                                |
| Commit message     | `render_commit_message()`                          |
| SQLite persistence | `_save_workflow_state()` / `_get_workflow_state()` |
| Scope validation   | `_get_cog_scopes()` / `_validate_scope()`          |
