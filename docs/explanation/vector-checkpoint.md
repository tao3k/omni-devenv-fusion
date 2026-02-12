# Vector Checkpoint System

> Agent Layer - LangGraph Checkpoint Persistence with Semantic Search

## Overview

The vector checkpoint system provides state persistence for LangGraph workflows using LanceDB. It combines traditional checkpoint storage with semantic search capabilities, enabling experience recall across sessions.

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Python Layer (omni.langgraph.checkpoint)                                │
│  ┌────────────────────────┐  ┌─────────────────────────────────────────┐│
│  │ LanceCheckpointer      │  │ RustCheckpointSaver (LangGraph adapter) ││
│  │ - Core checkpoint ops  │  │ - BaseCheckpointSaver interface         ││
│  │ - Semantic search      │  │ - CheckpointTuple NamedTuple returns    ││
│  │ - Rust LanceDB bridge  │  │ - Async method delegation               ││
│  └───────────┬────────────┘  └────────────────┬────────────────────────┘│
└──────────────┼─────────────────────────────────┼────────────────────────┘
               │                                 │
┌──────────────▼─────────────────────────────────▼────────────────────────┐
│ Rust Bindings (omni-core-rs)                                              │
│  - create_checkpoint_store() factory                                     │
│  - CheckpointStore wrapper                                               │
│  - LanceDB operations via PyO3                                           │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────────┐
│ Rust Core (omni-vector crate)                                            │
│  - CheckpointStore: LanceDB operations                                   │
│  - Semantic search with embeddings                                       │
│  - Parent checkpoint chains                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Concepts

### Checkpoint (LangGraph 1.0+ Format)

A checkpoint captures the complete state of a LangGraph workflow:

```python
{
    "v": 2,                         # Checkpoint version (LangGraph 1.0+)
    "id": "abc123hex",              # UUID6 hex (time-ordered)
    "ts": "2024-01-01T00:00:00Z",   # ISO 8601 timestamp
    "channel_values": {...},        # Workflow state (LangGraph 1.0+)
    "channel_versions": {},         # Per-channel version tracking
    "versions_seen": {},            # Node-level version tracking
    "updated_channels": None,       # List of updated channel names
}
```

### CheckpointTuple

LangGraph uses `CheckpointTuple` NamedTuple for checkpoint operations:

```python
from langgraph.checkpoint.base import CheckpointTuple

CheckpointTuple(
    config={"configurable": {"thread_id": "..."}},  # RunnableConfig
    checkpoint={...},                               # Checkpoint dict
    metadata={"source": "input", "step": 0, "writes": {}},
    parent_config=None,                             # Optional parent
    pending_writes=None,                            # Optional pending writes
)
```

### Thread ID

Each workflow session has a unique thread ID for checkpoint isolation:

```python
config = {"configurable": {"thread_id": "research-session-123"}}
```

### Parent Checkpoint Chain

Checkpoints form a history chain via parent links, enabling full state reconstruction:

```text
checkpoint_3 (parent: checkpoint_2)
    └── checkpoint_2 (parent: checkpoint_1)
            └── checkpoint_1 (parent: None)
                    └── Initial State
```

## Architecture

### LanceCheckpointer

Low-level checkpoint operations with semantic search:

```python
from omni.langgraph.checkpoint.lance import LanceCheckpointer

checkpointer = LanceCheckpointer(
    uri=".cache/checkpoints.lance",  # Optional: auto-generated
    dimension=1536,                   # Embedding dimension (OpenAI Ada-002)
)

# Save checkpoint
checkpoint_id = checkpointer.put(
    thread_id="session-123",
    state={"current_plan": "Fix bug in auth", "step": 2},
    checkpoint_id="cp-001",           # Optional: auto-generated UUID6
    metadata={"source": "user_input"}, # Optional metadata
)

# Get latest checkpoint
state = checkpointer.get("session-123")

# Get checkpoint history
history = checkpointer.get_history("session-123", limit=10)

# Delete all checkpoints for a thread
count = checkpointer.delete("session-123")

# Semantic search for similar states
results = checkpointer.search_similar(
    query_vector=embedding,  # 1536-dim vector
    thread_id=None,          # Optional: search specific thread
    limit=5,
    filter_metadata={"success": True},  # Optional filter
)
```

### RustCheckpointSaver

LangGraph-compatible adapter implementing `BaseCheckpointSaver`:

```python
from omni.langgraph.checkpoint.saver import RustCheckpointSaver
from langgraph.graph import StateGraph

# Create saver with custom settings
saver = RustCheckpointSaver(
    table_name="checkpoints",       # Table name for isolation
    uri=".cache/checkpoints.lance", # LanceDB path
    dimension=1536,                 # Embedding dimension
)

# Use with LangGraph
workflow = StateGraph(GraphState)
# ... add nodes and edges ...
app = workflow.compile(checkpointer=saver)

# Run workflow with checkpoints
result = app.invoke(
    initial_state,
    config={"configurable": {"thread_id": "session-123"}}
)
```

#### Interface Methods

The `RustCheckpointSaver` implements the `BaseCheckpointSaver` interface:

| Method                                            | Type  | Description                             |
| ------------------------------------------------- | ----- | --------------------------------------- |
| `get_tuple(config)`                               | sync  | Get latest checkpoint for thread        |
| `put(config, checkpoint, metadata, new_versions)` | sync  | Save checkpoint                         |
| `list(config, limit, filter, before)`             | sync  | List checkpoint history                 |
| `delete_thread(thread_id)`                        | sync  | Delete all checkpoints                  |
| `aget_tuple(config)`                              | async | Async version of get_tuple              |
| `aput(...)`                                       | async | Async version of put                    |
| `alist(...)`                                      | async | Async version of list (async generator) |
| `adelete_thread(thread_id)`                       | async | Async version of delete_thread          |

**Note:** Async methods delegate to sync implementations (LangGraph 1.0+ pattern).

## Semantic Search & Experience Recall

### How It Works

When the system saves a checkpoint, it performs these actions:

1. Serialize the workflow state to JSON
2. Extract searchable text from the state (prioritizes `current_plan` field)
3. Generate an embedding vector using the embedding service
4. Store the embedding alongside the checkpoint in LanceDB

This enables finding semantically similar historical states for experience recall:

```python
# Recall similar successful solutions
from omni.langgraph.checkpoint.lance import LanceCheckpointer

checkpointer = LanceCheckpointer()

# Find similar successful states
similar = checkpointer.search_similar(
    query_vector=current_state_embedding,
    limit=3,
    filter_metadata={"outcome": "success"},
)

for content, metadata, distance in similar:
    print(f"Similarity: {distance:.3f}")
    print(f"State: {content}")
```

### Embedding Generation

The system extracts text from checkpoints for embedding:

```python
# Priority: current_plan field > full state JSON
search_text = state.get("current_plan", "") or json.dumps(state)
```

## Data Model

### LanceDB Schema

| Column     | Type                   | Description                                |
| ---------- | ---------------------- | ------------------------------------------ |
| `id`       | String                 | Unique checkpoint ID                       |
| `vector`   | FixedSizeList<Float32> | State embedding (1536-dim)                 |
| `content`  | String                 | Serialized state JSON                      |
| `metadata` | String                 | JSON metadata (thread_id, timestamp, etc.) |

### CheckpointRecord (Rust)

```rust
pub struct CheckpointRecord {
    pub checkpoint_id: String,      // Unique ID
    pub thread_id: String,          // Session identifier
    pub parent_id: Option<String>,  // Parent checkpoint ID
    pub timestamp: f64,             // Unix timestamp
    pub content: String,            // JSON serialized state
    pub embedding: Option<Vec<f32>>, // Semantic embedding
    pub metadata: Option<String>,   // JSON metadata
}
```

## Configuration

```yaml
# settings.yaml (merged runtime view)
checkpoint:
  path: ".cache/checkpoints.lance"
  dimension: 1536 # OpenAI Ada-002 embedding dimension
  default_limit: 10
```

## Integration Points

### With LangGraph

```python
from omni.langgraph.checkpoint.saver import RustCheckpointSaver
from langgraph.graph import END, StateGraph

# Define state
class WorkflowState(TypedDict):
    messages: Annotated[list[str], operator.add]
    current_plan: str

# Build graph
workflow = StateGraph(WorkflowState)
workflow.add_node("plan", plan_node)
workflow.add_node("execute", execute_node)
workflow.set_entry_point("plan")
workflow.add_edge("plan", "execute")
workflow.add_edge("execute", END)

# Compile with checkpoint saver
app = workflow.compile(
    checkpointer=RustCheckpointSaver()
)

# Run with thread ID
result = app.invoke(
    {"messages": ["Hello"], "current_plan": ""},
    config={"configurable": {"thread_id": "user-session-001"}}
)
```

### With Skills

```python
# assets/skills/git/scripts/smart_commit_workflow.py
from omni.foundation.config.logging import get_logger
from omni.langgraph.checkpoint.saver import RustCheckpointSaver

logger = get_logger("git.smart_commit")

# Import Rust checkpoint saver
try:
    from omni.langgraph.checkpoint.saver import RustCheckpointSaver as _RustCheckpointSaver
    _CHECKPOINT_AVAILABLE = True
    logger.info("RustCheckpointSaver imported successfully")
except ImportError as e:
    _CHECKPOINT_AVAILABLE = False
    _RustCheckpointSaver = None  # type: ignore
    logger.warning(f"RustCheckpointSaver import failed: {e}")

# Compile with checkpointer at module level
if _CHECKPOINT_AVAILABLE and _RustCheckpointSaver:
    try:
        _memory = _RustCheckpointSaver()
        logger.info(f"RustCheckpointSaver initialized: {_memory}")
    except Exception as e:
        logger.error(f"RustCheckpointSaver init failed: {e}")
        _memory = None
else:
    _memory = None

_app = create_sharded_research_graph().compile(checkpointer=_memory)
logger.info(f"Compiled app checkpointer: {_app.checkpointer}")
```

## Performance

| Operation       | Time Complexity | Notes                                 |
| --------------- | --------------- | ------------------------------------- |
| Put Checkpoint  | O(d)            | Single vector insertion               |
| Get Latest      | O(n)            | Linear scan with timestamp comparison |
| Get History     | O(n log n)      | Sort by timestamp                     |
| Semantic Search | O(log n + k)    | ANN with vector index                 |
| Delete Thread   | O(n)            | Linear scan + delete                  |

## Related Files

**Python:**

- `packages/python/agent/src/omni/langgraph/checkpoint/lance.py` - LanceCheckpointer
- `packages/python/agent/src/omni/langgraph/checkpoint/saver.py` - RustCheckpointSaver
- `packages/python/agent/src/omni/langgraph/checkpoint/__init__.py` - Exports
- `assets/skills/researcher/tests/test_researcher.py` - Integration tests

**Rust:**

- `packages/rust/crates/omni-vector/src/checkpoint.rs` - CheckpointStore
- `packages/rust/crates/omni-vector/src/lib.rs` - Main lib
- `packages/rust/bindings/python/src/vector.rs` - PyO3 bindings

**Configuration:**

- `settings.yaml` - Runtime configuration (`assets/settings.yaml` base + `$PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml` override)

---

## Event-Driven Checkpointing (v5.0)

**Location**: `packages/python/core/src/omni/core/services/persistence.py`

The `AsyncPersistenceService` provides fire-and-forget checkpoint saving via the Rust Event Bus.

### Architecture

```
OmniLoop._publish_step_complete()
              ↓
PyGlobalEventBus.publish("agent", "agent/step_complete", payload)
              ↓
KernelReactor (Python async consumer)
              ↓
AsyncPersistenceService.handle_agent_step()
              ↓
Background Worker (async queue)
              ↓
Rust CheckpointStore.save_checkpoint()
```

### Usage

```python
from omni.core.services.persistence import AsyncPersistenceService
from omni.core.kernel.reactor import get_reactor

# Create service with Rust store wrapper
service = AsyncPersistenceService(rust_store)

# Register handler with reactor
reactor = get_reactor()
reactor.register_handler("agent/step_complete", service.handle_agent_step)

# Start service
await service.start()

# Service runs in background - checkpoints queued and saved asynchronously
```

### Service Methods

| Method                     | Description                             |
| -------------------------- | --------------------------------------- |
| `start()`                  | Start background save worker            |
| `stop()`                   | Stop worker and flush pending saves     |
| `handle_agent_step(event)` | Event handler for `agent/step_complete` |
| `is_running`               | Check if service is active              |
| `get_queue_size()`         | Get pending saves count                 |

### Integration with Agent Loop

The agent loop publishes checkpoint events:

```python
# In omni/agent/core/omni/loop.py
try:
    from omni_core_rs import PyGlobalEventBus
    EVENT_BUS_AVAILABLE = True
except ImportError:
    EVENT_BUS_AVAILABLE = False

def _publish_step_complete(self, state: Dict[str, Any]) -> None:
    """Fire-and-forget checkpoint event to Rust Event Bus."""
    if not EVENT_BUS_AVAILABLE:
        return

    self.current_step += 1
    payload = json.dumps({
        "thread_id": self.session_id,
        "step": self.current_step,
        "state": state,
        "timestamp": time.time(),
    })

    PyGlobalEventBus.publish("agent", "agent/step_complete", payload)
```
