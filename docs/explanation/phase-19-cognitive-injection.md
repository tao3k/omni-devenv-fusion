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

| Event Type       | When Emitted          | Payload                                                     |
| ---------------- | --------------------- | ----------------------------------------------------------- |
| `think_start`    | LLM starts reasoning  | `{"step": 1, "task": "...", "history_length": 0}`           |
| `act_execute`    | Tool execution starts | `{"step": 1, "tool": "read_file", "args": {"path": "..."}}` |
| `observe_result` | Tool result received  | `{"step": 1, "tool": "read_file", "success": true}`         |

#### Event Format

```json
{
  "type": "think_start",
  "agent": "coder",
  "payload": { "step": 1, "task": "Fix the bug", "history_length": 0 },
  "timestamp": 1704384000.123
}
```

#### Test Coverage

| Test                                         | Description                                                 |
| -------------------------------------------- | ----------------------------------------------------------- |
| `test_emit_ux_event_writes_to_file`          | Events written to `.cache/omni_ux_events.jsonl`             |
| `test_emit_ux_event_format`                  | Event has required fields (type, agent, payload, timestamp) |
| `test_react_loop_emits_think_start_event`    | ReAct loop emits `think_start`                              |
| `test_react_loop_emits_act_execute_event`    | ReAct loop emits `act_execute`                              |
| `test_react_loop_emits_observe_result_event` | ReAct loop emits `observe_result`                           |

### 2. Robustness: ReAct Loop Error Handling

| Test                                      | Scenario                       | Expected Behavior                        |
| ----------------------------------------- | ------------------------------ | ---------------------------------------- |
| `test_stuck_loop_detection`               | LLM calls same tool repeatedly | Stops at `max_steps` with low confidence |
| `test_tool_exception_handling`            | Tool throws exception          | Caught and returned as error result      |
| `test_unavailable_tool_graceful_handling` | Tool not in registry           | Error message to LLM, continue loop      |

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

| Test                                       | Description                                 |
| ------------------------------------------ | ------------------------------------------- |
| `test_coder_review_cycle_exists`           | `_execute_with_feedback_loop` method exists |
| `test_reviewer_agent_has_audit_method`     | ReviewerAgent has `audit()` method          |
| `test_orchestrator_has_tools_for_reviewer` | Reviewer tools available                    |
| `test_feedback_loop_architecture_diagram`  | Architecture supports cycle                 |

### Test Results Summary

| Category             | Tests  | Status          |
| -------------------- | ------ | --------------- |
| Core ReAct Loop      | 3      | ✅ Pass         |
| Tool Call Parsing    | 5      | ✅ Pass         |
| Thread Safety        | 6      | ✅ Pass         |
| Dependency Injection | 4      | ✅ Pass         |
| State Persistence    | 2      | ✅ Pass         |
| UX Event Emission    | 5      | ✅ Pass         |
| ReAct Robustness     | 3      | ✅ Pass         |
| Feedback Loop        | 4      | ✅ Pass         |
| **Total**            | **45** | **✅ All Pass** |

---

## Phase 19.6: The Black Box

> **Status**: Complete (30 new tests)
> **Philosophy**: "Flight data recorder for traceability and resumability."

### 1. Telemetry: Token Usage and Cost Estimation

The Black Box tracks token consumption and estimates costs in real-time.

```python
from agent.core.telemetry import CostEstimator, TokenUsage

# Estimate cost for a call
usage = CostEstimator.estimate(
    text_input="Hello, world!",
    text_output="Hi there!",
    model="claude-3-5-sonnet"
)
print(f"Cost: ${usage.cost_usd:.4f}")  # Cost: $0.0001
```

#### CostEstimator Pricing

| Model             | Input ($/1M) | Output ($/1M) |
| ----------------- | ------------ | ------------- |
| Claude 3.5 Sonnet | $3.00        | $15.00        |
| Claude 3 Opus     | $15.00       | $75.00        |
| GPT-4o            | $5.00        | $15.00        |

#### SessionTelemetry

Accumulates usage across the entire session:

```python
telemetry = SessionTelemetry()
telemetry.add_usage(TokenUsage(cost_usd=0.01))
telemetry.add_usage(TokenUsage(cost_usd=0.02))

print(telemetry.get_cost_rate())  # "$0.90/min"
print(telemetry.get_summary())    # {total_cost_usd: 0.03, ...}
```

### 2. Session Manager: The Recorder

The SessionManager persists all events to JSONL for traceability.

```python
from agent.core.session import SessionManager

# Start new session
session = SessionManager()
session.log("user", "user", "Fix the threading bug")
session.log("agent_action", "coder", "Fixed by adding global declaration")

# Resume from disk
session2 = SessionManager(session_id="abc12345")  # Auto-loads history
```

#### Session Event Types

| Type           | Source         | Description                     |
| -------------- | -------------- | ------------------------------- |
| `user`         | user           | User input                      |
| `router`       | hive_router    | Routing decision with reasoning |
| `agent_action` | coder/reviewer | Agent output and audit results  |
| `tool`         | filesystem/git | Tool execution                  |
| `error`        | orchestrator   | Error events                    |

#### Session File Format

```jsonl
{"id":"uuid","timestamp":1704384000.123,"type":"user","source":"user","content":"Fix the bug"}
{"id":"uuid","timestamp":1704384000.456,"type":"router","source":"hive_router","content":{"target_agent":"coder"},"usage":{"input_tokens":100,"output_tokens":50,"cost_usd":0.001}}
{"id":"uuid","timestamp":1704384000.789,"type":"agent_action","source":"coder","content":"Fixed the bug by..."}
```

### 3. Orchestrator Integration

The Orchestrator now integrates SessionManager at key decision points:

```python
class Orchestrator:
    def __init__(self, session_id=None):
        self.session = SessionManager(session_id=session_id)

    async def dispatch(self, user_query):
        # Log user input
        self.session.log("user", "user", user_query)

        # Route and log decision
        route = await self.router.route_to_agent(user_query)
        self.session.log("router", "hive_router", route_info, usage)

        # Execute and log result
        result = await worker.run(...)
        self.session.log("agent_action", worker.name, result.content)
```

### 4. CLI Commands

```bash
# List all sessions
orchestrator --list-sessions

# Resume a session
orchestrator --resume abc12345

# New session (default)
orchestrator --new
```

### 5. Storage Location

All session data is stored in the project cache:

```
.cache/agent/sessions/
├── {session_id}.jsonl    # Session events
├── latest -> {session_id}.jsonl  # Symlink to latest
└── ...                   # Historical sessions
```

### 6. Test Coverage

| Category         | Tests  | Description                          |
| ---------------- | ------ | ------------------------------------ |
| TokenUsage       | 3      | Model creation and arithmetic        |
| CostEstimator    | 6      | Token counting and cost calculation  |
| SessionTelemetry | 2      | Session-wide accumulation            |
| SessionEvent     | 3      | Event model and serialization        |
| SessionManager   | 12     | Logging, persistence, resumption     |
| Class Methods    | 2      | list_sessions, get_latest_session_id |
| Integration      | 3      | Orchestrator session integration     |
| CLI              | 2      | Argument parsing                     |
| **Total**        | **30** | **✅ All Pass**                      |

### 7. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 19.6: The Black Box                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   User Input                                                         │
│       │                                                              │
│       ▼                                                              │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                    Orchestrator.dispatch()                    │  │
│   │                                                              │  │
│   │   1. Log user input to SessionManager                        │  │
│   │   2. Route via HiveRouter                                    │  │
│   │   3. Log routing decision (with cost estimate)               │  │
│   │   4. Execute agent (Coder/Reviewer)                          │  │
│   │   5. Log agent output (with cost estimate)                   │  │
│   │   6. Return result to user                                   │  │
│   │                                                              │  │
│   └──────────────────────────────────────────────────────────────┘  │
│       │                                                              │
│       │ SessionManager                                              │
│       ▼                                                              │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                    Session Events                             │  │
│   │                                                              │  │
│   │   • user → agent_action (conversation history)               │  │
│   │   • router → agent_action (control flow)                     │  │
│   │   • audit → retry (feedback loop)                            │  │
│   │                                                              │  │
│   └──────────────────────────────────────────────────────────────┘  │
│       │                                                              │
│       ▼                                                              │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                 .cache/agent/sessions/                        │  │
│   │                 {session_id}.jsonl                            │  │
│   │                                                              │  │
│   │   {"type":"user","source":"user","content":"Fix bug"}        │  │
│   │   {"type":"router","source":"hive_router",...}               │  │
│   │   {"type":"agent_action","source":"coder",...}               │  │
│   │                                                              │  │
│   └──────────────────────────────────────────────────────────────┬──┘  │
│                                                          │          │
│   Resumption:                                            ▼          │
│   orchestrator --resume <id>                    ┌──────────────┐   │
│                                              │   Telemetry   │   │
│                                              │   $0.05 spent │   │
│                                              └──────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 8. Why Not Just Use Aider?

| Layer              | Responsibility               | Analogy                |
| ------------------ | ---------------------------- | ---------------------- |
| **Aider**          | Conversation recording (CVR) | Cockpit Voice Recorder |
| **Omni Black Box** | State snapshots (FDR)        | Flight Data Recorder   |

Aider records what was _said_. The Black Box records:

- **Routing decisions** (why coder instead of reviewer?)
- **Control flow** (which iteration of the feedback loop?)
- **Context snapshots** (what did the reviewer see?)
- **Cost accumulation** (how much did this cost?)

### 9. Files Changed

- `agent/core/telemetry.py` - New: TokenUsage, CostEstimator, SessionTelemetry
- `agent/core/session.py` - New: SessionManager, SessionEvent, SessionState
- `agent/core/orchestrator.py` - Added SessionManager integration
- `agent/main.py` - Added `--resume`, `--new`, `--list-sessions` CLI args
- `agent/tests/test_phase19_blackbox.py` - 30 tests

### 10. Test Results

| Suite                   | Tests  | Status          |
| ----------------------- | ------ | --------------- |
| Phase 19.5 (ReAct + UX) | 45     | ✅ Pass         |
| Phase 19.6 (Black Box)  | 30     | ✅ Pass         |
| **Total**               | **75** | **✅ All Pass** |

---

## Phase 19.7: Claude Code Symbiosis

> **Status**: Complete (17 new tests)
> **Philosophy**: "Omni as the strategic brain, Claude Code as the tactical hand."

### Strategic Shift

Instead of building a replacement for Claude Code, Omni now **enhances** it:

| Layer                      | Responsibility                            | Component                |
| -------------------------- | ----------------------------------------- | ------------------------ |
| **Strategic (Omni)**       | Context injection, Routing, Memory, Audit | RAG, MCP Server, Session |
| **Tactical (Claude Code)** | Terminal, Git, Diff, Test Execution       | Official CLI             |

### 1. ClaudeCodeAdapter - The Wrapper

Omni wraps Claude CLI instead of replacing it:

```python
from agent.core.adapters.claude_cli import ClaudeCodeAdapter

adapter = ClaudeCodeAdapter(session=session_manager)
result = await adapter.run_mission(
    mission_brief="Fix the threading bug",
    relevant_files=["agent/core/bootstrap.py"],
    relevant_docs=["docs/threading-guide.md"],
)
```

**Features:**

- Dynamic context injection via temporary files
- Real-time output streaming
- Session tracking (Black Box)
- Cost estimation

### 2. ContextInjector - Dynamic CLAUDE.md

Generates project-specific context for Claude Code:

```python
context = injector.generate_context_file(
    mission_brief="Add authentication",
    relevant_files=["src/auth/models.py"],
    relevant_docs=["docs/security/auth.md"],
)
# Output:
# # Mission Context
# **Task**: Add authentication
# **Generated**: 2026-01-04T10:00:00
#
# ## Relevant Files
# 1. `src/auth/models.py`
#
# ## Documentation References
# - docs/security/auth.md
```

### 3. Omni MCP Server - Skills as Services

Exposes Omni capabilities to any MCP client:

```python
# Tools available to Claude Code, Cursor, Windsurf:
- omni_search_memory()     # Query Phase 16 RAG
- omni_ingest_knowledge()  # Store new knowledge
- omni_request_review()    # Request code review
- omni_get_session_summary() # Get Black Box status
- omni_list_sessions()     # List historical sessions
- omni_generate_context()  # Generate CLAUDE.md
```

### 4. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Omni-Claude Symbiosis                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    Omni (Strategic Layer)                   │   │
│   │                                                             │   │
│   │   ┌─────────────────┐     ┌─────────────────────────────┐  │   │
│   │   │ ContextInjector │────►│ Dynamic CLAUDE.md Generator │  │   │
│   │   └─────────────────┘     └─────────────────────────────┘  │   │
│   │           │                       │                          │   │
│   │           ▼                       ▼                          │   │
│   │   ┌─────────────────────────────────────────────────────┐  │   │
│   │   │              ClaudeCodeAdapter                      │  │   │
│   │   │   - Wraps `claude` CLI                              │  │   │
│   │   │   - Injects context file                            │  │   │
│   │   │   - Tracks session (Black Box)                      │  │   │
│   │   │   - Streams output to TUI                           │  │   │
│   │   └─────────────────────────────────────────────────────┘  │   │
│   │           │                       │                          │   │
│   └───────────┼───────────────────────┼──────────────────────────┘   │
│               │                       │                              │
│               ▼                       ▼                              │
│   ┌─────────────────────────┐  ┌─────────────────────────────────┐  │
│   │ Claude Code CLI         │  │ MCP Clients (Cursor/Windsurf)   │  │
│   │ (Tactical Execution)    │  │                                 │  │
│   │ - Terminal              │  │  - omni_search_memory()         │  │
│   │ - Git/Diff              │  │  - omni_request_review()        │  │
│   │ - Test Runner           │  │  - omni_ingest_knowledge()      │  │
│   └─────────────────────────┘  └─────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 5. Why This Architecture?

| Old Approach                    | New Approach                |
| ------------------------------- | --------------------------- |
| Build a new Agent from scratch  | Wrap existing Claude Code   |
| Reimplement Git/Diff/Test tools | Let Claude Code handle them |
| Single context window           | Dynamic context injection   |
| Proprietary execution           | MCP protocol integration    |

**Benefits:**

- Best-in-class terminal experience (Claude Code)
- Best-in-class code editing (Claude Code)
- Best-in-class project memory (Omni RAG)
- Best-in-class auditing (Omni Reviewer)

### 6. Files Changed

| File                                           | Changes                                 |
| ---------------------------------------------- | --------------------------------------- |
| `agent/core/adapters/claude_cli.py`            | New: ClaudeCodeAdapter, ContextInjector |
| `agent/mcp_server.py`                          | New: FastMCP server with Omni tools     |
| `agent/tests/test_phase19_claude_symbiosis.py` | New: 17 tests                           |
| `agent/main.py`                                | Added `--list-sessions` CLI arg         |
| `agent/core/session.py`                        | Enhanced session tracking               |
| `agent/core/telemetry.py`                      | Enhanced cost estimation                |

### 7. Usage

```bash
# Start MCP Server (for Claude Desktop/Cursor)
python -m agent.mcp_server --stdio

# List sessions
orchestrator --list-sessions

# Resume session
orchestrator --resume abc12345
```

### 8. Test Results

| Suite                         | Tests  | Status          |
| ----------------------------- | ------ | --------------- |
| Phase 19.5 (ReAct + UX)       | 45     | ✅ Pass         |
| Phase 19.6 (Black Box)        | 30     | ✅ Pass         |
| Phase 19.7 (Claude Symbiosis) | 17     | ✅ Pass         |
| **Total**                     | **92** | **✅ All Pass** |

### 9. MCP Tool Reference

| Tool                       | Description        | Parameters                                    |
| -------------------------- | ------------------ | --------------------------------------------- |
| `omni_search_memory`       | Query vector store | `query: str, n_results: int`                  |
| `omni_ingest_knowledge`    | Store documents    | `documents: list, ids: list`                  |
| `omni_request_review`      | Code review        | `code: str, language: str, focus_areas: list` |
| `omni_get_session_summary` | Session status     | None                                          |
| `omni_list_sessions`       | List sessions      | None                                          |
| `omni_generate_context`    | Generate CLAUDE.md | `mission: str, relevant_files: list`          |

### 10. Configuration (settings.yaml)

Context compression and Post-Mortem audit can be configured in `agent/settings.yaml`:

```yaml
# Context Compression (Phase 19.7)
context_compression:
  # Enable/disable context compression globally
  enabled: true

  # Maximum context tokens before compression is triggered
  max_context_tokens: 4000

  # Maximum file size (KB) before truncation
  max_file_size_kb: 50

  # Compression method: "llm" (LLM summary) or "truncate"
  method: "llm"

# Post-Mortem Audit (Phase 19.7)
post_mortem:
  # Enable/disable Post-Mortem audit after Claude Code execution
  enabled: true

  # Confidence threshold for auto-approval
  confidence_threshold: 0.8
```

#### Configuration Options

| Setting                                  | Default | Description                                          |
| ---------------------------------------- | ------- | ---------------------------------------------------- |
| `context_compression.enabled`            | `true`  | Enable/disable LLM-based context compression         |
| `context_compression.max_context_tokens` | `4000`  | Token threshold before compression                   |
| `context_compression.max_file_size_kb`   | `50`    | Max file size in KB before truncation                |
| `context_compression.method`             | `"llm"` | `"llm"` for LLM summary, `"truncate"` for simple cut |
| `post_mortem.enabled`                    | `true`  | Enable/disable automatic review after execution      |
| `post_mortem.confidence_threshold`       | `0.8`   | Min confidence for auto-approval                     |

---

## Phase 20: The Recursive Evolution (The `omni dev` Command)

> **Status**: Complete (15 new tests)
> **Philosophy**: "The system that builds itself."

### Overview

Phase 20 introduces **DevWorkflow** - a self-evolution engine that orchestrates the complete feature development lifecycle. This is the "singularity" moment where Omni gains the ability to autonomously develop features.

### The DevWorkflow Engine

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DevWorkflow (Orchestrator)                       │
│                                                                     │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐      │
│   │VectorMemory │──►│ContextInjector│──►│  ClaudeCodeAdapter  │      │
│   │   (RAG)     │   │  (CLAUDE.md) │   │    (CLI Wrapper)    │      │
│   └─────────────┘   └─────────────┘   └─────────────────────┘      │
│                                      │                              │
│                                      ▼                              │
│   ┌─────────────────────────────────────────────────────────────┐  │
│   │                 ReviewerAgent                               │  │
│   │                 (Post-Mortem Audit)                         │  │
│   └─────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Lifecycle

| Phase | Component | Description |
|-------|-----------|-------------|
| 1. Plan & Retrieve | VectorMemory | RAG-based context retrieval |
| 2. Contextualize | ContextInjector | Dynamic CLAUDE.md generation |
| 3. Execute | ClaudeCodeAdapter | Launch Claude CLI for implementation |
| 4. Verify | ReviewerAgent | Post-Mortem audit of changes |

### Usage

```bash
# Run a feature development task
uv run omni dev "Add a hello-world script to scripts/"

# With session resumption
uv run omni dev --resume abc123 "Add user authentication"
```

### API

```python
from agent.core.workflows.dev_mode import DevWorkflow, create_dev_workflow

# Factory creation
workflow = create_dev_workflow()

# Execute feature development
result = await workflow.run("Add user authentication feature")

print(result)
# {
#   "feature_request": "Add user authentication feature",
#   "success": True,
#   "context_files": [...],
#   "claude_output": "...",
#   "audit_result": {...},
#   "duration_seconds": 45.2
# }
```

### Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| Phase 19.5 (ReAct + UX) | 45 | ✅ Pass |
| Phase 19.6 (Black Box) | 30 | ✅ Pass |
| Phase 19.7 (Claude Symbiosis) | 25 | ✅ Pass |
| Phase 20 (DevWorkflow) | 15 | ✅ Pass |
| **Total** | **115** | **✅ All Pass** |

### Files Changed

| File | Changes |
|------|---------|
| `agent/core/workflows/dev_mode.py` | New: DevWorkflow engine |
| `agent/main.py` | Added `dev` subcommand |
| `agent/tests/test_phase20_dev_mode.py` | New: 15 tests |

### Why This Matters

| Layer | Before Phase 20 | After Phase 20 |
|-------|-----------------|----------------|
| Development | Manual coding | Automated feature development |
| Context | Manual RAG | Automatic context retrieval |
| Review | Manual audit | Automatic post-mortem audit |
| Workflow | Linear | Full lifecycle automation |

### The Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Strategic Layer (Omni)                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • Routing (what to build)                                  │   │
│  │  • RAG (context injection)                                  │   │
│  │  • Planning (mission briefs)                                │   │
│  │  • Auditing (quality gates)                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│                    Tactical Layer (Claude Code)                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • Terminal operations                                      │   │
│  │  • File editing                                             │   │
│  │  • Git operations                                           │   │
│  │  • Test execution                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│                    Infrastructure Layer                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • Vector Memory (persistent knowledge)                     │   │
│  │  • Black Box (session tracking)                             │   │
│  │  • MCP Server (tool exposure)                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Summary

Phase 20 transforms Omni from a helper into a true **Agentic OS** that can:
- Understand feature requests
- Retrieve relevant context automatically
- Execute development via Claude Code
- Verify quality via Post-Mortem audit

This is the foundation for **recursive self-improvement** - Omni can now build features, and those features can make Omni better.
