# Context Optimization (The Token Diet)

> Agent Layer - Smart Context Management

## Overview

The context optimization system reduces token usage in the CCA loop without losing context quality. It implements tiered memory management with smart pruning.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Agent Core (omni.agent.core.context)                        │
│                                                              │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │ ContextManager  │◄──►│ ContextPruner                   │ │
│  │                 │    │  ┌────────────────────────────┐ │ │
│  │ - add_turn()    │    │  │ Priority Layers:           │ │ │
│  │ - get_context() │    │  │ - System (CRITICAL)        │ │ │
│  │ - prune()       │    │  │ - Recent (HIGH)            │ │ │
│  │ - segment()     │    │  │ - Summary (MEDIUM)         │ │ │
│  │ - compress()    │    │  │ - Overflow (LOW)           │ │ │
│  │ - snapshot()    │    │  └────────────────────────────┘ │ │
│  │ - summary       │    └─────────────────────────────────┘ │
│  └─────────────────┘                                        │
│                                                              │
│  ┌─────────────────┐    ┌────────────────────────────┐    │
│  │ Turn Tracking   │    │ NoteTaker Integration      │    │
│  │                 │    │                             │    │
│  │ - Turn dataclass│    │  - _messages_to_trajectory │    │
│  │ - Serialization │    │  - _extract_summary_content│    │
│  └─────────────────┘    │  - _simple_summarize       │    │
│                         └────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Pruning Strategy

### Priority Layers

| Layer        | Priority | Action              | Rationale                  |
| ------------ | -------- | ------------------- | -------------------------- |
| **System**   | CRITICAL | Always preserved    | Identity, tool definitions |
| **Recent**   | HIGH     | Last N turns intact | Conversation continuity    |
| **Summary**  | MEDIUM   | Insert on prune     | Memory compression         |
| **Overflow** | LOW      | Truncate oldest     | Token budget protection    |

### Configuration

```python
from omni.agent.core.context import ContextManager, ContextPruner, PruningConfig

config = PruningConfig(
    max_tokens=128000,    # Context window budget
    retained_turns=10,    # Keep last 10 turns
    preserve_system=True, # Never drop system prompts
    strategy="truncate",  # or "summarize"
)

ctx = ContextManager(pruner=ContextPruner(config))
```

## Usage

### Basic Conversation

```python
from omni.agent.core.context import ContextManager

ctx = ContextManager()

# Add conversation turns
ctx.add_turn("User message", "Assistant response")

# Get pruned context for LLM
messages = ctx.get_active_context(strategy="pruned")

# Get statistics
stats = ctx.stats()
# {
#     "turn_count": 1,
#     "total_messages": 3,
#     "estimated_tokens": ~150,
#     "pruner_config": {...}
# }
```

### With Summary

```python
# Add many turns
for i in range(20):
    ctx.add_turn(f"User {i}", f"Assistant {i}")

# Prune and insert summary
ctx.prune_with_summary(
    "User discussed project setup, git workflow, and testing"
)

# Context now contains summary + last 10 turns
```

## Smart Context Compression

When conversation history exceeds limits, instead of discarding old messages, the system can **semantically compress** them using the NoteTaker skill.

### Key Components

```python
# packages/python/agent/src/omni/agent/core/context/manager.py

class ContextManager:
    def __init__(self, ...):
        self.summary: str | None = None  # Persistent summary

    def segment(self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Split context into (system, to_summarize, recent)"""

    async def compress(self) -> bool:
        """Compress old context using NoteTaker skill"""
```

### Compression Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ ContextManager.compress()                                       │
├─────────────────────────────────────────────────────────────────┤
│ 1. segment() → (system, to_summarize, recent)                   │
│                                                                 │
│ 2. _messages_to_trajectory() → NoteTaker trajectory format      │
│                                                                 │
│ 3. Call NoteTaker.summarize() → markdown file                   │
│                                                                 │
│ 4. _extract_summary_content() → clean summary text              │
│                                                                 │
│ 5. _apply_compression() → replace old with summary              │
└─────────────────────────────────────────────────────────────────┘
```

### Usage

```python
from omni.agent.core.context import ContextManager

ctx = ContextManager()

# Add many conversation turns
for i in range(20):
    ctx.add_turn(f"User {i}", f"Assistant {i}")

# Segment into 3 parts
system, to_summarize, recent = ctx.segment()
# system: [{"role": "system", "content": "..."}]
# to_summarize: [{"role": "user", "content": "..."}, ...]  # Old messages
# recent: [{"role": "user", "content": "..."}, ...]  # Last N turns

# Async compression with NoteTaker integration
compressed = await ctx.compress()
# Returns True if compression occurred

# Summary is stored and reused
print(ctx.summary)  # "Session discussed project setup, git workflow..."

# Context now contains: system + [Context Summary] + recent
messages = ctx.get_active_context(strategy="pruned")
```

### Fallback Summarization

If NoteTaker is unavailable, uses simple extractive summarization:

```python
def _simple_summarize(self, messages):
    """Extract key content from messages."""
    summaries = []
    for msg in messages:
        role = msg.get("role", "")
        content = str(msg.get("content", ""))
        if len(content) >= 20:  # Skip short messages
            if len(content) > 300:
                content = content[:300] + "..."
            summaries.append(f"[{role}]: {content}")
    return f"Summarized {len(messages)} messages:\n" + "\n".join(summaries[-10:])
```

### API Reference

| Method                       | Type  | Description                                    |
| ---------------------------- | ----- | ---------------------------------------------- |
| `segment()`                  | sync  | Returns `(system, to_summarize, recent)` tuple |
| `compress()`                 | async | Compresses old context, returns bool           |
| `_messages_to_trajectory()`  | sync  | Converts messages to NoteTaker format          |
| `_extract_summary_content()` | sync  | Parses markdown summary output                 |
| `_simple_summarize()`        | sync  | Fallback extractive summarization              |
| `_apply_compression()`       | sync  | Replaces old messages with summary             |

### Serialization

```python
# Save session (includes summary if compressed)
snapshot = ctx.snapshot()
# {
#     "system_prompts": [...],
#     "turns": [...],
#     "turn_count": 5,
#     "summary": "Session discussed project setup...",
#     "pruner_config": {...}
# }

# Restore later
new_ctx = ContextManager()
new_ctx.load_snapshot(snapshot)

# Summary is restored
print(new_ctx.summary)
```

### Statistics

```python
stats = ctx.stats()
# {
#     "turn_count": 5,
#     "system_messages": 2,
#     "total_messages": 15,
#     "estimated_tokens": 1200,
#     "has_summary": True,  # NEW: Indicates compression occurred
#     "pruner_config": {...}
# }
```

## CLI Integration

```python
# packages/python/agent/src/omni/agent/cli/omni_loop.py

from omni.agent.core.omni import OmniLoop

agent = OmniLoop()
result = await agent.run(task, max_steps=10)

# Stats come from ContextManager
stats = agent.context.stats()
```

## Token Estimation

Current implementation uses character-based estimation:

```python
# pruner.py
def estimate_tokens(self, messages):
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    return total_chars // 4  # ~4 chars per token
```

**Future Enhancement**: Replace with tiktoken for accurate counting.

## Related Files

**Core:**

- `packages/python/agent/src/omni/agent/core/context/__init__.py`
- `packages/python/agent/src/omni/agent/core/context/pruner.py`
- `packages/python/agent/src/omni/agent/core/context/manager.py`
- `packages/python/agent/src/omni/agent/core/omni.py`

**Tests:**

- `packages/python/agent/tests/unit/test_context/test_pruner.py`
- `packages/python/agent/tests/unit/test_context/test_manager.py`

**CLI:**

- `packages/python/agent/src/omni/agent/cli/omni_loop.py`
