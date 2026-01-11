# Memory Skill Guide

> "Memory is the residue of thought." - Daniel Willingham

## Purpose

The **Memory Skill** is the **Hippocampus Interface** - it enables vector-based memory storage and retrieval via ChromaDB.

**It does NOT:**

- Execute commands
- Edit files
- Make decisions

**It ONLY:**

- Stores insights as vectors in ChromaDB
- Retrieves memories via semantic search
- Logs episodes for session tracking

## When to Use

### After Learning Something New

```python
# Store a reusable insight
remember_insight(content="Use scope 'nix' for flake-related changes", domain="git")
```

### After Completing a Significant Action

```python
# Log what you did
log_episode(action="Refactored skill registry", result="Skills now load from settings.yaml", context="packages/python/agent/src/agent/core/skill_registry.py")
```

### When You Need to Remember

```python
# Search for past learnings
recall("how to add a new skill")
recall("git commit format")
recall("nixfmt error solution")
```

### At End of Session (Consolidation)

```python
# Harvest key learnings
harvest_session_insight(context_summary="Implemented knowledge skill for context injection", files_changed=["agent/skills/knowledge/tools.py"])
```

## Tools Reference

| Tool                         | Purpose                 | When to Call                |
| ---------------------------- | ----------------------- | --------------------------- |
| `remember_insight()`         | Store reusable learning | After discovering a pattern |
| `log_episode()`              | Log session action      | After completing work       |
| `recall()`                   | Semantic search         | When you need to remember   |
| `list_harvested_knowledge()` | Show all insights       | Periodic review             |
| `harvest_session_insight()`  | Consolidate session     | End of significant session  |
| `get_memory_stats()`         | Memory statistics       | Diagnostics                 |

## Output Examples

### remember_insight()

```
✅ Insight stored in Hippocampus:
[Domain: git]
"Use scope 'nix' for flake changes..."
```

### recall()

```
🧠 **Hippocampus Recall**:
[1] [git] Use scope 'nix' for flake changes
---
[2] [workflow] Always run 'just validate' before committing
```

### get_memory_stats()

```
🧠 **Memory Statistics**
Semantic memories (insights): 12
Episodic memories (actions): 47
```

## Memory Architecture

**Path Configuration (settings.yaml):**

```yaml
memory:
  path: "" # Empty = use prj-spec: {git_toplevel}/.cache/{project}/.memory/
```

**Default Path (prj-spec):**

```
{git_toplevel}/.cache/{project}/.memory/
├── chroma_db/              # ChromaDB persistent storage
│   ├── semantic_knowledge/ # Insights, learnings, rules
│   └── episodic_memory/    # Session actions, episodes
└── active_context/         # Active context (RAM)

┌─────────────────────────────────────────────────────────┐
│  ChromaDB (Persistent Vector Store)                     │
│  ├── semantic_knowledge: Insights, learnings, rules     │
│  └── episodic_memory: Session actions, episodes         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Memory Skill (The Hippocampus Interface)               │
│  ├── remember_insight() → Vectorize & Store             │
│  ├── recall() → Embed query & Search                    │
│  └── log_episode() → Store action/result                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  LLM Context                                             │
│  "I remember that from session..."                      │
└─────────────────────────────────────────────────────────┘
```

## Anti-Patterns

### ❌ Don't: Use memory as a todo list

```python
# WRONG - Memory is for learnings, not tasks
remember_insight(content="Fix bug #123")
```

### ✅ Do: Use memory for reusable knowledge

```python
# CORRECT - Capture what you learned
remember_insight(content="The project uses Conventional Commits with scopes from cog.toml", domain="git")
```

### ❌ Don't: Log every tiny action

```python
# WRONG - Too granular
log_episode(action="Opened file", result="Success")
```

### ✅ Do: Log significant episodes

```python
# CORRECT - Log meaningful actions
log_episode(action="Refactored git skill", result="Removed smart_commit, simplified to executor mode", context="agent/skills/git/tools.py")
```

## Integration with Other Skills

### Knowledge + Memory

```
# First get context (knowledge skill)
context = get_development_context()
# Then store what you learned (memory skill)
remember_insight("Remember: knowledge skill must be preloaded first", domain="architecture")
```

### Terminal + Memory

```
# Execute something
result = run_task("just validate")
# Log the outcome
log_episode(action="Ran just validate", result=result[:100])
```
