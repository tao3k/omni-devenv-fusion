# Context Optimization (The Token Diet)

> Agent Layer - Rust-accelerated Context Window Management
> AutoFix Recovery with Cognitive Re-anchoring

## Overview

The context optimization system reduces token usage in the CCA loop without losing context quality. It implements tiered memory management with smart pruning using **Rust-accelerated token counting** (20-100x faster than Python tiktoken).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ Agent Core (omni.agent.core.context)                                │
│                                                                      │
│  ┌─────────────────┐    ┌─────────────────────────────────────────┐ │
│  │ ContextPruner   │◄──►│ omni-tokenizer (Rust)                   │ │
│  │                 │    │  ┌────────────────────────────┐        │ │
│  │ - count_tokens()│    │  │ - count_tokens()          │        │ │
│  │ - compress()    │    │  │ - ContextPruner (Rust)    │        │ │
│  │ - prune_for_retry│   │  │  - Message struct         │        │ │
│  │ - estimate_compression│ └────────────────────────────┘        │ │
│  └─────────────────┘    └─────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────┐    ┌────────────────────────────────────────┐  │
│  │ AutoFixLoop     │    │ TimeTraveler                          │  │
│  │                 │    │                                       │  │
│  │ - run()         │    │  - fork_and_correct()                 │  │
│  │ - run_streaming │    │  - get_timeline()                     │  │
│  └─────────────────┘    └────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Components

### ContextPruner

Rust-accelerated context pruner for LangGraph workflows.

```python
from omni.agent.core.context.pruner import ContextPruner

# Create pruner with custom settings
pruner = ContextPruner(
    window_size=4,           # Last N*2 messages kept as working memory
    max_tool_output=500,     # Max characters for tool outputs in archive
    max_context_tokens=8000, # Maximum total tokens
)
```

#### Key Methods

| Method                                 | Type | Description                             |
| -------------------------------------- | ---- | --------------------------------------- |
| `count_tokens(text)`                   | sync | Count tokens in text (Rust-accelerated) |
| `count_messages(messages)`             | sync | Count tokens in message list            |
| `compress_messages(messages)`          | sync | Compress with smart truncation          |
| `prune_for_retry(messages, error)`     | sync | Create pruned context for AutoFix       |
| `truncate_middle(text, max_tokens)`    | sync | Head + tail preservation                |
| `estimate_compression_ratio(messages)` | sync | Measure compression effectiveness       |

### Message Compression Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                 compress_messages() Flow                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: [System, Tool(2KB), Tool(1KB), User, Assistant, ...]   │
│                                                                  │
│  ┌───────────────────────────────────────────────────────┐      │
│  │ Step 1: Partition                                      │      │
│  │   - System messages (ALWAYS PRESERVE)                 │      │
│  │   - Other messages (archive + working)                │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌───────────────────────────────────────────────────────┐      │
│  │ Step 2: Identify Safety Zone                          │      │
│  │   - Keep last N*2 messages as working memory         │      │
│  │   - Remaining messages become archive                │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌───────────────────────────────────────────────────────┐      │
│  │ Step 3: Process Archive (Compress Tool Outputs)       │      │
│  │   - If tool output > max_tool_output:                │      │
│  │     preview + "[... N chars hidden to save context]" │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                  │
│  ┌───────────────────────────────────────────────────────┐      │
│  │ Step 4: Reassemble                                    │      │
│  │   [System] + [Processed Archive] + [Working Memory]  │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                  │
│  Output: [System, Tool(500 chars + note), User, Assistant]     │
└─────────────────────────────────────────────────────────────────┘
```

## AutoFixLoop Integration

The `AutoFixLoop` class provides anti-fragile workflow execution with automatic recovery.

```python
from omni.agent.core.time_travel.recovery import AutoFixLoop
from omni.agent.core.context.pruner import ContextPruner
from omni.agent.core.time_travel.traveler import TimeTraveler

# Create components
pruner = ContextPruner(window_size=4)
traveler = TimeTraveler(checkpointer)
fixer = AutoFixLoop(traveler, pruner, max_retries=2)

# Execute with automatic recovery
result = await fixer.run(
    graph,
    {"task": "write code"},
    config,
    validator=lambda x: x.get("success"),
)
```

### AutoFix Recovery Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AutoFixLoop.run()                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Execute workflow                                                │
│  2. Validate output                                                 │
│  3. If failed:                                                      │
│     a. Get current state                                            │
│     b. Prune context (prune_for_retry)                             │
│     c. Generate "Lesson Learned" summary                           │
│     d. TimeTravel to checkpoint N-1                                 │
│     e. Apply correction patch                                       │
│     f. Retry from forked state                                      │
│  4. Repeat until success or max_retries                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Lesson Learned Summary

Instead of full error traces, creates compressed summaries:

```python
[AUTO-FIX RECOVERY]
Previous attempt failed: ValueError: invalid input
We have rolled back to a previous checkpoint.
Please analyze the error and try a different approach.
Consider what went wrong and how to avoid the same mistake.
```

## Model-Specific Configuration

```python
from omni.agent.core.context.pruner import create_pruner_for_model

# Optimized configurations for different models
configs = {
    "gpt-4o": {"window": 6, "max_tokens": 120000},
    "gpt-4-turbo": {"window": 6, "max_tokens": 128000},
    "gpt-4": {"window": 4, "max_tokens": 8192},
    "gpt-3.5-turbo": {"window": 8, "max_tokens": 16384},
}

pruner = create_pruner_for_model("gpt-4o")
```

## Performance

| Operation             | Rust           | Python Fallback |
| --------------------- | -------------- | --------------- |
| Token counting        | 20-100x faster | ~4 chars/token  |
| Message compression   | <1ms           | <5ms            |
| Context prune (retry) | <5ms           | <20ms           |

## Usage Examples

### Basic Context Pruning

```python
from omni.agent.core.context.pruner import ContextPruner

pruner = ContextPruner(window_size=4, max_tool_output=500)

messages = [
    {"role": "system", "content": "You are a coding assistant."},
    {"role": "tool", "content": "..." * 1000},  # Long tool output
    {"role": "user", "content": "Fix the bug"},
    {"role": "assistant", "content": "I'll help you fix the bug."},
]

# Compress messages
compressed = pruner.compress_messages(messages)
# Result: [System, Tool(500 + note), User, Assistant]
```

### AutoFix Recovery

```python
from omni.agent.core.time_travel.recovery import AutoFixLoop

fixer = AutoFixLoop(traveler, pruner, max_retries=2)

try:
    result = await fixer.run(
        graph,
        input_data,
        config,
        validator=is_valid_result,
    )
except Exception as e:
    print(f"All retries failed: {e}")
```

### Compression Ratio Estimation

```python
from omni.agent.core.context.pruner import ContextPruner

pruner = ContextPruner()
messages = [...]  # Your message history

original_tokens = pruner.count_messages(messages)
compressed = pruner.compress_messages(messages)
compressed_tokens = pruner.count_messages(compressed)

ratio = pruner.estimate_compression_ratio(messages)
print(f"Compression ratio: {ratio:.2f}x")
# Example output: "Compression ratio: 2.3x"
```

## Fallback Mode

When Rust bindings are unavailable (e.g., during development), ContextPruner automatically falls back to Python estimation:

```python
WARNING:omni.agent.core.context.pruner:ContextPruner falling back to estimation mode
```

- Token counting: ~4 characters per token estimation
- Compression: Python-based message processing

## Related Files

**Core Implementation:**

- `packages/python/agent/src/omni/agent/core/context/pruner.py`
- `packages/python/agent/src/omni/agent/core/time_travel/recovery.py`
- `packages/rust/crates/omni-tokenizer/src/lib.rs`
- `packages/rust/crates/omni-tokenizer/src/pruner.rs`
- `packages/rust/bindings/python/src/tokenizer.rs`

**Tests:**

- `packages/python/agent/tests/unit/test_context/test_pruner.py`

**Rust Tests:**

- `packages/rust/crates/omni-tokenizer/tests/test_tokenizer.rs`

## See Also

- [Cognitive Re-anchoring](cognitive-reanchoring.md)
- [AutoFix Loop Scenario Test](../testing/scenario-test-driven-autofix-loop.md)
- [Rust Crates](../architecture/rust-crates.md)
- [Pensieve / StateLM: Implications for Omni-Dev-Fusion](pensieve-statelm-implications.md) — stateful context self-management (arXiv:2602.12108)
