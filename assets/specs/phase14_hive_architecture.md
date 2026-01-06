# Phase 14: The Hive Architecture (Multi-Agent Collaboration)

> **Status**: Draft
> **Complexity**: L3
> **Owner**: @omni-orchestrator
> **Version**: 1.0

## 1. Context & Goal (Why)

**Problem**: Current monolithic Orchestrator handles everything (planning, coding, reviewing) leading to:

- Cognitive overload on complex tasks
- No clear separation of concerns
- Hard to scale specialized capabilities

**Goal**: Transition from "Monolithic Brain" to "Specialized Swarm"

- **Orchestrator**: The Manager. Talks to user, plans, delegates.
- **Specialists**: The Workers. Single-minded, tool-heavy, no user-chat responsibility.

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      The Hive (In-Process)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   User Input                                                     │
│       │                                                          │
│       ▼                                                          │
│   ┌───────────────────────────────────────────┐                 │
│   │         OrchestratorAgent                  │                 │
│   │  - Interprets user intent                  │                 │
│   │  - Plans workflow                          │                 │
│   │  - Delegates to Specialists                │                 │
│   │  - Synthesizes responses                   │                 │
│   └────────────────┬──────────────────────────┘                 │
│                    │                                              │
│         ┌─────────┼─────────┬─────────┐                          │
│         │         │         │         │                          │
│         ▼         ▼         ▼         ▼                          │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│   │ Coder    │ │ Reviewer │ │ Planner  │                       │
│   │ Agent    │ │ Agent    │ │ Agent    │                       │
│   ├──────────┤ ├──────────┤ ├──────────┤                       │
│   │Write Code│ │PR Review │ │ Analysis │                       │
│   │Run Tests │ │Lint/Sec  │ │ Planning │                       │
│   └────┬─────┘ └────┬─────┘ └────┬─────┘                       │
│        │            │            │                              │
│        └────────────┴────────────┘                              │
│                    │                                              │
│              Shared ChromaDB                                      │
│         (Routing Experience, Knowledge)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 3. The Agent Protocol (Interface)

### 3.1 Agent Response Model

```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum

class Decision(Enum):
    ACT = "act"          # Execute tool call
    HANDOFF = "handoff"  # Transfer to another agent
    ASK_USER = "ask_user"  # Need clarification
    FINISH = "finish"    # Task complete

class ToolCall(BaseModel):
    tool: str
    args: Dict[str, Any]

class AgentResponse(BaseModel):
    decision: Decision
    tool_call: Optional[ToolCall] = None
    handoff_to: Optional[str] = None  # Agent name
    message: str = ""  # For user or internal log
    confidence: float = 0.5
```

### 3.2 Base Agent Abstract Class

```python
from abc import ABC, abstractmethod
from typing import Optional

class BaseAgent(ABC):
    name: str           # Unique identifier
    role: str           # Human-readable role
    description: str    # For orchestration
    skills: List[str]   # Allowed skill names

    @abstractmethod
    async def run(self, task: str, context: Dict[str, Any]) -> AgentResponse:
        """
        Main cognitive loop for the agent.

        Args:
            task: The task description from orchestrator
            context: Shared context (project info, file contents, etc.)

        Returns:
            AgentResponse with decision and supporting data
        """
        pass

    async def think(self, task: str, context: Dict[str, Any]) -> AgentResponse:
        """
        Decision phase: Analyze task and decide next action.
        Default implementation delegates to run().
        """
        return await self.run(task, context)

    async def act(self, tool_call: ToolCall) -> str:
        """
        Execution phase: Execute the tool call.
        """
        from agent.capabilities.skill_manager import _execute_skill_operation
        from agent.core.skill_registry import get_skill_registry, get_router

        # Use invoke_skill mechanism
        result = await _execute_skill_operation(
            skill=tool_call.tool.split('.')[0],  # e.g., "filesystem"
            operation=tool_call.tool.split('.')[1],  # e.g., "list_directory"
            kwargs=tool_call.args,
            mcp=None,
            registry=get_skill_registry()
        )
        return result
```

## 4. Memory & State Model

### 4.1 Memory Layers

| Layer                   | Type       | Access                | TTL        |
| ----------------------- | ---------- | --------------------- | ---------- |
| **Shared Vector Store** | Long-term  | All agents read/write | Persistent |
| **Handoff Context**     | Short-term | Transfer on handoff   | Per task   |
| **Agent Scratchpad**    | Ephemeral  | Private to agent      | Per turn   |

### 4.2 Handoff Protocol

```python
class TaskBrief(BaseModel):
    """Context passed during agent handoff"""
    task_description: str
    constraints: List[str]
    relevant_files: List[str]
    previous_attempts: List[str]  # What didn't work
    success_criteria: List[str]

class HandoffProtocol:
    @staticmethod
    async def handoff(
        from_agent: BaseAgent,
        to_agent: BaseAgent,
        task: str,
        brief: TaskBrief
    ) -> AgentResponse:
        """
        Transfer control from one agent to another.

        1. Serialize current state
        2. Brief receiving agent
        3. Transfer control
        """
        # Log the handoff for audit
        print(f"[HANDOFF] {from_agent.name} -> {to_agent.name}: {task}")

        # Create context for receiving agent
        context = {
            "handoff_from": from_agent.name,
            "task_brief": brief.model_dump(),
            "handoff_timestamp": time.time()
        }

        # Start receiving agent
        return await to_agent.run(task, context)
```

## 5. The Roles

### 5.1 OrchestratorAgent (The Manager)

**Trigger**: User Input
**Skills**: `router`, `context`, `knowledge`
**Goal**: Understand -> Plan -> Delegate -> Review -> Reply

```python
class OrchestratorAgent(BaseAgent):
    name = "orchestrator"
    role = "Manager"
    description = "Interprets user intent and coordinates specialist agents"
    skills = ["router", "context", "knowledge"]

    async def run(self, user_input: str, context: Dict) -> AgentResponse:
        # 1. Parse user intent
        routing_result = await get_router().route(user_input)

        # 2. If simple task, handle directly
        if len(routing_result.selected_skills) == 1:
            skill = routing_result.selected_skills[0]
            return AgentResponse(
                decision=Decision.ACT,
                tool_call=ToolCall(tool=f"{skill}.execute", args={"query": user_input}),
                message=routing_result.mission_brief
            )

        # 3. Complex task: Delegate to specialist
        if "code" in user_input.lower() or "implement" in user_input.lower():
            return AgentResponse(
                decision=Decision.HANDOFF,
                handoff_to="coder",
                message="Delegating to CoderAgent"
            )
        elif "review" in user_input.lower() or "check" in user_input.lower():
            return AgentResponse(
                decision=Decision.HANDOFF,
                handoff_to="reviewer",
                message="Delegating to ReviewerAgent"
            )

        # 4. Default: ask for clarification
        return AgentResponse(
            decision=Decision.ASK_USER,
            message="I need more details to help you."
        )
```

### 5.2 CoderAgent (The Builder)

**Trigger**: Handoff from Orchestrator
**Skills**: `filesystem`, `software_engineering`, `terminal`, `testing`
**Goal**: Write code that passes tests

```python
class CoderAgent(BaseAgent):
    name = "coder"
    role = "Builder"
    description = "Implements features and fixes bugs"
    skills = ["filesystem", "software_engineering", "terminal", "testing"]

    async def run(self, task: str, context: Dict) -> AgentResponse:
        # Analyze task from brief
        brief = context.get("task_brief", {})

        # Execute using invoke_skill
        return AgentResponse(
            decision=Decision.ACT,
            tool_call=ToolCall(
                tool="software_engineering.analyze_and_modify",
                args={
                    "task": task,
                    "constraints": brief.get("constraints", []),
                    "files": brief.get("relevant_files", [])
                }
            ),
            message=f"Coding: {task}"
        )
```

### 5.3 ReviewerAgent (The Gatekeeper)

**Trigger**: Handoff from Orchestrator or Coder
**Skills**: `git`, `testing`, `linter`
**Goal**: Ensure quality, approve for commit

```python
class ReviewerAgent(BaseAgent):
    name = "reviewer"
    role = "Gatekeeper"
    description = "Reviews code quality and security"
    skills = ["git", "testing", "linter"]

    async def run(self, task: str, context: Dict) -> AgentResponse:
        # Run tests
        test_result = await _execute_skill_operation(
            skill="testing",
            operation="run_tests",
            kwargs={},
            mcp=None,
            registry=get_skill_registry()
        )

        # Run linter
        lint_result = await _execute_skill_operation(
            skill="linter",
            operation="check_code",
            kwargs={},
            mcp=None,
            registry=get_skill_registry()
        )

        # Decide
        if "pass" in test_result and "pass" in lint_result:
            return AgentResponse(
                decision=Decision.FINISH,
                message="Code review passed. Ready for commit."
            )
        else:
            return AgentResponse(
                decision=Decision.HANDOFF,
                handoff_to="coder",
                message=f"Issues found: {test_result} {lint_result}"
            )
```

## 6. Workflow Example

### Example: "Refactor Login"

```
1. User: "Refactor login to use OAuth"

2. OrchestratorAgent:
   - Analyzes intent (refactor + OAuth)
   - Creates TaskBrief with constraints
   - HANDOFF -> CoderAgent

3. CoderAgent:
   - Reads login files
   - Modifies code
   - Runs tests
   - HANDOFF -> ReviewerAgent (with changes summary)

4. ReviewerAgent:
   - Runs full test suite
   - Runs security lint
   - If pass: FINISH (approved)
   - If fail: HANDOFF -> CoderAgent (with fixes needed)

5. OrchestratorAgent:
   - Receives completion
   - "Refactor complete and ready to commit"
```

## 7. Integration Points

### 7.1 Router Integration

The main router will be enhanced to support agent routing:

```python
# In router.py route() method
async def route(self, user_query: str, chat_history: List[Dict] = None) -> RoutingResult:
    # ... existing routing ...

    # New: Check if should route to agent
    if should_delegate_to_agent(routing_result.selected_skills):
        target_agent = select_agent(routing_result.selected_skills)
        return RoutingResult(
            selected_skills=[target_agent],
            mission_brief=f"Handoff to {target_agent}",
            reasoning=f"Complex task requiring {target_agent} expertise",
            confidence=0.9,
        )
```

### 7.2 Main Loop

```python
async def hive_main():
    """Main entry point for the Hive architecture."""
    # Initialize agents
    orchestrator = OrchestratorAgent()
    coder = CoderAgent()
    reviewer = ReviewerAgent()

    agents = {
        "orchestrator": orchestrator,
        "coder": coder,
        "reviewer": reviewer
    }

    # Main loop
    while True:
        user_input = await get_user_input()
        if user_input == "exit":
            break

        # Orchestrator handles initial request
        response = await orchestrator.run(user_input, {})

        # Handle response
        while response.decision not in [Decision.FINISH, Decision.ASK_USER]:
            if response.decision == Decision.ACT:
                result = await orchestrator.act(response.tool_call)
                response = await orchestrator.run(result, {})
            elif response.decision == Decision.HANDOFF:
                target = agents[response.handoff_to]
                brief = TaskBrief(
                    task_description=response.message,
                    constraints=[],
                    relevant_files=[],
                    previous_attempts=[],
                    success_criteria=["Complete task"]
                )
                response = await HandoffProtocol.handoff(
                    orchestrator, target, response.message, brief
                )

        print(response.message)
```

## 8. Testing Strategy

| Level       | Test File                   | Coverage                            |
| ----------- | --------------------------- | ----------------------------------- |
| Unit        | `test_agent_base.py`        | BaseAgent lifecycle, decision logic |
| Unit        | `test_handoff_protocol.py`  | Context transfer, error handling    |
| Integration | `test_coder_workflow.py`    | CoderAgent file operations          |
| Integration | `test_reviewer_workflow.py` | ReviewerAgent quality checks        |
| E2E         | `test_hive_end_to_end.py`   | Complete user workflows             |

## 9. Trade-offs & Constraints

| Trade-off                         | Rationale                                |
| --------------------------------- | ---------------------------------------- |
| In-process vs. Separate processes | Shared memory, simpler state management  |
| No hard isolation                 | Agents trust each other (same process)   |
| Sequential by default             | Parallel agent execution adds complexity |

## 10. Rollout Plan

1. **Step 1**: Create this architecture document ✅
2. **Step 2**: Implement `BaseAgent` abstract class
3. **Step 3**: Implement `OrchestratorAgent` (minimal)
4. **Step 4**: Implement `CoderAgent`
5. **Step 5**: Implement `ReviewerAgent`
6. **Step 6**: Integrate with existing router
7. **Step 7**: Test end-to-end workflows

## 11. Related Documents

| Document                       | Purpose                               |
| ------------------------------ | ------------------------------------- |
| `phase10_hive_architecture.md` | Multi-process architecture (Phase 10) |
| `phase14_5_semantic_cortex.md` | Semantic caching for routing          |
| `skills/*/prompts.md`          | Skill-specific rules                  |
