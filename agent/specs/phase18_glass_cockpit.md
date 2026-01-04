# Phase 18: The Glass Cockpit

**Status**: Implemented
**Type**: UX/UI Enhancement
**Owner**: UXManager
**Vision**: Real-time TUI visualization for agent state, routing, RAG knowledge, and audit feedback

## 1. Problem Statement

**The Pain: Opaque Agent Execution**

When agents execute tasks, users see nothing until completion:

```
> Fix the auth bug
> (3 minutes of silence)
> Here is the fixed code
```

No visibility into:
- Which agent was selected and why
- What knowledge was retrieved
- Execution progress
- Audit/review results
- Self-correction attempts

## 2. The Solution: Glass Cockpit TUI

Transform opaque execution into a beautiful, real-time terminal experience:

```
╭──────────────────────────────────────────────────────────────────────────────╮
│ 🚀 New Task                                                                   │
│ User Query: Fix the auth bug in login.py                                     │
╰──────────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────────╮
│ 📋 Mission for CODER (cached)                                                │
│ Fix the auth bug in login.py                                                 │
│ Confidence: 75%                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯

📚 [bold cyan]Active RAG Knowledge[/]
├── [green]agent/skills/knowledge/standards/security.md
│   Similarity: 92%
└── [green]agent/skills/knowledge/standards/lang-python.md
    Similarity: 85%

🛠️ CODER is working...
```

## 3. Architecture Specification

### 3.1 UXManager Class

```python
from enum import Enum
from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from typing import Optional, List, Dict, Any

class AgentState(Enum):
    """Agent execution states for TUI display."""
    IDLE = "idle"
    ROUTING = "routing"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    CORRECTING = "correcting"
    COMPLETED = "completed"
    FAILED = "failed"

class UXManager:
    """
    Glass Cockpit - Terminal UI Manager for Omni Orchestrator.

    Transforms complex agent internal states into beautiful, readable TUI.
    """

    def __init__(self):
        self.console = Console()
        self.task_id: Optional[str] = None
        self.current_state: AgentState = AgentState.IDLE
        self._status: Optional[Progress] = None

    # Task Lifecycle
    def start_task(self, user_query: str) -> None
    def end_task(self, success: bool = True) -> None

    # Routing Visualization
    def start_routing(self) -> None
    def stop_routing(self) -> None
    def show_routing_result(
        self,
        agent_name: str,
        mission_brief: str,
        confidence: float = 1.0,
        from_cache: bool = False
    ) -> None

    # RAG Visualization
    def show_rag_hits(self, hits: List[Dict[str, Any]]) -> None

    # Execution Visualization
    def start_execution(self, agent_name: str) -> None
    def stop_execution(self) -> None

    # Review/Audit Visualization
    def start_review(self) -> None
    def show_audit_result(
        self,
        approved: bool,
        feedback: str,
        issues: List[str] = None,
        suggestions: List[str] = None
    ) -> None

    # Correction Loop
    def show_correction_loop(self, attempt: int, max_attempts: int) -> None

    # Agent Response
    def print_agent_response(self, content: str, title: str = "Agent Output") -> None
```

### 3.2 Integration with Orchestrator

```python
class Orchestrator:
    def __init__(self, ...):
        self.ux = get_ux_manager()  # Phase 18: Glass Cockpit

    async def dispatch(self, user_query: str, ...) -> str:
        # Phase 18: Start task visualization
        self.ux.start_task(user_query)

        # === Phase 1: Hive Routing ===
        self.ux.start_routing()
        route = await self.router.route_to_agent(...)
        self.ux.stop_routing()

        # Phase 18: Show routing result
        self.ux.show_routing_result(
            agent_name=route.target_agent,
            mission_brief=route.task_brief,
            confidence=route.confidence,
            from_cache=route.from_cache
        )

        # === Phase 2: Execution ===
        self.ux.start_execution(worker.name)
        result = await worker.run(...)
        self.ux.stop_execution()

        # Phase 18: Show RAG sources
        if result.rag_sources:
            self.ux.show_rag_hits(result.rag_sources)

        self.ux.end_task(success=result.success)
        return result.content
```

### 3.3 Enhanced Models

```python
# packages/python/agent/src/agent/core/router/models.py
class AgentRoute(BaseModel):
    target_agent: str
    confidence: float = 0.5
    reasoning: str
    task_brief: str = ""
    constraints: List[str] = []
    relevant_files: List[str] = []
    from_cache: bool = False  # Phase 18: Cache hit indicator

# packages/python/agent/src/agent/core/agents/base.py
class AgentResult(BaseModel):
    success: bool
    content: str = ""
    tool_calls: List[Dict[str, Any]] = []
    message: str = ""
    confidence: float = 0.5
    audit_result: Optional[Dict[str, Any]] = None
    needs_review: bool = False
    rag_sources: List[Dict[str, Any]] = []  # Phase 18: RAG sources for UX
```

## 4. Visual Design Specs

### 4.1 Color Scheme

| State | Color | Usage |
|-------|-------|-------|
| Routing | Cyan | HiveRouter analysis |
| Execution | Yellow | Agent working |
| Review | Magenta | Reviewer auditing |
| Correction | Yellow | Self-correction loop |
| Success | Green | Task completed |
| Error | Red | Task failed |
| Cache Hit | Yellow | Cached routing |

### 4.2 Panel Layout

```
┌─────────────────────────────────────────────────────┐
│ 🚀 New Task (or ✅ Task Completed / ❌ Task Failed) │
├─────────────────────────────────────────────────────┤
│ User Query:                                         │
│ [user query content]                                │
├─────────────────────────────────────────────────────┤
│ 📋 Mission for [AGENT] (cached)                     │
│ [mission brief]                                     │
│ Confidence: XX%                                     │
├─────────────────────────────────────────────────────┤
│ 📚 Active RAG Knowledge                             │
│ ├── [file1] - Similarity: XX%                       │
│ └── [file2] - Similarity: XX%                       │
├─────────────────────────────────────────────────────┤
│ 🤖 [AGENT] Output                                   │
│ [Markdown rendered content]                         │
└─────────────────────────────────────────────────────┘
```

## 5. Implementation Files

| File | Change |
|------|--------|
| `packages/python/agent/src/agent/core/ux.py` | NEW: UXManager class |
| `packages/python/agent/src/agent/core/orchestrator.py` | MODIFIED: Integrate UXManager |
| `packages/python/agent/src/agent/core/agents/base.py` | MODIFIED: Add rag_sources |
| `packages/python/agent/src/agent/core/router/models.py` | MODIFIED: Add from_cache to AgentRoute |
| `packages/python/agent/src/agent/core/router/hive.py` | MODIFIED: Set from_cache flag |

## 6. Benefits

| Aspect | Before | After |
|--------|--------|-------|
| Visibility | Silent execution | Real-time progress |
| Debugging | Post-mortem logs | Live state tracking |
| User Trust | Black box | Transparent workflow |
| Cache Awareness | Hidden | Explicit (cached) indicator |
| RAG Feedback | None | Shows retrieved knowledge |

## 7. Future Enhancements

- [ ] Live layout with `rich.live` for real-time updates
- [ ] Progress bars for long-running tasks
- [ ] Keyboard shortcuts for interrupting tasks
- [ ] Export execution trace to file
- [ ] Agent-specific icons (coder: 🛠️, reviewer: 🕵️, orchestrator: 🎯)
