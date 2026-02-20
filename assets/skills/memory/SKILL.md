---
name: memory
description: Use for short-term operational memory: track transient issues/workarounds, recall recent execution context, and support cleanup of stale entries.
metadata:
  author: omni-dev-fusion
  version: "1.0.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/memory"
  routing_keywords:
    - "memory"
    - "remember"
    - "store"
    - "save"
    - "learn"
    - "forget"
    - "context"
    - "short-term"
    - "transient"
    - "workaround"
    - "cleanup"
    - "recall"
    - "embeddings"
    - "vector"
    - "note"
    - "revalidation"
  intents:
    - "Track transient operational findings"
    - "Recall recent issue context"
    - "Store temporary workaround knowledge"
    - "Support short-term memory cleanup workflows"
---

# Memory Skill Policy

This skill is an MCP-facing facade for memory operations.
Core memory policy (lifecycle/revalidation/promotion) belongs to Rust memory core, not this skill surface.

## Router Logic

### Scenario 1: User wants to store a transient finding

1. **Analyze**: Determine if the item is transient operational memory (bug/workaround/incident note)
2. **Store**: Call `save_memory(content, metadata)`
3. **Confirm**: Show the saved memory ID

### Scenario 2: User wants to remember/search

1. **Search**: Call `search_memory(query, limit)`
2. **Format**: Present results with relevance scores
3. **Respond**: "I found X memories about that..."

### Scenario 3: User asks for current operational memory status

1. **List**: Call `get_memory_stats()`
2. **Recall**: Call `search_memory()` with relevant keywords
3. **Present**: Show structured summary with transient scope

## Commands Reference

| Command            | Description                              | Example                                                                          |
| ------------------ | ---------------------------------------- | -------------------------------------------------------------------------------- |
| `save_memory`      | Store short-term operational memory item | `save_memory("Temporary workaround for timeout in parser", {"tag": "incident"})` |
| `search_memory`    | Semantic search in memory                | `search_memory("git commit format", limit=5)`                                    |
| `index_memory`     | Optimize vector index (IVF-FLAT)         | `index_memory()`                                                                 |
| `get_memory_stats` | Get memory count                         | `get_memory_stats()`                                                             |
| `load_skill`       | Load skill manifest into memory          | `load_skill("git")`                                                              |

## Workflow: Store a Transient Workaround

```
User: Remember this temporary fix: increase parser timeout when MCP queue spikes.

Claude:
  1. save_memory(
       content="Temporary workaround: increase parser timeout under MCP queue spike",
       metadata={"domain": "runtime", "kind": "workaround", "source": "user"}
     )
  2. → Saved memory [a1b2c3d4]: Temporary workaround: increase parser timeout...
  3. → "Stored as short-term operational memory."
```

## Workflow: Recall Recent Operational Context

```
User: What workaround did we use for MCP queue timeout?

Claude:
  1. search_memory("MCP queue timeout workaround")
  2. → Found 2 matches:
     - [Score: 0.8921] Temporary workaround: increase parser timeout...
     - [Score: 0.7234] Queue backpressure note...
  3. → "I found recent operational memory for this issue..."
```

## Memory vs Knowledge Skill

| Aspect       | Memory (this skill)                            | Knowledge skill                               |
| ------------ | ---------------------------------------------- | --------------------------------------------- |
| **Scope**    | Short-term operational context                 | Long-term reusable knowledge                  |
| **Nature**   | Transient (can be purged after revalidation)   | Stable (promoted/curated)                     |
| **Purpose**  | "What recent issue/workaround context exists?" | "What durable rule/pattern should be reused?" |
| **Policy**   | Managed by Rust memory core lifecycle          | Managed by knowledge ingestion/curation flows |
| **Exposure** | MCP tool facade                                | MCP tool interface                            |

## Best Practices

1. **Store transient operational memory**, not permanent rules
2. **Include `kind` in metadata** (`incident`, `workaround`, `observation`)
3. **Use clear, searchable phrasing** in content
4. **Promote only proven durable patterns** to `knowledge`
