# Memory Skill Guide

> "Memory is the residue of thought." - Daniel Willingham

## Purpose

The **Memory Skill** is the **Hippocampus Interface** - it enables vector-based memory storage and retrieval via LanceDB + FastEmbed.

**It does NOT:**

- Execute commands
- Edit files
- Make decisions

**It ONLY:**

- Stores insights as vectors in LanceDB
- Retrieves memories via semantic search
- Loads skill manifests for capability discovery

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Memory Skill (The Hippocampus Interface)               │
│  ├── save_memory() → Vectorize & Store (LanceDB)       │
│  ├── search_memory() → Embed query & Search             │
│  ├── load_skill() → Load skill manifest into memory     │
│  └── get_memory_stats() → Memory statistics             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  LanceDB Vector Store                                   │
│  • Dimension: 384 (BGE-small-en-v1.5)                   │
│  • Path: .cache/memory/lancedb                          │
│  • Index: IVF-FLAT                                      │
└─────────────────────────────────────────────────────────┘
```

## Usage Examples

### Store an Insight

```python
# Store a reusable insight
result = await save_memory(
    content="Always use semantic versioning for git tags. Format: v1.2.3",
    metadata={"domain": "git", "source": "test"}
)
# Returns: "Saved memory [a1b2c3d4]: Always use semantic versioning..."
```

### Search for Past Learning

```python
# Search for relevant memories
result = await search_memory(
    query="git tags semantic versioning rule",
    limit=5
)
# Returns: "Found 2 matches for 'git tags semantic versioning rule':\n- [Score: 0.8921] ..."
```

### Load Skill Manifest

```python
# Load a skill's capabilities into memory
result = await load_skill("git")
# Returns: "✅ Skill 'git' loaded into semantic memory."
```

## Tools Reference

| Tool               | Purpose                | When to Call                |
| ------------------ | ---------------------- | --------------------------- |
| `save_memory`      | Store reusable insight | After discovering a pattern |
| `search_memory`    | Semantic search        | When you need to remember   |
| `load_skill`       | Index skill manifest   | During skill sync           |
| `index_memory`     | Optimize search index  | After bulk imports          |
| `get_memory_stats` | Memory statistics      | Diagnostics                 |

## External Usage (e.g., NoteTaker)

The Memory skill can be loaded externally via `load_skill_module`:

```python
from omni.foundation.skills_path import load_skill_module

memory = load_skill_module("memory")

# Direct function calls
await memory.save_memory(content, metadata)
await memory.search_memory(query, limit)
```

## Path Configuration

**settings.yaml:**

```yaml
memory:
  path: "" # Empty = use default: .cache/{project}/.memory/
```

**Default Path:**

```
{git_toplevel}/.cache/{project}/memory/lancedb/
```

## Anti-Patterns

### Don't: Use memory as a todo list

```python
# WRONG - Memory is for learnings, not tasks
save_memory(content="Fix bug #123")
```

### Do: Use memory for reusable knowledge

```python
# CORRECT - Capture what you learned
save_memory(
    content="The project uses Conventional Commits with scopes from cog.toml",
    metadata={"domain": "git"}
)
```

### Don't: Log every tiny action

```python
# WRONG - Too granular
save_memory(content="Opened file")
```

### Do: Log significant insights

```python
# CORRECT - Log meaningful learnings
save_memory(
    content="The project requires 'just validate' before any commit",
    metadata={"domain": "git", "source": "workflow"}
)
```

## Integration with Other Skills

### Knowledge + Memory

```python
# Get context (knowledge skill)
context = get_development_context()

# Store what you learned (memory skill)
await save_memory(
    "Remember: knowledge skill must be preloaded first",
    metadata={"domain": "architecture"}
)
```

### NoteTaker + Memory

```python
# NoteTaker uses memory.save_memory() to persist wisdom notes
# Automatically called at end of OmniAgent session
```

## See Also

- [SKILL.md](SKILL.md) - Full routing policy and command reference
- [scripts/memory.py](scripts/memory.py) - Implementation
