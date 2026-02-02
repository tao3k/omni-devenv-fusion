# Cognitive Re-anchoring Mechanism

> Anti-Fragile Workflow with Time-Travel Recovery

## Overview

In long interactive sessions, Large Language Models (LLMs) often suffer from "context drift" or "protocol forgetting." Even if a skill's rules were initially loaded via `SKILL.md`, they can be diluted by extensive dialogue history, leading the LLM to revert to default (often unoptimized or unsafe) behaviors.

The **Cognitive Re-anchoring** mechanism in `omni-dev-fusion` solves this by transforming the Security Gatekeeper from a passive "permission checker" into an active "cognitive anchor."

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AutoFixLoop                                  │
├─────────────────────────────────────────────────────────────────────┤
│  1. Execute workflow                                                │
│  2. Validate output                                                 │
│  3. If failed: Context Pruning (compress history)                   │
│  4. TimeTravel to previous checkpoint                               │
│  5. Apply correction patch                                          │
│  6. Retry from forked state                                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     ContextPruner                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐   ┌──────────────────────────────────────────┐   │
│  │ Rust        │   │ Message Compression Strategy:            │   │
│  │ tokenizer   │   │  1. Always keep system messages          │   │
│  │ (20-100x    │   │  2. Keep last N*2 messages (working mem) │   │
│  │  faster)    │   │  3. Truncate tool outputs in archive     │   │
│  └─────────────┘   └──────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ "Lesson Learned" Summary (instead of full error trace)       │  │
│  │                                                              │  │
│  │ [AUTO-FIX RECOVERY]                                          │  │
│  │ Previous attempt failed: ValueError: invalid input           │  │
│  │ We have rolled back to a previous checkpoint.                │  │
│  │ Please analyze the error and try a different approach.       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Protocol Extraction

When a `UniversalScriptSkill` is loaded, it automatically splits the `SKILL.md` file into metadata (YAML) and **Protocol Content** (Markdown instructions).

### 2. Drift Detection

The `SecurityValidator` (Gatekeeper) monitors every tool call. If the LLM attempts to use a tool that is not authorized for the active skill (e.g., trying to use `terminal.run_command` instead of the mandated `git.smart_commit`), the Gatekeeper identifies this as a **Protocol Drift**.

### 3. Active Re-anchoring (Reactive)

Instead of returning a generic error, the Gatekeeper captures the `protocol_content` of the active skill and injects it into a `SecurityError`. This forces the LLM to re-read its instructions at the exact moment of failure.

### 4. Proactive Overload Management (Cognitive Load Control)

To support massive skill libraries (100-1000+ skills), the Gatekeeper tracks the number of **active skills** in the current session.

- **Threshold**: Defaults to 5 active skills.
- **Proactive Warning**: When the threshold is exceeded, even **successful** tool calls will include a `[COGNITIVE LOAD WARNING]`.
- **Injection Mechanism**:
  - For string results: Appended to the end.
  - For dictionary results: Injected into the `message` field or a specialized `_cognition` metadata field.
- **Reset**: Can be cleared via `validator.reset_active_skills()` during session cleanup.

## Context Pruning for AutoFix Recovery

When AutoFixLoop triggers recovery, it uses **Rust-accelerated ContextPruner** to compress the message history before retry.

### Key Features

| Feature                    | Description                                        |
| -------------------------- | -------------------------------------------------- |
| **Rust Tokenizer**         | 20-100x faster token counting via `omni-tokenizer` |
| **Smart Compression**      | Keep system + recent, truncate tool outputs        |
| **Lesson Learned**         | Compressed error summary instead of full trace     |
| **Model-Specific Configs** | Optimized for GPT-4o, GPT-4, GPT-3.5-turbo         |

### Usage

```python
from omni.agent.core.context.pruner import ContextPruner, create_pruner_for_model

# Create pruner (auto-detects Rust bindings)
pruner = ContextPruner(window_size=4, max_tool_output=500)

# Compress messages for AutoFix retry
compressed = pruner.prune_for_retry(messages, error)
```

### Model-Specific Configuration

```python
from omni.agent.core.context import create_pruner_for_model

# Optimized for different model context windows
gpt4o_pruner = create_pruner_for_model("gpt-4o")   # 120K tokens, 6 turns
gpt4_pruner = create_pruner_for_model("gpt-4")     # 8K tokens, 4 turns
gpt35_pruner = create_pruner_for_model("gpt-3.5-turbo")  # 16K tokens, 8 turns
```

### Compression Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Message Flow                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Input: [System, Tool(1000 chars), Tool(800 chars), ...]   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. Extract System Messages (Always Keep)            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. Identify Working Memory (Last N*2 messages)      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 3. Archive = Middle Messages                        │   │
│  │    - Truncate tool outputs > max_tool_output        │   │
│  │    - Replace with preview + "[... N chars hidden]"  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 4. Add Recovery Message                             │   │
│  │    "[AUTO-FIX RECOVERY] Previous attempt failed..." │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  Output: [System, Tool(500 chars + note), ..., Working]    │
└─────────────────────────────────────────────────────────────┘
```

### Performance

| Metric              | Value                               |
| ------------------- | ----------------------------------- |
| Token counting      | 20-100x faster than tiktoken Python |
| Message compression | ~50-80% reduction in tokens         |
| Recovery overhead   | <10ms for typical conversation      |

## Advanced Permission Handling

The system supports **Wildcard Permission Projection**:

- `service:*`: Grants access to all methods in a service (e.g., `filesystem:*`).
- `service:method`: Specific method access.
- Correctly resolves both `:` (YAML standard) and `.` (MCP tool standard) delimiters.

## Technical Implementation

### Gatekeeper-based Re-anchoring

| Component         | Location                                                  |
| ----------------- | --------------------------------------------------------- |
| Security Module   | `packages/python/core/src/omni/core/security/__init__.py` |
| Universal Skills  | `packages/python/core/src/omni/core/skills/universal.py`  |
| Kernel Dispatcher | `packages/python/core/src/omni/core/kernel/engine.py`     |

### AutoFixLoop with Context Pruning

| Component              | Location                                                            |
| ---------------------- | ------------------------------------------------------------------- |
| AutoFixLoop            | `packages/python/agent/src/omni/agent/core/time_travel/recovery.py` |
| TimeTraveler           | `packages/python/agent/src/omni/agent/core/time_travel/traveler.py` |
| ContextPruner (Python) | `packages/python/agent/src/omni/agent/core/context/pruner.py`       |
| omni-tokenizer (Rust)  | `packages/rust/crates/omni-tokenizer/src/lib.rs`                    |
| Python Bindings        | `packages/rust/bindings/python/src/tokenizer.rs`                    |

### AutoFixLoop API

```python
from omni.agent.core.time_travel.recovery import AutoFixLoop
from omni.agent.core.context.pruner import ContextPruner

# Create components
pruner = ContextPruner(window_size=4)

# AutoFixLoop handles recovery automatically
fixer = AutoFixLoop(
    traveler=time_traveler,
    pruner=pruner,
    max_retries=2,
)

# Execute with automatic recovery
result = await fixer.run(
    graph,
    input_data,
    config,
    validator=lambda x: x.get("success"),
)
```

### Events Emitted

| Event             | Description                     |
| ----------------- | ------------------------------- |
| `autofix/attempt` | When a retry attempt starts     |
| `autofix/prune`   | When context pruning is applied |
| `autofix/travel`  | When time travel is triggered   |
| `autofix/recover` | When recovery is successful     |
| `autofix/fail`    | When all retries are exhausted  |
