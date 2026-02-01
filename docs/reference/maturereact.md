# MatureReAct - CCA Architecture Enhancement

> **Status**: Active | **Version**: v2.0 | **Date**: 2025-01-25

## Overview

MatureReAct is an enhanced ReAct (Reasoning + Acting) loop implementation based on **CCA (Confucius Code Agent)** theory. It addresses the **Schema-Execution Gap** problem where LLM-generated tool arguments may not conform to schemas, causing runtime errors that pollute context.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MatureReAct Loop                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Epistemic Gating                                                            │
│            - Task intent verification                                        │
│            - Route decision                                                  │
│            - Block vague tasks before execution                              │
│                                                                              │
│  Structured Reasoning                                                        │
│            - Mandatory <thinking> tags                                       │
│            - Thought and Action separation                                   │
│                                                                              │
│  Resilient Execution                                                         │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  1. Validation Guard                                                    │  │
│  │         Static Pydantic validation → Micro-Correction if invalid       │  │
│  │                                                                         │  │
│  │  2. Loop Detection                                                      │  │
│  │         Tool call hash history → Detect duplicate calls                │  │
│  │                                                                         │  │
│  │  3. Output Truncation                                                   │  │
│  │         Long output compression → Prevent context overflow             │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Hierarchical Memory                                                         │
│            - Short-term: Full tool outputs                                   │
│            - Long-term: Compressed success patterns                          │
│                                                                              │
│  Self-Evolution                                                              │
│            - Harvester: Background learning from sessions                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. ResilientReAct Workflow Engine

Main workflow class integrating all execution features.

```python
from omni.agent.core.omni.react import ResilientReAct

workflow = ResilientReAct(
    engine=inference_client,
    get_tool_schemas=get_schemas_func,
    execute_tool=execute_tool_func,
    max_tool_calls=15,           # Safety limit
    max_consecutive_errors=3,    # Stop after 3 errors
    verbose=True,
)
```

### 2. Validation Guard

Static validation of tool arguments before execution.

```python
from omni.agent.core.omni.react import ArgumentValidator, ValidationResult

schema = {
    "parameters": {
        "required": ["path", "content"],
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        }
    }
}

result = ArgumentValidator.validate(schema, {"path": "/test.txt"})
# ValidationResult(is_valid=True, cleaned_args={...})

result = ArgumentValidator.validate(schema, {})  # Missing required
# ValidationResult(is_valid=False, error_message="Missing required arguments: path, content")
```

**Features:**

- Check required fields
- Type coercion (string to integer)
- Unknown field detection

### 3. OutputCompressor

Prevents context overflow from long tool outputs.

```python
from omni.agent.core.omni.react import OutputCompressor

# Short output - unchanged
result = OutputCompressor.compress("short result")
# "short result"

# Long output - compressed
long_output = "x" * 5000
result = OutputCompressor.compress(long_output)
# "... [Output Truncated: 3000 chars hidden] ..."
# "(Hint: Use a specific tool to read the hidden section if needed)"
```

### 4. Adaptive Skill Projection

Tool filtering based on skill hierarchy.

```python
from omni.agent.core.omni.loop import OmniLoop, TIER_1_ATOMIC, HIGH_LEVEL_KEYWORDS

# Tier 1: Atomic Tools (Hidden when high-level skills exist)
TIER_1_ATOMIC = {
    "omnicell.run_command",  # Unified Nushell bridge for all file/command ops
}

# High-level skill indicators
HIGH_LEVEL_KEYWORDS = ["researcher", "code_tools", "git_smart"]
```

### 5. EpistemicGater

Task intent verification before execution.

```python
from omni.agent.core.omni.loop import EpistemicGater

gater = EpistemicGater()

# Valid task
should_proceed, reason, _ = gater.evaluate("Read file /path/to/main.py")
# (True, "Task appears valid", {...})

# Vague task - blocked
should_proceed, reason, _ = gater.evaluate("do something")
# (False, "Task 'do something' is too vague", {...})
```

### 6. Loop Detection

Prevents infinite loops by tracking tool call hashes.

```python
# First call - executes
tool_hash = workflow._compute_tool_hash("omnicell.run_command", {"cmd": "open /test.py", "ensure_structured": true})
workflow._tool_hash_history.add(tool_hash)

# Same call again - detected as loop
if tool_hash in workflow._tool_hash_history:
    # Skip execution, ask LLM to try different approach
    return "[System Warning] Loop Detected..."
```

### 7. Exit Signal Detection

Strict protocol for task completion.

```python
# Valid completion signals
workflow._check_completion("Task done. EXIT_LOOP_NOW")  # True
workflow._check_completion("TASK_COMPLETED_SUCCESSFULLY")  # True
```

## Configuration

```python
from omni.agent.core.omni.config import OmniLoopConfig

config = OmniLoopConfig(
    max_tokens=128000,              # Context window
    retained_turns=10,              # Conversation turns
    max_tool_calls=20,              # Safety limit
    verbose=False,                  # Debug logging
    suppress_atomic_tools=True,     # Hide low-level tools
    max_tool_schemas=20,            # Max tools in prompt
    max_consecutive_errors=3,       # Error threshold
)
```

## Micro-Correction System

When validation fails, the system generates helpful hints:

```python
# Missing required argument
"Argument Validation Error: Missing required arguments: path, content"

# Type error
"Argument Validation Error: Argument 'lines' must be an integer."

# Runtime error
"Runtime Error: [error details]"
```

## Cognitive Protocol

Injected into system prompts to guide LLM behavior:

```
[COGNITIVE PROTOCOL]
1. DO NOT act as a text editor. Use High-Level Skills first.
2. `skill.discover` is MANDATORY for unknown capabilities.
3. Stop immediately if you are stuck in a loop.
4. Output 'EXIT_LOOP_NOW' only when the user's intent is fully satisfied.
```

## Files

| File                                                        | Description                    |
| ----------------------------------------------------------- | ------------------------------ |
| `packages/python/agent/src/omni/agent/core/omni/react.py`   | ResilientReAct workflow engine |
| `packages/python/agent/src/omni/agent/core/omni/loop.py`    | OmniLoop orchestrator          |
| `packages/python/agent/src/omni/agent/core/omni/config.py`  | Configuration model            |
| `packages/python/agent/tests/unit/test_validation_guard.py` | Unit tests                     |

## Comparison

| Feature              | Traditional ReAct | MatureReAct             |
| -------------------- | ----------------- | ----------------------- |
| Task Validation      | None              | Epistemic Gating        |
| Parameter Validation | Runtime only      | Static + Runtime        |
| Loop Detection       | Basic             | Hash-based with history |
| Output Handling      | Raw truncation    | Smart compression       |
| Error Recovery       | Basic retries     | Micro-correction hints  |
| Skill Projection     | All tools         | Adaptive filtering      |
| Exit Protocol        | Implicit          | Strict (EXIT_LOOP_NOW)  |

## Related Documentation

- [CCA Theory](./cognitive-scaffolding.md)
- [Trinity Architecture](./trinity-architecture.md)
- [Tool Schema Extraction](./odf-rep-protocol.md)
