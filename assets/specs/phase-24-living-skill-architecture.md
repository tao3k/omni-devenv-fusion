# Phase 24: Living Skill Architecture

## 🎯 Objective

Transform skills from simple function collections into "Intelligent Microservice Units" using LangGraph for orchestration. Implement **Omni Skill Standard (OSS)** for the Git skill as a proof-of-concept.

## 📋 Deliverables

1. **OSS Directory Structure** - Standardize skill package layout
2. **State Definition** (`state.py`) - Pydantic models for structured context
3. **Workflow Engine** (`workflow.py`) - LangGraph-based orchestration
4. **Router Integration** - Allow MCP router to invoke graphs
5. **Documentation** - Update guide.md and prompts.md

## 🏗️ Omni Skill Standard (OSS) - Directory Structure

```
agent/skills/<skill_name>/
├── 📄 manifest.json       # [IDENTITY]  Metadata & configuration
├── 🛠️ tools.py            # [HANDS]     Atomic tools (stateless, side-effects only)
├── 🧠 workflow.py         # [BRAIN]     Workflow logic (LangGraph graph)
├── 💾 state.py            # [MEMORY]    State definition (Pydantic models)
├── 📘 guide.md            # [INTERFACE] Usage docs (RAG/prompt context)
└── 📝 prompts.md          # [PERSONA]   Routing rules & prompt injection
```

### File Responsibilities

| File            | Role      | Intelligence | Purpose                             |
| --------------- | --------- | ------------ | ----------------------------------- |
| `manifest.json` | Identity  | ❌ None      | Metadata, dependencies, entry_point |
| `tools.py`      | Hands     | 🔵 Low       | Atomic actions, side-effects only   |
| `workflow.py`   | Brain     | 🔴 High      | Orchestration, LangGraph graph      |
| `state.py`      | Memory    | 🟡 Medium    | Pydantic models, structured context |
| `guide.md`      | Interface | 🟣 Semantic  | LLM alignment, usage docs           |
| `prompts.md`    | Persona   | 🟣 Semantic  | Routing rules, prompt injection     |

### Current Git Skill Structure

```
agent/skills/git/
├── manifest.json          # v2.0.0 - Skill metadata
├── tools.py               # All Git operations (atomic tools)
├── workflow.py            # LangGraph workflow orchestration
├── state.py               # GitWorkflowState Pydantic model
├── guide.md               # Usage documentation
├── prompts.md             # Routing rules & persona
└── Backlog.md             # Feature backlog (optional)
```

## 🚀 Implementation Plan

### Phase 1: Foundation (Day 1)

#### 1.1 Create `state.py`

```python
# agent/skills/git/state.py
from pydantic import BaseModel, Field
from typing import Optional, List

class GitWorkflowState(BaseModel):
    # 输入
    intent: str = Field(..., description="User's high-level intent, e.g. 'hotfix'")
    target_branch: str = ""
    commit_message: str = ""

    # 运行时状态
    current_step: str = "init"
    stashed_hash: Optional[str] = None
    files_changed: List[str] = []
    is_dirty: bool = False

    # 结果
    error_message: Optional[str] = None
    success: bool = False

    class Config:
        extra = "allow"  # Allow additional fields for flexibility
```

#### 1.2 Create `workflow.py`

```python
# agent/skills/git/workflow.py
from langgraph.graph import StateGraph, END
from .state import GitWorkflowState
from .tools import git_status, git_stash_save, git_checkout, git_add

# 1. Nodes (原子思考)
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

# 2. Graph (逻辑编排)
workflow = StateGraph(GitWorkflowState)
workflow.add_node("check_env", node_check_env)
workflow.add_node("stash", node_stash)
workflow.add_node("commit", node_commit)

workflow.set_entry_point("check_env")

# 3. Conditional Edges (智能路由)
def route_env(state: GitWorkflowState):
    if state.is_dirty:
        return "stash"
    return "commit"

workflow.add_conditional_edges("check_env", route_env, {"stash": "stash", "commit": "commit"})
workflow.add_edge("stash", "commit")
workflow.add_edge("commit", END)

app = workflow.compile()
```

#### 1.3 Update `manifest.json`

```json
{
  "name": "git",
  "version": "2.0.0",
  "description": "Git operations with LangGraph workflow support",
  "dependencies": ["langgraph"],
  "entry_point": "workflow",
  "tools_module": "agent.skills.git.tools",
  "workflow_module": "agent.skills.git.workflow",
  "intents": ["git_hotfix", "git_pr", "git_branch", "git_commit"]
}
```

### Phase 2: Integration (Day 2)

#### 2.1 Update mcp_server.py

Add support for invoking LangGraph workflows:

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

#### 2.2 Update Router

Add intent matching for high-level Git operations:

```python
# In router.py - detect git intents
GIT_INTENTS = ["hotfix", "pr", "branch", "commit", "stash"]

def detect_git_intent(query: str) -> Optional[str]:
    for intent in GIT_INTENTS:
        if intent in query.lower():
            return intent
    return None
```

### Phase 3: Testing & Rollout (Day 3)

#### 3.1 Test Scenarios

1. **Hotfix Workflow**: Dirty → Stash → Switch → Commit → Pop
2. **Clean Workflow**: Direct commit when working tree is clean
3. **Interrupt & Resume**: State persists across sessions
4. **Error Handling**: Graceful degradation on failures

## 🔑 Key Technical Decisions

1. **State Schema**: Pydantic BaseModel with `extra = "allow"` for flexibility
2. **Graph Engine**: LangGraph StateGraph (not ComplexGraph for simplicity)
3. **Node Functions**: Pure functions taking state, returning state dict
4. **Conditional Edges**: Function-based routing with type hints
5. **Backward Compatibility**: All existing tools.py functions remain accessible

## 📊 Success Criteria

- [ ] Git skill can handle hotfix workflow via single intent
- [ ] State persists across interruptions
- [ ] Conditional branching works (dirty → stash → commit)
- [ ] All existing tools still accessible via MCP
- [ ] Router can route to workflow based on intent

## 📦 Dependencies

```txt
langgraph>=0.2.0
pydantic>=2.0
```

## 🎯 Next Steps

1. Create `state.py` with GitWorkflowState model
2. Create `workflow.py` with LangGraph nodes
3. Update `manifest.json` to declare langgraph dependency
4. Add router integration in mcp_server.py
5. Write tests for the living skill architecture
