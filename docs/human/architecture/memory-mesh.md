# Memory Mesh

> Episodic Memory for Self-Learning Agents
> **Status**: Active
> **Version**: v1.1 | 2026-01-25 (Self-Evolution Integration)

## Overview

The Memory Mesh completes the **Cognitive Trinity** by adding episodic memory - the ability for the Agent to remember past experiences and learn from them.

### Cognitive Trinity

| Component     | Capability                     | Data Source                    |
| ------------- | ------------------------------ | ------------------------------ |
| **Skills**    | "I know how to do"             | `assets/skills/*/scripts/*.py` |
| **Knowledge** | "I know what that is"          | `docs/`, `assets/specs/`       |
| **Memory**    | "I remember doing that before" | VectorDB (LanceDB)             |

### Architecture

```
                    ┌─────────────────────────────────────┐
                    │         The Memory Mesh             │
                    │    (Episodic Memory System)         │
                    └─────────────────────────────────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          ▼                         ▼                         ▼
   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐
   │   Skills    │          │  Knowledge  │          │   Memory    │
   │   Table     │          │   Table     │          │   Table     │
   └─────────────┘          └─────────────┘          └─────────────┘
   └─────────────────────────┴─────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────────┐
                    │        AdaptiveLoader               │
                    │  Core + Dynamic Tool Loading        │
                    │  + Memory Context Injection         │
                    └─────────────────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────────┐
                    │           Agent Runtime             │
                    │    (Learns from past experiences)   │
                    └─────────────────────────────────────┘
```

---

## 1. Type Definitions

**File**: `packages/python/agent/src/omni/agent/core/memory/types.py`

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class InteractionLog(BaseModel):
    """
    Episode: Describes a single agent interaction.

    Stores structured "Input -> Tool -> Result -> Reflection" chains.
    These records are vectorized and stored for retrieving relevant
    historical experiences.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique UUID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(), description="ISO 8601 timestamp"
    )

    # Context - User intent
    user_query: str = Field(..., description="User's original intent/query")
    session_id: Optional[str] = Field(None, description="Session identifier for grouping")

    # Action - Execution trace
    tool_calls: List[str] = Field(
        default_factory=list, description="List of tools that were called"
    )

    # Consequence - Execution result
    outcome: str = Field(..., description="'success' or 'failure'")
    error_msg: Optional[str] = Field(None, description="Error message if failed")

    # Knowledge - Lesson learned (core retrieval field)
    reflection: str = Field(..., description="Synthesized lesson learned from this interaction")

    def to_vector_record(self) -> dict:
        """
        Convert to LanceDB storage format.

        Returns:
            Dict with fields:
            - id: Record ID
            - text: Combined text for embedding (query + reflection)
            - metadata: Full JSON dump of the record
            - type: Record type ("memory")
            - timestamp: ISO timestamp
            - outcome: success/failure
        """
        # Build text for vectorization
        # Combine user query and reflection for matching "similar problems" and "solutions"
        text_parts = [f"Query: {self.user_query}", f"Reflection: {self.reflection}"]

        if self.error_msg:
            text_parts.append(f"Error: {self.error_msg}")

        text = "\n".join(text_parts)

        return {
            "id": self.id,
            "text": text,
            "metadata": self.model_dump(mode="json"),
            "type": "memory",
            "timestamp": self.timestamp,
            "outcome": self.outcome,
        }

    def to_summary(self) -> str:
        """Generate a short summary string for logging output."""
        status = "OK" if self.outcome == "success" else "FAIL"
        return f"[{status}] {self.user_query[:50]} -> {self.reflection[:50]}"


class MemoryQuery(BaseModel):
    """Memory query parameters."""

    query: str = Field(..., description="Search query")
    limit: int = Field(default=3, ge=1, le=10, description="Max results")
    outcome_filter: Optional[str] = Field(None, description="Filter by outcome")
```

---

## 2. Memory Manager

**File**: `packages/python/agent/src/agent/core/memory/manager.py`

### Core Responsibilities

- Write structured interaction logs to vector store
- Retrieve relevant past experiences via semantic search
- Provide high-level API for memory operations

### API Reference

```python
class MemoryManager:
    """Manages episodic memory storage and retrieval."""

    async def add_experience(
        self,
        user_query: str,
        tool_calls: List[str],
        outcome: str,
        reflection: str,
        error_msg: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str | None:
        """
        Record a new experience to memory.

        Args:
            user_query: The user's original query/intent
            tool_calls: List of tools that were called
            outcome: "success" or "failure"
            reflection: Synthesized lesson learned
            error_msg: Error message if outcome was failure
            session_id: Optional session identifier

        Returns:
            The ID of the created record, or None if failed
        """

    async def recall(
        self,
        query: str,
        limit: int = 3,
        outcome_filter: Optional[str] = None,
    ) -> List[InteractionLog]:
        """
        Retrieve relevant past experiences.

        Args:
            query: Natural language query describing the current situation
            limit: Maximum number of memories to return (default: 3, max: 10)
            outcome_filter: Optional filter for "success" or "failure"

        Returns:
            List of matching InteractionLog objects, sorted by relevance
        """

    async def get_recent(self, limit: int = 5) -> List[InteractionLog]:
        """Get the most recent memories regardless of content."""

    async def count(self) -> int:
        """Get total number of memories stored."""
```

---

## 3. Runtime Interceptor

**File**: `packages/python/agent/src/agent/core/memory/interceptor.py`

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MemoryInterceptor (Runtime Hook)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Task Execution                                                             │
│       ↓                                                                    │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │  before_execution(user_input)                       │                   │
│  │  - Retrieve relevant memories from vector store     │ ← Context Injection│
│  │  - Return formatted memories for LLM context        │                   │
│  └─────────────────────────────────────────────────────┘                   │
│       ↓                                                                    │
│  Agent receives memories in system prompt                                   │
│       ↓                                                                    │
│  Task Execution (with memory context)                                       │
│       ↓                                                                    │
│  ┌─────────────────────────────────────────────────────┐                   │
│  │  after_execution(user_input, tool_calls, success)   │                   │
│  │  - Generate reflection (success summary or error)   │ ← Memory Recording│
│  │  - Store experience in vector store                 │                   │
│  └─────────────────────────────────────────────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### API Reference

```python
class MemoryInterceptor:
    """Runtime interceptor for automatic memory capture and injection."""

    async def before_execution(
        self,
        user_input: str,
        limit: int = 3,
    ) -> List[InteractionLog]:
        """
        Retrieve relevant memories before task execution.

        Args:
            user_input: The current user query/intent
            limit: Maximum memories to retrieve (default: 3)

        Returns:
            List of relevant InteractionLog objects
        """

    async def after_execution(
        self,
        user_input: str,
        tool_calls: List[str],
        success: bool,
        error: Optional[str] = None,
        reflection: Optional[str] = None,
    ) -> str | None:
        """
        Record experience after task execution.

        Args:
            user_input: The original user query/intent
            tool_calls: List of tools that were called
            success: Whether the task succeeded
            error: Error message if failed
            reflection: Optional pre-generated reflection

        Returns:
            ID of the created memory record, or None if failed
        """

    async def get_memory_interceptor() -> MemoryInterceptor:
        """Get the singleton MemoryInterceptor instance."""
```

---

## 4. VectorStore Integration

**File**: `packages/python/agent/src/agent/core/vector_store.py`

### New Methods

```python
class VectorMemory:
    async def add_memory(self, record: dict[str, Any]) -> bool:
        """
        Add a single memory record to the memory table.

        Args:
            record: Dictionary with fields:
                - id: Unique identifier
                - text: Text for embedding
                - metadata: JSON-serializable metadata
                - outcome: "success" or "failure"
                - timestamp: ISO timestamp

        Returns:
            True if successful, False otherwise
        """

    async def search_memory(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search memories using semantic similarity.

        Args:
            query: Natural language query
            limit: Maximum results (default: 5)

        Returns:
            List of memory records with:
            - id: Record ID
            - content: Full text content
            - distance: Similarity score (lower = better)
            - metadata: Parsed metadata dict
            - outcome: success/failure
        """
```

### VectorTable Enum

**File**: `packages/python/agent/src/agent/core/types.py`

```python
from enum import Enum

class VectorTable(str, Enum):
    """Vector store table names."""
    SKILLS = "skills"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"  # Episodic memory
```

---

## 5. AdaptiveLoader Integration

**File**: `packages/python/agent/src/agent/core/adaptive_loader.py`

### New Methods

```python
class AdaptiveLoader:
    async def get_relevant_memories(
        self,
        user_query: str,
        limit: int = 3,
    ) -> str:
        """
        Get relevant past experiences for context injection.

        The Memory Mesh - Retrieves similar past experiences
        to help the agent learn from previous interactions.

        Returns:
            Formatted string of memories for context injection
        """

    async def record_experience(
        self,
        user_query: str,
        tool_calls: list[str],
        success: bool,
        error: str | None = None,
    ) -> str | None:
        """
        Record a new experience to memory.

        Called after task execution to store the experience.

        Returns:
            ID of the created memory record
        """
```

### Context Injection Example

```python
# AdaptiveLoader.get_context_tools() now includes:
async def get_context_tools(self, user_query: str, ...) -> list[dict[str, Any]]:
    # ... existing core + dynamic tool loading ...

    # Inject relevant memories
    memories = await self.get_relevant_memories(user_query, limit=3)
    if memories:
        context += f"\n\n## Relevant Past Experience:\n{memories}"

    return context
```

---

## 6. Usage Examples

### Direct Python API

```python
from omni.agent.core.memory.manager import get_memory_manager

mm = get_memory_manager()

# Record a failure experience
await mm.add_experience(
    user_query="git commit fails due to lock file",
    tool_calls=["git.commit"],
    outcome="failure",
    error_msg="fatal: Unable to create lock",
    reflection="Git lock error solved by removing .git/index.lock"
)

# Record a success experience
await mm.add_experience(
    user_query="search project documentation",
    tool_calls=["knowledge.search_project_knowledge"],
    outcome="success",
    reflection="Hybrid search with keywords yields better results"
)

# Recall relevant experiences
memories = await mm.recall("git commit lock file")
for m in memories:
    print(f"[{m.outcome}] {m.reflection}")
```

### Memory Interceptor Integration

```python
from omni.agent.core.memory.interceptor import get_memory_interceptor

interceptor = get_memory_interceptor()

# Before execution: Get relevant memories
memories = await interceptor.before_execution(
    user_input="How do I fix git lock error?",
    limit=3
)
# memories injected into system prompt

# After execution: Record experience
await interceptor.after_execution(
    user_input="How do I fix git lock error?",
    tool_calls=["git.commit", "filesystem.read_files"],
    success=True,
    reflection="Removed .git/index.lock file to resolve lock error"
)
```

---

## 7. File Structure

```
packages/python/agent/src/omni/agent/core/
├── types.py                    # VectorTable enum (MEMORY = "memory")
├── vector_store.py             # add_memory(), search_memory()
├── adaptive_loader.py          # get_relevant_memories(), record_experience()
└── memory/
    ├── __init__.py
    ├── types.py                # InteractionLog, MemoryQuery
    ├── manager.py              # MemoryManager class
    └── interceptor.py          # MemoryInterceptor class

packages/python/agent/src/omni/agent/tests/unit/
└── test_memory_mesh.py         # Unit tests for Memory Mesh
```

---

## 8. Comparison: Knowledge vs Memory

| Aspect               | Knowledge (Docs)               | Memory (Experiences)           |
| -------------------- | ------------------------------ | ------------------------------ |
| **Purpose**          | Static documentation search    | Dynamic experience retrieval   |
| **Data Source**      | Markdown files (docs/, specs/) | Agent execution history        |
| **Update Frequency** | Manual sync or file change     | Real-time (per task)           |
| **Key Method**       | `search_knowledge_hybrid()`    | `recall()`, `add_experience()` |
| **Data Model**       | DocRecord, DocChunk            | InteractionLog                 |
| **Context**          | "What is this?"                | "What happened before?"        |

---

## 9. Testing

```bash
# Test memory write/read cycle
python3 -c "
import asyncio
from agent.core.memory.manager import get_memory_manager

async def test():
    mm = get_memory_manager()

    # Write
    await mm.add_experience(
        user_query='git commit fails with lock',
        tool_calls=['git.commit'],
        outcome='failure',
        error_msg='index.lock exists',
        reflection='Solution: rm .git/index.lock'
    )
    print('Memory written!')

    # Read
    memories = await mm.recall('git commit lock')
    for m in memories:
        print(f'[{m.outcome}] {m.reflection}')

asyncio.run(test())
"

# Run unit tests
uv run pytest packages/python/agent/src/agent/tests/unit/test_memory_mesh.py -v
```

---

## 10. Future Enhancements

- [ ] Auto-reflection generation using LLM
- [ ] Session-based memory grouping
- [ ] Memory decay for stale experiences
- [ ] Cross-session memory consolidation
- [ ] Memory quality scoring

---

## 11. Self-Evolution Integration

The Memory Mesh integrates with the Self-Evolution system for continuous improvement.

### Fast Path: Rule Extraction

User corrections and preferences are automatically extracted and stored:

```python
# From omni.agent.core.evolution.harvester
class Harvester:
    async def extract_lessons(self, history: List[Dict]) -> Optional[ExtractedLesson]:
        """Extract rules/preferences from user feedback."""
        correction_patterns = ["no,", "not", "wrong", "don't", "instead", "use"]
        relevant = [m for m in history if any(p in m.content for p in correction_patterns)]
        # LLM extracts the underlying rule...
        return ExtractedLesson(rule="Always use async for I/O", domain="python_style")
```

### Memory Recall in Omni Loop

```python
async def _inject_memory_context(self, task: str) -> None:
    """Associative Recall before task execution."""
    memories = await vector_store.search(query=task, n_results=3)
    if memories:
        self.context.add_system_message(f"\n[RECALLED MEMORIES]\n{memories}\n[/RECALLED MEMORIES]\n")
```

### Storage Locations

| Data Type            | Location                              |
| -------------------- | ------------------------------------- |
| **Learned Rules**    | `memory` collection in VectorStore    |
| **Harvested Skills** | `assets/skills/harvested/quarantine/` |

## Related Documentation

- [Knowledge Matrix](knowledge-matrix.md) (Documentation RAG)
- [Omni Loop](omni-loop.md) (CCA Runtime with Knowledge + Memory)
- [Self-Evolution](omni-loop.md#self-evolution) (Skill harvesting and rule extraction)
