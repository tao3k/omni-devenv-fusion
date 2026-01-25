# ReAct Workflow

> Reasoning + Acting pattern for tool-augmented LLM

## Overview

ReAct is a pattern that enables LLM to alternate between reasoning (thinking) and acting (tool calls). This document describes the ReAct implementation in Omni-Dev-Fusion.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ReAct Workflow                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐ │
│  │  Think   │───▶│  Act     │───▶│ Execute  │───▶│Obs.  │ │
│  │  (LLM)   │    │  (Tool)  │    │  (Tool)  │    │      │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────┘ │
│       │               │               │               │     │
│       │               │               │               │     │
│       └───────────────┴───────────────┴───────────────┘     │
│                           │                                   │
│                           ▼                                   │
│                  ┌─────────────────┐                         │
│                  │  Loop Until     │                         │
│                  │  No More Tools  │                         │
│                  └─────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## Files

| File                                                       | Description                          |
| ---------------------------------------------------------- | ------------------------------------ |
| `packages/python/agent/src/omni/agent/core/omni/react.py`  | ReAct workflow implementation        |
| `packages/python/agent/src/omni/agent/core/omni/loop.py`   | OmniLoop orchestrator                |
| `packages/python/agent/src/omni/agent/core/omni/config.py` | Configuration (max_tool_calls, etc.) |

## Key Components

### ReActWorkflow Class

```python
class ReActWorkflow:
    def __init__(
        self,
        engine: InferenceClient,
        get_tool_schemas,
        execute_tool,
        max_tool_calls: int = 10,
        verbose: bool = False,
    ):
        """Initialize ReAct workflow."""
        self.engine = engine           # LLM client
        self.get_tool_schemas = get_tool_schemas  # Schema provider
        self.execute_tool = execute_tool  # Tool executor
        self.max_tool_calls = max_tool_calls  # Safety limit
        self.verbose = verbose
        self.step_count = 0
        self.tool_calls_count = 0
```

### Run Loop

```python
async def run(self, task: str, system_prompt: str, messages: list) -> str:
    """Execute ReAct loop."""
    tools = await self.get_tool_schemas()

    while True:
        self.step_count += 1

        # Check safety limit
        if self.tool_calls_count >= self.max_tool_calls:
            break

        # Call LLM with tools
        response = await self.engine.complete(
            system_prompt=system_prompt,
            user_query=task,
            messages=messages,
            tools=tools if tools else None,
        )

        # Check for tool calls
        tool_calls = response.get("tool_calls", [])
        if not tool_calls:
            break  # No more tools needed

        # Execute each tool call
        for tool_call in tool_calls:
            self.tool_calls_count += 1
            result = await self.execute_tool(tool_call)
            messages.append({"role": "user", "content": result})

    return response["content"]
```

## Configuration

| Parameter        | Default | Description                    |
| ---------------- | ------- | ------------------------------ |
| `max_tool_calls` | 20      | Maximum tool calls per session |
| `verbose`        | False   | Enable debug logging           |

```python
# In OmniLoopConfig
class OmniLoopConfig(BaseModel):
    max_tokens: int = 128000
    retained_turns: int = 10
    max_tool_calls: int = 20
    verbose: bool = False
```

## Task Completion Detection

The ReAct loop exits when:

1. **No tool calls in response** - LLM indicates no more tools needed
2. **`✅ Completed` marker detected** - LLM explicitly signals completion
3. **`## Summary` or `## Reflection`** - LLM provides structured completion
4. **Max tool calls reached** - Safety limit enforced

```python
completion_patterns = [
    r"✅\s*Completed",
    r"##\s*Summary",
    r"##\s*Reflection",
    r"Task completed",
]
```

## Issues & Improvements

### Current Issues

| Issue                       | Severity | Description                                              |
| --------------------------- | -------- | -------------------------------------------------------- |
| Early exit on thinking-only | High     | LLM generates `<thinking>` without `[TOOL_CALL:...]`     |
| Path guessing               | High     | LLM guesses file paths instead of using `skill.discover` |
| Tool selection errors       | Medium   | Wrong tool selection without discovery                   |
| No self-reflection          | Low      | LLM doesn't evaluate its own progress                    |

### Potential Improvements

1. **Structured Thinking** - Use JSON schema for thinking output
2. **Planning Phase** - Separate planning from execution
3. **Self-Correction** - Allow LLM to revise previous tool calls
4. **Checkpointing** - Save progress for long-running tasks
5. **Parallel Execution** - Execute independent tools concurrently

### Research Directions

- **Reflexion** (Shinn et al., 2023) - Self-reflection for better task completion
- **AutoGPT/PromptGPT** - Autonomous agent frameworks
- **LangGraph** - Graph-based workflow orchestration
- **MRKL Systems** - Modular reasoning with knowledge retrieval
- **Toolformer** (Schick et al., 2023) - Tool-augmented language models

## Debug Logging

Enable verbose mode to see step-by-step execution:

```bash
uv run omni run "task" -v
```

Sample debug output:

```
DEBUG: ReAct: tools count = 83
DEBUG: ReAct: step=1, tool_calls=0, max=20
DEBUG: ReAct: tool_calls in response = 1
DEBUG: ReAct: tool_names = ['skill.discover']
[1/20] 🔧 skill.discover(intent="read file")
→ {"quick_guide": [...]}
DEBUG: ReAct: step=2, tool_calls=1, max=20
DEBUG: ReAct: tool_calls in response = 1
DEBUG: ReAct: tool_names = ['filesystem.read_files']
[2/20] 🔧 filesystem.read_files(paths=[...])
→ {...}
```

## Related Documentation

- [Omni-Loop](omni-loop.md) - Higher-level orchestrator
- [Intent Protocol](../../assets/prompts/routing/intent_protocol.md) - System prompt for LLM
- [LangGraph Integration](../architecture/langgraph.md) - Graph-based workflow alternative
