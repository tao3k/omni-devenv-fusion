# Hippocampus

> Long-Term Memory Interface for Self-Learning Agents
> **Status**: Active
> **Version**: v1.3 | 2026-02-03
> **Skill ID**: `memory`

## Overview

**Hippocampus** is the **Memory Interface** - a vector-based long-term memory system that enables the Agent to remember past experiences, learn from them, and apply learned rules in future sessions.

### Core Philosophy

| Aspect             | Description                                          |
| ------------------ | ---------------------------------------------------- |
| **Analogy**        | Hippocampus in brain = memory consolidation & recall |
| **Implementation** | LanceDB + LLM Embedding (MiniMax-M2.1, 1024-dim)     |
| **Purpose**        | "I remember doing that before"                       |
| **Update**         | Selective storage (only valuable learnings)          |

### Storage Policy

Hippocampus **only stores valuable learnings**, not every successful task:

| Condition           | Store? | Reason                     |
| ------------------- | ------ | -------------------------- |
| Single-step success | ❌ No  | No learning value          |
| Multi-step success  | ✅ Yes | Valuable execution pattern |
| Retry → Success     | ✅ Yes | Learned from failure       |
| Pure failure        | ❌ No  | Don't store failures       |

### Embedding Configuration

**Merged settings** (packages/conf/settings.yaml + user):

```yaml
embedding:
  provider: "llm" # Use same LLM as Omni Loop (MiniMax-M2.1)
  dimension: 1024 # High-quality semantic vectors from LLM
```

**How it works**:

1. LLM generates 16 core semantic values via structured prompting
2. Core values are expanded to configured dimension (1024) for storage
3. LanceDB stores vectors for fast similarity search

**Implementation**:

```python
# packages/python/foundation/src/omni/foundation/services/embedding.py

async def _embed_with_llm_async(self, text: str) -> list[list[float]]:
    """Generate embedding using LLM (async version).

    Returns a semantic vector of configured dimension (from settings).
    LLM generates 16 core values, which are interpolated to the target dimension.
    """
    # Prompt LLM to generate 16 core semantic values
    system_prompt = """You are a semantic embedding generator.
Output format: 16 comma-separated numbers between -1 and 1.
Example: 0.5,0.3,-0.2,0.8,0.1,0.9,-0.5,0.2,0.7,-0.1,0.4,0.6,-0.3,0.8,0.0,5
Do not include any other text."""

    response = await self._model.complete(
        system_prompt=system_prompt,
        user_query=f"Text: {text[:500]}\nOutput:",
        max_tokens=100,
    )

    # Parse 16 core values and expand to configured dimension (1024)
    content = response.get('content', '')
    values = [float(x.strip()) for x in content.split(',') if x.strip()]
    core = (values * 16)[:16] if len(values) < 16 else values[:16]

    # Expand to 1024-dim vector
    target_dim = self._dimension  # 1024
    vector = (core * (target_dim // 16 + 1))[:target_dim]
    return [vector]
```

### Functional Role in Omega Architecture

In the **Omega Architecture**, the Hippocampus serves as the long-term memory center, complementing the other functional systems:

| System          | Role       | Analogy            | Data Source           |
| :-------------- | :--------- | :----------------- | :-------------------- |
| **Cortex**      | Scheduling | Thinking Brain     | Mission Task Graph    |
| **Cerebellum**  | Perception | Motor Coordination | Codebase AST / Docs   |
| **Hippocampus** | Memory     | Memory Center      | LanceDB (Experiences) |
| **Evolution**   | Learning   | Adaptation         | Crystallized Skills   |
| **Homeostasis** | Isolation  | Internal Balance   | Isolated Git Branches |

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Hippocampus (Memory Interface)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │   save_memory   │  │  search_memory  │  │      load_skill         │  │
│  └────────┬────────┘  └────────┬────────┘  └────────────┬────────────┘  │
│           │                    │                        │                │
│           └────────────────────┼────────────────────────┘                │
│                                ▼                                         │
│                   ┌─────────────────────────┐                           │
│                   │    LanceDB VectorStore  │                           │
│                   │  - Dimension: 1024      │                           │
│                   │  - Index: IVF-FLAT      │                           │
│                   │  - Path: .cache/        │                           │
│                   └─────────────────────────┘                           │
│                                │                                         │
│                                ▼                                         │
│                   ┌─────────────────────────┐                           │
│                   │   LLM Embedding Service │                           │
│                   │  - Provider: MiniMax    │                           │
│                   │  - 16 core → 1024 dim   │                           │
│                   │  - Source: settings│                           │
│                   └─────────────────────────┘                           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Agent Runtime                                    │
│  - Clarify/Plan Node: Recall via hippocampus.recall_experience()        │
│  - Validate Node: Store only on retry_recovery or complex_execution     │
│  - NoteTaker: Persists wisdom notes                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

### Storage Flow

```
Task Execution
     │
     ├──► Recall: Query hippocampus for relevant past experiences
     │         └── Injects into Clarify/Plan node prompts
     │
     ├──► Execute: Run the task
     │
     └──► Validate: Check if should store
               │
               ├──► retry_count > 0 → Store (learned from failure)
               ├──► steps > 1 → Store (complex execution pattern)
               └──► single-step success → Skip (no learning value)
```

### 1.1 EpisodicMemoryProvider (Layer 4)

The **Hippocampus Layer** in the cognitive pipeline provides automatic memory recall:

```python
# packages/python/core/src/omni/core/context/providers.py

class EpisodicMemoryProvider(ContextProvider):
    """Layer 4: The Hippocampus (Long-term Memory Recall).

    Automatically retrieves relevant past interactions from VectorDB
    based on the current conversation context.
    """

    async def provide(self, state: dict[str, Any], budget: int) -> ContextResult | None:
        # Query from last message or current_task
        query = state.get("current_task") or state.get("messages", [])[-1]
        results = await store.search(query=query, n_results=self.top_k)

        # Format as <recalled_memories> block
        content = "<recalled_memories>\n" + "\n".join(memories) + "\n</recalled_memories>"
        return ContextResult(content=content, token_count=len(content.split()), name="episodic_memory", priority=40)
```

---

## 2. Storage Configuration

**Path**: `{git_toplevel}/.cache/{project}/memory/lancedb/`

**Merged settings** (packages/conf/settings.yaml + user):

```yaml
memory:
  path: "" # Empty = use default: .cache/{project}/memory/
```

---

## 3. API Reference

### 3.1 Core Functions

```python
# assets/skills/memory/scripts/memory.py

async def save_memory(content: str, metadata: dict[str, Any] | None = None) -> str:
    """
    Store insight/recipe into vector memory.

    Args:
        content: The insight to store (what you learned)
        metadata: Optional dict with domain, source, tags, etc.

    Returns:
        "Saved memory [ID]: {content preview}"

    Example:
        await save_memory(
            "Always use semantic versioning for git tags",
            {"domain": "git", "source": "user"}
        )
    """

async def search_memory(query: str, limit: int = 5) -> str:
    """
    Semantic search in memory.

    Args:
        query: Natural language query
        limit: Maximum results (default: 5)

    Returns:
        "Found N matches:\n- [Score: X] ..."

    Example:
        await search_memory("git tags semantic versioning")
    """

async def load_skill(skill_name: str) -> str:
    """
    Load skill manifest into semantic memory.

    Args:
        skill_name: Name of skill to load (e.g., "git", "researcher")

    Returns:
        "Skill '{skill_name}' loaded into semantic memory."

    Example:
        await load_skill("git")
    """

async def index_memory() -> str:
    """
    Optimize vector index (IVF-FLAT) for faster search.
    Call after bulk imports.

    Returns:
        "Vector index created/updated."
    """

async def get_memory_stats() -> str:
    """
    Get memory count and statistics.

    Returns:
        "Memory Statistics:\n- Total memories: N"
    """
```

### 3.2 Direct Python API

```python
from omni.foundation.services.vector import get_vector_store

store = get_vector_store()

# Add memory directly
await store.add(
    content="All commit messages must be in English only",
    metadata={"domain": "git", "source": "user"}
)

# Search memories
results = await store.search(query="git commit format", n_results=5)

# List all (with pagination)
all_memories = await store.list(limit=100, offset=0)
```

---

## 4. Memory Types

### 4.1 Extracted Lessons (Fast Path)

Rules/preferences extracted from user feedback:

```python
# From omni.agent.core.evolution.harvester
class ExtractedLesson:
    rule: str          # "Always use async for I/O"
    domain: str        # "python_style"
    confidence: float  # 0.0 - 1.0
    source: str        # "user_correction"
```

**Sources**:

- User corrections ("no, use async instead")
- Workflow preferences ("always run just validate first")
- Project conventions discovered during execution

### 4.2 Harvested Wisdom (Slow Path)

Skills synthesized from successful sessions:

```python
# From omni.agent.core.evolution.harvester
class SessionCandidate:
    trajectory: list[dict]  # Execution steps
    outcome: str            # "success" / "partial" / "failure"
    insight: str            # "Use researcher skill for code analysis"
```

---

## 5. Integration Points

### 5.1 OmniLoop Memory Injection

```python
# packages/python/agent/src/omni/agent/core/omni/loop.py

async def _inject_memory_context(self, task: str) -> None:
    """Associative Recall before task execution."""
    store = get_vector_store()
    memories = await store.search(query=task, n_results=3)

    if memories:
        memory_block = "\n[RECALLED MEMORIES]\n"
        for m in memories:
            source = m.metadata.get("domain", "User")
            memory_block += f"- {m.content} (Source: {source})\n"
        memory_block += "[End of Memories]\n"

        self.context.add_system_message(memory_block)
```

### 5.2 Harvester Rule Extraction

```python
# packages/python/agent/src/omni/agent/core/evolution/harvester.py

class Harvester:
    async def extract_lessons(self, history: list[dict]) -> list[ExtractedLesson]:
        """Extract rules/preferences from user feedback."""
        correction_patterns = ["no,", "not", "wrong", "don't", "instead", "use"]
        relevant = [m for m in history if any(p in m.content.lower() for p in correction_patterns)]
        # LLM extracts the underlying rule...
        return lessons

    async def store_lessons(self, lessons: list[ExtractedLesson]) -> None:
        """Persist extracted lessons to Hippocampus."""
        store = get_vector_store()
        for lesson in lessons:
            await store.add(
                content=lesson.rule,
                metadata={
                    "domain": lesson.domain,
                    "confidence": lesson.confidence,
                    "type": "extracted_lesson"
                }
            )
```

### 5.3 NoteTaker Integration

NoteTaker calls memory.save_memory() to persist wisdom notes automatically at end of OmniAgent session.

---

## 6. Comparison: Knowledge vs Memory

| Aspect      | Knowledge (Cortex)     | Memory (Hippocampus) |
| ----------- | ---------------------- | -------------------- |
| **Source**  | Project docs           | LLM's own learnings  |
| **Storage** | File system (markdown) | LanceDB (vectors)    |
| **Query**   | Keyword/pattern match  | Semantic search      |
| **Update**  | Pre-indexed docs       | Runtime accumulation |
| **Purpose** | "What are the rules?"  | "What did I learn?"  |
| **Content** | Static documentation   | Dynamic experiences  |

---

## 7. Best Practices

### 7.1 What to Store (Automatic)

Hippocampus **automatically** stores experiences based on these conditions:

| Condition           | Store? | Tag                 | Reason                     |
| ------------------- | ------ | ------------------- | -------------------------- |
| `retry_count > 0`   | ✅ Yes | `retry_recovery`    | Learned from failure       |
| `steps > 1`         | ✅ Yes | `complex_execution` | Valuable execution pattern |
| Single-step success | ❌ No  | -                   | No learning value          |
| Pure failure        | ❌ No  | -                   | Don't store failures       |

### 7.2 Manual Storage (via Skills)

For explicit learnings, use NoteTaker or memory.save_memory():

```python
# Store explicit wisdom
await note_taker.update_knowledge_base(
    category="patterns",
    title="Research Workflow Pattern",
    content="Use researcher.run_research_graph for code analysis..."
)
```

### 7.3 Metadata Guidelines

```python
# Good metadata
await save_memory(
    "The project requires 'just validate' before any commit",
    metadata={
        "domain": "workflow",       # Required: categorize by domain
        "source": "user",           # How it was learned
        "confidence": 0.9,          # Certainty level
        "tags": ["git", "commit"]   # For filtering
    }
)
```

---

## 8. Directory Structure

```
assets/skills/memory/
├── SKILL.md              # Routing policy (routing_keywords, intents)
├── README.md             # User-facing documentation
└── scripts/
    └── memory.py         # Implementation (save_memory, search_memory, etc.)

packages/python/core/src/omni/core/skills/
└── memory.py             # SkillMemory facade for ContextAssembler

packages/python/agent/src/omni/agent/core/
└── evolution/
    ├── harvester.py      # Session analysis & rule extraction
    └── factory.py        # Skill synthesis from sessions

.cache/{project}/memory/lancedb/
├── _data.lance           # Vector data
└── _idx.lance            # Vector index
```

---

## 9. Testing

```bash
# Test memory write/read cycle
uv run python -c "
import asyncio
from omni.foundation.services.vector import get_vector_store

async def test():
    store = get_vector_store()

    # Write
    await store.add(
        content='Use semantic versioning: v1.2.3',
        metadata={'domain': 'git', 'source': 'test'}
    )
    print('Memory written!')

    # Read
    results = await store.search('git version format', n_results=3)
    for r in results:
        print(f'[{r.distance:.2f}] {r.content}')

asyncio.run(test())
"

# Run unit tests
uv run pytest packages/python/agent/tests/unit/test_memory_mesh.py -v
```

---

## 10. Related Documentation

| Document                                                     | Description                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------------- |
| [Memory Mesh](memory-mesh.md)                                | Episodic memory architecture (detailed types, manager, interceptor) |
| [Knowledge Matrix](knowledge-matrix.md)                      | Unified index (Skills + Knowledge + Memory tables)                  |
| [Omni Loop](../explanation/omni-loop.md)                     | CCA Runtime with memory injection                                   |
| [Self-Evolution](../explanation/omni-loop.md#self-evolution) | Skill harvesting and rule extraction                                |
| [Skill: memory](../../assets/skills/memory/SKILL.md)         | Routing policy and command reference                                |
| [Skill: memory README](../../assets/skills/memory/README.md) | Usage examples and best practices                                   |
