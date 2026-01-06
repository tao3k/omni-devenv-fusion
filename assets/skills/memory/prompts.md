# Memory Skill Policy

## Router Logic

### Scenario 1: User asks "Did we ever...", "Have we...", "I remember..."

1. **Recall**: Call `recall(query)` with relevant keywords
2. **Synthesize**: Combine results into a coherent answer
3. **Respond**: "I found X memories about that..."

### Scenario 2: User asks to "remember this", "store this", "don't forget"

1. **Analyze**: Determine if this is an insight or an episode
2. **Store**: Call `remember_insight()` for learnings, `log_episode()` for actions
3. **Confirm**: Show what was stored

### Scenario 3: User asks "What have you learned?", "Show memories"

1. **List**: Call `list_harvested_knowledge()`
2. **Format**: Organize by domain/category
3. **Present**: Show structured summary

### Scenario 4: End of significant session

1. **Consolidate**: Call `harvest_session_insight(context_summary, files_changed)`
2. **Store**: Extract key learnings and store them

## Workflow: Remembering a Solution

```
User: How did we fix the nixfmt error before?

Claude:
  1. recall("nixfmt error solution")
  2. → Found: "Use 'just fmt' before committing when nixfmt fails"
  3. → "I remember! We solved this by running 'just fmt'..."
```

## Workflow: Storing an Insight

```
User: Remember that for this project, all commit messages must be in English.

Claude:
  1. remember_insight(content="All commit messages must be in English only", domain="git")
  2. → Stored in semantic memory
  3. → "✅ Got it! I'll remember that commit messages must be in English."
```

## Workflow: Session Harvesting

```
User: We're done with this feature. Summarize what we did.

Claude:
  1. harvest_session_insight(context_summary="Implemented knowledge skill for context injection", files_changed=["agent/skills/knowledge/..."])
  2. → Stored as session memory
  3. → "✅ Session harvested. Key learnings stored in Hippocampus."
```

## When NOT to Use Memory Skill

- **Quick temporary notes** → Use scratchpad instead
- **Task tracking** → Use backlog/issue tracker
- **Code snippets** → Use proper documentation

## Memory vs Knowledge Skill

| Aspect  | Memory              | Knowledge              |
| ------- | ------------------- | ---------------------- |
| Source  | LLM's own learnings | Project documentation  |
| Storage | ChromaDB (vector)   | File system (markdown) |
| Query   | Semantic search     | Keyword/pattern match  |
| Purpose | "What did I learn?" | "What are the rules?"  |

## Best Practices

1. **Store actionable insights**, not obvious facts
2. **Use domains** (git, nix, architecture) for organization
3. **Log significant episodes** with context
4. **Harvest at session end** for long-term retention
