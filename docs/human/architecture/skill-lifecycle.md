# Skill Lifecycle

> **Status**: Active | **Version**: v1.0 | **Date**: 2024-XX-XX

## Overview

This document describes the lifecycle of a "Living Skill" - an Intelligent Microservice Unit using LangGraph for orchestration.

## Omni Skill Standard (OSS) - Directory Structure

```
agent/skills/<skill_name>/
├── 📄 SKILL.md           # [IDENTITY]  Metadata & configuration
├── 🛠️ scripts/           # [HANDS]     Atomic commands (stateless, side-effects only)
├── 🧠 workflow.py        # [BRAIN]     Workflow logic (LangGraph graph)
├── 💾 state.py           # [MEMORY]    State definition (Pydantic models)
├── 📘 guide.md           # [INTERFACE] Usage docs (RAG/prompt context)
└── 📝 prompts.md         # [PERSONA]   Routing rules & prompt injection
```

### File Responsibilities

| File           | Role      | Intelligence | Purpose                             |
| -------------- | --------- | ------------ | ----------------------------------- |
| `SKILL.md`     | Identity  | ❌ None      | Metadata, dependencies, entry_point |
| `scripts/*.py` | Hands     | 🔵 Low       | Atomic actions, side-effects only   |
| `workflow.py`  | Brain     | 🔴 High      | Orchestration, LangGraph graph      |
| `state.py`     | Memory    | 🟡 Medium    | Pydantic models, structured context |
| `guide.md`     | Interface | 🟣 Semantic  | LLM alignment, usage docs           |
| `prompts.md`   | Persona   | 🟣 Semantic  | Routing rules, prompt injection     |

## Current Git Skill Structure

```
agent/skills/git/
├── SKILL.md              # v2.0.0 - Skill metadata
├── scripts/              # All Git operations (atomic commands)
│   ├── __init__.py
│   ├── status.py
│   ├── commit.py
│   ├── push.py
│   └── ...
├── workflow.py           # LangGraph workflow orchestration
├── state.py              # GitWorkflowState Pydantic model
├── guide.md              # Usage documentation
├── prompts.md            # Routing rules & persona
└── Backlog.md            # Feature backlog (optional)
```

## State Definition

```python
# agent/skills/git/state.py
from pydantic import BaseModel, Field
from typing import Optional, List

class GitWorkflowState(BaseModel):
    # Input
    intent: str = Field(..., description="User's high-level intent, e.g. 'hotfix'")
    target_branch: str = ""
    commit_message: str = ""

    # Runtime state
    current_step: str = "init"
    stashed_hash: Optional[str] = None
    files_changed: List[str] = []
    is_dirty: bool = False

    # Results
    error_message: Optional[str] = None
    success: bool = False

    class Config:
        extra = "allow"  # Allow additional fields for flexibility
```

## Workflow Engine

```python
# agent/skills/git/workflow.py
from langgraph.graph import StateGraph, END
from .state import GitWorkflowState
from .scripts import git_status, git_stash_save, git_checkout, git_add

# 1. Nodes (atomic thoughts)
def node_check_env(state: GitWorkflowState):
    status = git_status(short=True)
    is_dirty = bool(status and "nothing to commit" not in status)
    return {"is_dirty": is_dirty, "current_step": "check_env"}

def node_stash(state: GitWorkflowState):
    hash = git_stash_save("Auto-stash by Omni Living Skill")
    return {"stashed_hash": hash, "current_step": "stash"}

def node_commit(state: GitWorkflowState):
    git_add(".")
    # ... call git_commit
    return {"success": True, "current_step": "commit"}

# 2. Graph (logic orchestration)
workflow = StateGraph(GitWorkflowState)
workflow.add_node("check_env", node_check_env)
workflow.add_node("stash", node_stash)
workflow.add_node("commit", node_commit)

workflow.set_entry_point("check_env")

# 3. Conditional Edges (smart routing)
def route_env(state: GitWorkflowState):
    if state.is_dirty:
        return "stash"
    return "commit"

workflow.add_conditional_edges("check_env", route_env, {"stash": "stash", "commit": "commit"})
workflow.add_edge("stash", "commit")
workflow.add_edge("commit", END)

app = workflow.compile()
```

## Manifest Structure

```json
{
  "name": "git",
  "version": "2.0.0",
  "description": "Git operations with LangGraph workflow support",
  "dependencies": ["langgraph"],
  "entry_point": "workflow",
  "scripts_module": "agent.skills.git.scripts",
  "workflow_module": "agent.skills.git.workflow",
  "intents": ["git_hotfix", "git_pr", "git_branch", "git_commit"]
}
```

## Integration Points

### MCP Server Integration

```python
# In mcp_server.py or router.py
from agent.skills.git.workflow import app, GitWorkflowState

@mcp.tool()
async def invoke_git_workflow(intent: str, **kwargs) -> str:
    """Invoke Git skill with LangGraph workflow."""
    state = GitWorkflowState(intent=intent, **kwargs)
    result = app.invoke(state)
    return format_result(result)
```

### Router Integration

```python
# In router.py - detect git intents
GIT_INTENTS = ["hotfix", "pr", "branch", "commit", "stash"]

def detect_git_intent(query: str) -> Optional[str]:
    for intent in GIT_INTENTS:
        if intent in query.lower():
            return intent
    return None
```

## Test Scenarios

1. **Hotfix Workflow**: Dirty → Stash → Switch → Commit → Pop
2. **Clean Workflow**: Direct commit when working tree is clean
3. **Interrupt & Resume**: State persists across sessions
4. **Error Handling**: Graceful degradation on failures

## Key Technical Decisions

1. **State Schema**: Pydantic BaseModel with `extra = "allow"` for flexibility
2. **Graph Engine**: LangGraph StateGraph (not ComplexGraph for simplicity)
3. **Node Functions**: Pure functions taking state, returning state dict
4. **Conditional Edges**: Function-based routing with type hints
5. **Backward Compatibility**: All existing command functions remain accessible

## Related Documentation

- [Skills Architecture](skills-architecture.md) - Complete skills architecture guide
- [Skill Standard](skill-standard.md) - OSS 1.0 compliance
- [Trinity Architecture](../explanation/trinity-architecture.md)
- [LangGraph Workflow Guide](../llm/langgraph-workflow-guide.md)
