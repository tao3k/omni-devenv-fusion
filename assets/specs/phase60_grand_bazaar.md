---
name: phase60_grand_bazaar
version: 1.0.0
description: Semantic Tool Routing & Dynamic Skill Loading for Scalable Agent Architecture
authors: Omni Team
created: 2026-01-13
routing_keywords:
  [semantic, routing, skills, tools, dynamic, loading, vector, rag]
intents: [index_skills, load_tools, retrieve_tools, semantic_search]
---

# Phase 60: The Grand Bazaar (语义路由与技能集市)

## Overview

Phase 60 implements **Semantic Tool Routing** - a dynamic tool loading system that enables the agent to scale to hundreds of skills without overwhelming the context window.

## Problem Statement

Current architecture loads **all** tools at initialization:

- Context Window Pressure: 100+ tools = massive prompt bloat
- Attention Pollution: LLM distracted by irrelevant tools
- Slow Startup: Loading unused modules wastes time
- No Skill Discovery: User can't discover new capabilities

## Solution: Dynamic Tool Loading

Instead of loading all tools, we:

1. **Index** all skills into a vector store at startup
2. **Retrieve** top-K relevant skills based on semantic task matching
3. **Load** only the tools needed for the current task

## Architecture

```
User Task: "commit changes to git"
    │
    ▼
┌─────────────────────────────────────┐
│  Semantic Router (skill_loader.py)  │
│  - Embed task description           │
│  - Search vector store              │
│  - Retrieve top-5 relevant skills   │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Dynamic Tool Loader                │
│  - Import skill modules             │
│  - Register relevant tools          │
│  - Return ToolRegistry              │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Agent Execution                    │
│  - Only 5 tools in context          │
│  - Faster, focused inference        │
└─────────────────────────────────────┘
```

## Key Components

### 1. Skill Loader (`agent/core/skill_loader.py`)

```python
# Index all skills (run once at startup)
loader = get_skill_loader()
loader.index_all_skills()

# Get relevant tools for a task
tools = await load_tools_for_task("commit changes to git")
# Returns: ToolRegistry with only git-related tools
```

### 2. IndexedSkill Data Model

```python
@dataclass
class IndexedSkill:
    name: str                    # e.g., "git"
    description: str             # Human-readable description
    routing_keywords: List[str]  # e.g., ["commit", "push", "branch"]
    intents: List[str]           # e.g., ["commit_changes", "create_branch"]
    module_path: str             # For dynamic import
    metadata: Dict[str, Any]     # Additional skill data
```

### 3. Vector Store Integration

Skills are indexed into `omni-vector` with:

- Collection: `system_skills`
- Embedding: BGE-small (384 dimensions)
- Search: Semantic similarity matching

## Workflow

### Step 1: Indexing (Startup)

```python
# Scan assets/skills/ for all SKILL.md files
# Extract metadata (name, description, keywords, intents)
# Generate search text for embedding
# Store in vector store
```

### Step 2: Retrieval (Per Task)

```python
# 1. Embed task description
query_vec = embed(task)

# 2. Search vector store for relevant skills
results = vector_store.search(query_vec, top_k=5)

# 3. Return ranked skills by relevance
return [skill for skill in results]
```

### Step 3: Loading (Per Task)

```python
# For each retrieved skill:
skill = retrieved_skills[0]

# Dynamic import
module = importlib.import_module(skill.module_path)

# Get tools from skill
tools = module.get_tools()

# Register in ToolRegistry
for tool in tools:
    registry.register(tool)
```

## Benefits

### Context Window Optimization

| Scenario      | Before              | After             |
| ------------- | ------------------- | ----------------- |
| 100 skills    | 100 tools in prompt | 5 tools in prompt |
| Tokens used   | ~50K                | ~5K               |
| LLM attention | Diluted             | Focused           |

### Startup Time

| Scenario       | Before          | After          |
| -------------- | --------------- | -------------- |
| Module imports | All 100 modules | Only 5 modules |
| Time           | ~2s             | ~0.5s          |

### Scalability

- Can support 1000+ skills without performance degradation
- New skills automatically discoverable via semantic search
- No code changes needed when adding skills

## Fallback Strategy

When vector store is unavailable:

1. Use keyword matching on routing_keywords and intents
2. Score skills by keyword overlap with task
3. Return top-K by score

```python
def _keyword_match(task: str, top_k: int) -> List[IndexedSkill]:
    task_lower = task.lower()
    scored = []
    for skill in self._skills.values():
        score = 0.0
        for kw in skill.routing_keywords:
            if kw.lower() in task_lower:
                score += 1.0
        if score > 0:
            scored.append((score, skill))
    return [s for _, s in sorted(scored)[:top_k]]
```

## Integration Points

### With Orchestrator

```python
async def run(self, task: str):
    # Dynamic tool loading
    self.tools = await load_tools_for_task(task)

    # Continue with normal execution
    # ...
```

### With Skill Discovery

```python
# Index newly discovered skills
loader = get_skill_loader()
loader.index_skill(new_skill_path)

# Re-index all (for major updates)
loader.reindex_all()
```

## Configuration

```yaml
# settings.yaml
skill_loading:
  # Maximum tools to load per task
  max_tools: 5

  # Minimum relevance score (0-1)
  min_score: 0.3

  # Enable fallback to keyword matching
  allow_keyword_fallback: true

  # Index on startup
  index_on_startup: true
```

## Future Enhancements

1. **Tool Composition**: Automatically combine complementary tools
2. **Skill Dependencies**: Load dependent skills together
3. **Caching**: Cache tool registrations across requests
4. **Hot Reload**: Update index without restart
5. **Skill Ratings**: Learn which skills work best for tasks

## Migration Guide

### For Existing Skills

Skills work unchanged - just need a valid SKILL.md with:

- `name`: Unique skill identifier
- `description`: What the skill does
- `routing_keywords`: Keywords for semantic matching
- `intents`: High-level intents

### For Tool Registration

Skills should expose `get_tools()` function:

```python
# In skill's __init__.py or tools.py
from agent.core.registry import tool

@tool
def git_commit(message: str) -> str:
    """Commit changes to git."""
    ...

def get_tools() -> List[Any]:
    return [git_commit]
```

## Testing

```python
# Test skill indexing
def test_index_skills():
    loader = get_skill_loader()
    count = loader.index_all_skills()
    assert count > 0

# Test retrieval
async def test_retrieve_skills():
    loader = get_skill_loader()
    skills = await loader.retrieve_relevant_skills("commit changes")
    assert "git" in [s.name for s in skills]

# Test tool loading
async def test_load_tools():
    tools = await load_tools_for_task("commit changes to git")
    assert len(tools) > 0
```

## Related Phases

- Phase 33: ODF-EP v6.0 (Tool standardization)
- Phase 53.5: The Encoder (Embedding service)
- Phase 57: omni-vector (Vector store migration)
- Phase 59: The Meta Agent (Task orchestration)
