# Phase 19: The Cognitive Injection

## Overview

Phase 19 introduces **Dependency Injection** and **ReAct Loop** capabilities to the agent system, giving CoderAgent a "brain" (LLM inference) and "hands" (filesystem tools).

## The Problem

Before Phase 19, CoderAgent was like a worker without tools:

```python
# Problem: Agent has no cognition or capabilities
class Orchestrator:
    def dispatch(self):
        worker = CoderAgent()  # Worker with no brain, no hands!
        result = worker.run()  # Just returns placeholder text
```

## The Solution

### 1. Dependency Injection Pattern

**Injection** means passing an already-configured Python object reference, not creating a new network session.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator (The Foreman)                   │
│                                                                 │
│   self.inference = InferenceClient()  ← Already configured     │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Dependency Injection
                           │ (passing object reference)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CoderAgent (The Worker)                      │
│                                                                 │
│   def __init__(self, inference, tools):                         │
│       self.inference = inference  ← Gets the walkie-talkie     │
│       self.tools = tools        ← Gets the tools               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits:**

- No additional network overhead (same API connection)
- Centralized configuration management
- Testable code (easy to mock dependencies)

### 2. ReAct Loop: Think → Act → Observe

The ReAct pattern gives agents intelligent decision-making:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ReAct Loop                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. THINK    LLM decides: "I need to read main.py first"      │
│       │                                                          │
│       ▼                                                          │
│   2. ACT      Execute: read_file(path="main.py")               │
│       │                                                          │
│       ▼                                                          │
│   3. OBSERVE  Get result: "File contains threading code"       │
│       │                                                          │
│       ▼                                                          │
│   4. THINK    LLM decides: "Now I see the bug, let me fix it"  │
│       │                                                          │
│       ▼                                                          │
│   5. ACT      Execute: write_file(path="main.py", content=...) │
│       │                                                          │
│       ▼                                                          │
│   6. OBSERVE  Get result: "File written successfully"          │
│       │                                                          │
│       ▼                                                          │
│   7. THINK    LLM decides: "Done, no more tools needed"        │
│       │                                                          │
│       ▼                                                          │
│   8. RETURN   AgentResult with final content                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Context Isolation (Token Economics)

**Why separate contexts matter:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    Main CLI Session (Shared Context)            │
│                                                                 │
│   User: "Fix the threading bug in main.py"                     │
│   Claude: [Delegates to CoderAgent via delegate_mission]       │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Extract essential context
                           │ (Mission Brief + Relevant Files)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CoderAgent (Private Context)                 │
│                                                                 │
│   - Clean, focused context window                              │
│   - Internal ReAct loop (many iterations)                      │
│   - All intermediate failures stay private                     │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Return final result only
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Main CLI Session (Clean)                     │
│                                                                 │
│   Result: "Fixed the threading bug in main.py"                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits of isolation:**

- Main conversation history stays clean
- Failed attempts don't pollute main context
- Token usage optimized per task
- Better LLM focus on specific task

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Phase 19 Architecture                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────────┐                                               │
│   │ Orchestrator    │                                               │
│   │                 │                                               │
│   │ - inference     │───┐                                           │
│   │ - router        │   │                                           │
│   │ - ux_manager    │   │                                           │
│   └─────────────────┘   │                                           │
│                         │                                           │
│   ┌─────────────────┐   │    ┌─────────────────┐                    │
│   │ _get_tools_for  │───┼───►│   CoderAgent    │                    │
│   │ _agent()        │   │    │                 │                    │
│   └─────────────────┘   │    │ - inference     │                    │
│                         │    │ - tools         │                    │
│   Tool Registry:        │    │ - _run_react()  │                    │
│   - read_file          │    └────────┬────────┘                    │
│   - write_file         │             │                             │
│   - search_files       │             │                             │
│   - git_status         │             │                             │
│   - run_tests          │             │                             │
│                         │             │                             │
│                         │    ┌────────▼────────┐                   │
│                         │    │ ReAct Loop      │                   │
│                         │    │                 │                   │
│                         │    │ 1. Think (LLM)  │                   │
│                         │    │ 2. Act (tool)   │                   │
│                         │    │ 3. Observe      │                   │
│                         │    │ 4. Repeat       │                   │
│                         │    └─────────────────┘                   │
│                         │                                           │
│                         └──────────────────────────────────────────┘
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation

### BaseAgent Changes

```python
class BaseAgent(ABC):
    def __init__(self, inference=None, tools=None):
        self.inference = inference      # LLM brain
        self.tools = tools or {}        # Action hands
        self._action_history = []       # Track ReAct steps

    async def _run_react_loop(self, task, system_prompt, max_steps=5):
        """Execute ReAct loop: Think → Act → Observe"""
        for step in range(max_steps):
            # 1. Call LLM with context
            result = await self.inference.complete(
                system_prompt=system_prompt,
                user_query=f"Task: {task}\nHistory: {self._action_history}"
            )

            # 2. Parse tool call from response
            tool_call = self._parse_tool_call(result["content"])

            if tool_call:
                # 3. Execute tool
                tool_name, args = tool_call
                if tool_name in self.tools:
                    output = await self.tools[tool_name](**args)
                    self._action_history.append({
                        "step": step + 1,
                        "action": f"TOOL: {tool_name}",
                        "result": str(output)[:500]
                    })
            else:
                # 4. No more tools needed, return result
                return AgentResult(
                    success=True,
                    content=result["content"],
                    confidence=0.9,
                    tool_calls=self._action_history
                )
```

### Orchestrator Changes

```python
class Orchestrator:
    def __init__(self, inference_engine=None):
        # Auto-create inference if not provided
        if inference_engine is None:
            from common.mcp_core.inference import InferenceClient
            inference_engine = InferenceClient()
        self.inference = inference_engine

    def _get_tools_for_agent(self, agent_name: str) -> Dict:
        """Tool registry per agent type"""
        from agent.skills.filesystem.tools import (
            read_file, write_file, list_directory, search_files
        )

        base_tools = {
            "list_directory": list_directory,
            "read_file": read_file,
            "search_files": search_files,
        }

        if agent_name == "coder":
            return {**base_tools, "write_file": write_file}

        elif agent_name == "reviewer":
            from agent.skills.git.tools import git_status, git_diff
            from agent.skills.testing.tools import run_tests
            return {**base_tools, "git_status": git_status,
                    "git_diff": git_diff, "run_tests": run_tests}

        return base_tools

    async def dispatch(self, user_query, history=None):
        # Route to agent
        route = await self.router.route_to_agent(user_query)

        # Create agent with injected dependencies
        tools = self._get_tools_for_agent(route.target_agent)
        worker = route.target_agent_class(
            inference=self.inference,
            tools=tools
        )

        # Execute
        return await worker.run(task=user_query, mission_brief=route.task_brief)
```

## Tool Call Format

CoderAgent expects LLM responses in this format for tool calls:

```python
# Format: TOOL: tool_name(arg1="value1", arg2="value2")

# Examples:
"TOOL: read_file(path=\"main.py\")"
"TOOL: write_file(path=\"test.py\", content=\"print('hello')\")"
"TOOL: search_files(pattern=\"**/*.py\")"
```

## Usage

```python
from agent.core.orchestrator import Orchestrator

# Orchestrator auto-initializes with inference
orchestrator = Orchestrator()

# Delegate complex task
result = await orchestrator.dispatch(
    user_query="Fix the threading bug in main.py"
)

print(result)
# Output: "Fixed the threading bug by adding daemon thread..."
```

## Summary

| Concept     | Before Phase 19          | After Phase 19                 |
| ----------- | ------------------------ | ------------------------------ |
| Cognition   | Placeholder text         | Real LLM inference             |
| Tools       | N/A                      | read_file, write_file, etc.    |
| Execution   | Single pass              | ReAct loop (Think→Act→Observe) |
| Context     | Shared with main session | Isolated per task              |
| Agent State | Empty shell              | Functional worker              |

## Files Changed

- `agent/core/agents/base.py` - Added `__init__()`, `_run_react_loop()`, `_parse_tool_call()`
- `agent/core/agents/coder.py` - Added `__init__()`, `_load_skill_tools()`, ReAct integration
- `agent/core/orchestrator.py` - Added auto inference creation, `_get_tools_for_agent()`
- `agent/core/skill_registry.py` - Added `get_skill_tools()` for tool retrieval
- `common/mcp_core/inference.py` - Added `get_tool_schema()` for LLM tool definitions

## Scenario Test: Fix Threading Bug

### Test Flow

```
User Request → delegate_mission → Orchestrator → CoderAgent(ReAct Loop) → Tool Execution
```

### Test Scenario: Fix the threading bug in main.py

**Executed ReAct Loop Steps:**

1. **Step 1**: LLM decides to use `list_directory` tool
   - Action: Execute `list_directory(path=".")`
   - Result: Found `packages/python/agent/src/agent/main.py`

2. **Step 2**: LLM continues exploration
   - Action: Search for files matching `**/main.py`
   - Result: Located `packages/python/agent/src/agent/main.py`

3. **Step 3**: LLM reads the file
   - Action: Execute `read_file(path="packages/python/agent/src/agent/main.py")`
   - Result: File content loaded

4. **Step 4**: LLM identifies the threading bug
   - Action: Analyze code for threading issues
   - Result: Found bug in `bootstrap.py` - global variable shadowing

5. **Step 5**: LLM fixes the bug
   - Action: Execute `write_file()` with fixed code
   - Result: Bug fixed

### Bug Found and Fixed

**Before (bootstrap.py:69):**

```python
def start_background_tasks() -> threading.Thread | None:
    _background_thread: threading.Thread | None = None  # Local variable shadows global!
```

**After (bootstrap.py:67):**

```python
def start_background_tasks() -> threading.Thread | None:
    global _background_thread  # Correctly reference global variable
```

### Test Results

| Test Class              | Count | Description                               |
| ----------------------- | ----- | ----------------------------------------- |
| TestReActLoop           | 3     | Think → Act → Observe cycle validation    |
| TestToolCallParsing     | 5     | Multi-format tool call parsing            |
| TestThreadSafety        | 6     | Thread safety and graceful shutdown       |
| TestDependencyInjection | 4     | Dependency injection verification         |
| TestStatePersistence    | 2     | Action history across steps               |
| Other                   | 13    | Orchestrator integration, UX events, etc. |

**Total: 33 passed, 4 warnings in 1.30s**

### Key Improvements Verified

1. **Cognitive Injection**: CoderAgent has "brain" (LLM) + "hands" (tools)
2. **Context Isolation**: Each task has independent context window
3. **State Persistence**: Tool execution history maintained in ReAct loop
4. **Graceful Shutdown**: Background threads can be properly closed
5. **Skill Registry Integration**: Tools loaded from dynamically loaded skills

---

## Phase 19.5: Enterprise Enhancements

> **Status**: Complete (45 tests passing)
> **Philosophy**: "Production-grade observability, robustness, and feedback loops."

### 1. Observability: UX Event Emission (Glass Cockpit)

Phase 18's Glass Cockpit now has real data from the ReAct loop.

#### UX Event Types

| Event Type | When Emitted | Payload |
|------------|--------------|---------|
| `think_start` | LLM starts reasoning | `{"step": 1, "task": "...", "history_length": 0}` |
| `act_execute` | Tool execution starts | `{"step": 1, "tool": "read_file", "args": {"path": "..."}}` |
| `observe_result` | Tool result received | `{"step": 1, "tool": "read_file", "success": true}` |

#### Event Format

```json
{
  "type": "think_start",
  "agent": "coder",
  "payload": {"step": 1, "task": "Fix the bug", "history_length": 0},
  "timestamp": 1704384000.123
}
```

#### Test Coverage

| Test | Description |
|------|-------------|
| `test_emit_ux_event_writes_to_file` | Events written to `.cache/omni_ux_events.jsonl` |
| `test_emit_ux_event_format` | Event has required fields (type, agent, payload, timestamp) |
| `test_react_loop_emits_think_start_event` | ReAct loop emits `think_start` |
| `test_react_loop_emits_act_execute_event` | ReAct loop emits `act_execute` |
| `test_react_loop_emits_observe_result_event` | ReAct loop emits `observe_result` |

### 2. Robustness: ReAct Loop Error Handling

| Test | Scenario | Expected Behavior |
|------|----------|-------------------|
| `test_stuck_loop_detection` | LLM calls same tool repeatedly | Stops at `max_steps` with low confidence |
| `test_tool_exception_handling` | Tool throws exception | Caught and returned as error result |
| `test_unavailable_tool_graceful_handling` | Tool not in registry | Error message to LLM, continue loop |

### 3. Feedback Loop: Coder → Reviewer → Coder

Architecture support for Phase 15's Audit System:

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    Feedback Loop Architecture                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   1. CoderAgent executes task                                       │
│           │                                                          │
│           ▼                                                          │
│   2. ReviewerAgent audits result                                    │
│           │                                                          │
│           ├── ✅ Approved → Return to user                          │
│           │                                                          │
│           └── ❌ Rejected → Return to Coder for revision            │
│           │                                                          │
│           └── 🔄 Loop until approved or max iterations              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### Test Coverage

| Test | Description |
|------|-------------|
| `test_coder_review_cycle_exists` | `_execute_with_feedback_loop` method exists |
| `test_reviewer_agent_has_audit_method` | ReviewerAgent has `audit()` method |
| `test_orchestrator_has_tools_for_reviewer` | Reviewer tools available |
| `test_feedback_loop_architecture_diagram` | Architecture supports cycle |

### Test Results Summary

| Category | Tests | Status |
|----------|-------|--------|
| Core ReAct Loop | 3 | ✅ Pass |
| Tool Call Parsing | 5 | ✅ Pass |
| Thread Safety | 6 | ✅ Pass |
| Dependency Injection | 4 | ✅ Pass |
| State Persistence | 2 | ✅ Pass |
| UX Event Emission | 5 | ✅ Pass |
| ReAct Robustness | 3 | ✅ Pass |
| Feedback Loop | 4 | ✅ Pass |
| **Total** | **45** | **✅ All Pass** |
