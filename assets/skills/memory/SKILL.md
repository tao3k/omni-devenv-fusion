---
name: "memory"
version: "1.0.0"
description: "The Hippocampus Interface - Vector-based Memory for LLM (LanceDB + FastEmbed)"
routing_keywords:
  [
    "memory",
    "remember",
    "store",
    "save",
    "learn",
    "forget",
    "context",
    "persistent",
    "long-term",
    "recall",
    "embeddings",
    "vector",
    "note",
    "wisdom",
  ]
authors: ["omni-dev-fusion"]
---

# Memory Skill Policy

## Router Logic

### Scenario 1: User wants to store something

1. **Analyze**: Determine the type of memory (insight, rule, decision)
2. **Store**: Call `save_memory(content, metadata)`
3. **Confirm**: Show the saved memory ID

### Scenario 2: User wants to remember/search

1. **Search**: Call `search_memory(query, limit)`
2. **Format**: Present results with relevance scores
3. **Respond**: "I found X memories about that..."

### Scenario 3: User asks "What have you learned?", "Show memories"

1. **List**: Call `get_memory_stats()`
2. **Recall**: Call `search_memory()` with relevant keywords
3. **Present**: Show structured summary

## Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `save_memory` | Store insight/recipe into vector memory | `save_memory("Use semantic versioning", {"tag": "git"})` |
| `search_memory` | Semantic search in memory | `search_memory("git commit format", limit=5)` |
| `index_memory` | Optimize vector index (IVF-FLAT) | `index_memory()` |
| `get_memory_stats` | Get memory count | `get_memory_stats()` |
| `load_skill` | Load skill manifest into memory | `load_skill("git")` |

## Workflow: Store an Insight

```
User: Remember that for this project, all commit messages must be in English.

Claude:
  1. save_memory(
       content="All commit messages must be in English only",
       metadata={"domain": "git", "source": "user"}
     )
  2. → Saved memory [a1b2c3d4]: All commit messages must be in English only
  3. → "Got it! I'll remember that commit messages must be in English."
```

## Workflow: Recall Past Learning

```
User: What do we use for git tags?

Claude:
  1. search_memory("git tags semantic versioning")
  2. → Found 2 matches:
     - [Score: 0.8921] Always use semantic versioning for git tags...
     - [Score: 0.7234] v1.2.3 format for releases
  3. → "I found memories about git tags:
       - Always use semantic versioning for git tags..."
```

## Memory vs Knowledge Skill

| Aspect | Memory | Knowledge |
|--------|--------|-----------|
| **Source** | LLM's own learnings | Project documentation |
| **Storage** | LanceDB (vector) | File system (markdown) |
| **Query** | Semantic search | Keyword/pattern match |
| **Purpose** | "What did I learn?" | "What are the rules?" |
| **Update** | Runtime accumulation | Pre-indexed docs |

## Best Practices

1. **Store actionable insights**, not obvious facts
2. **Include domain in metadata** for filtering
3. **Use clear, searchable phrasing** in content
4. **Recall before acting** on project-specific patterns
