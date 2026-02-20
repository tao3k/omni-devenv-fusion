# Cognitive Architecture

> **Status**: Active | **Version**: v1.0 | **Date**: 2024-XX-XX

## Overview

Cognitive Architecture introduces **Dependency Injection** and **ReAct Loop** capabilities to the agent system, giving CoderAgent a "brain" (LLM inference) and "hands" (OmniCell tools).

## The Problem

Before Cognitive Architecture, CoderAgent was like a worker without tools:

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
│                         Cognitive Architecture                       │
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

## Summary

| Concept     | Before Cognitive Architecture | After Cognitive Architecture   |
| ----------- | ----------------------------- | ------------------------------ |
| Cognition   | Placeholder text              | Real LLM inference             |
| Tools       | N/A                           | read_file, write_file, etc.    |
| Execution   | Single pass                   | ReAct loop (Think→Act→Observe) |
| Context     | Shared with main session      | Isolated per task              |
| Agent State | Empty shell                   | Functional worker              |

## The Black Box (Telemetry & Session)

### Telemetry: Token Usage and Cost Estimation

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

```python
telemetry = SessionTelemetry()
telemetry.add_usage(TokenUsage(cost_usd=0.01))
telemetry.add_usage(TokenUsage(cost_usd=0.02))

print(telemetry.get_cost_rate())  # "$0.90/min"
print(telemetry.get_summary())    # {total_cost_usd: 0.03, ...}
```

### Session Manager: The Recorder

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

### Feedback Loop: Coder → Reviewer → Coder

```
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

## Related Documentation

- [Trinity Architecture](./system-layering.md)
- [Cognitive Scaffolding](./cognitive-scaffolding.md)
- [Memory Mesh](../human/architecture/memory-mesh.md)
