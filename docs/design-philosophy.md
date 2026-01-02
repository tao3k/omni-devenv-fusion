# Design Philosophy

## Two Interaction Patterns

This project defines two clear patterns for how AI agents interact with project knowledge:

| Pattern | When LLM reads... | Purpose |
|---------|------------------|---------|
| **Memory Loading** | `agent/` directory | Follow rules to **act** (commit, write code, etc.) |
| **Document Query** | `docs/` directory | Find info to **answer** user questions |

### Memory Loading (For LLM Actions)

When LLM needs to **perform** a task, it loads guidelines from `agent/`:

```
User: "Help me commit these changes"
→ LLM loads: agent/how-to/git-workflow.md
→ LLM acts: follows rules to execute smart_commit
```

### Document Query (For User Questions)

When user asks **questions**, LLM queries `docs/`:

```
User: "What is the git flow?"
→ LLM queries: docs/how-to/git-workflow.md
→ LLM answers: explains the workflow
```

## Why This Separation?

| Directory | Audience | Content |
|-----------|----------|---------|
| `agent/` | LLM (Claude) | Rules, protocols, standards - for AI behavior |
| `docs/` | Users | Manuals, tutorials, explanations - for humans |

### Design Rationale

LLMs often "hallucinate" by skipping project-specific rules when answering questions.
By separating documentation into two audiences:

- **`agent/`**: Explicitly tells LLM "this is for you, read before acting"
- **`docs/``: Clearly marked as "for users", LLM can reference it when answering

This forces the LLM to:
1. Use `load_*_memory` tools when **acting** (follows rules)
2. Use `read_docs` tool when **answering** (finds information)

## Key Tools

| Tool | Pattern | Reads |
|------|---------|-------|
| `load_git_workflow_memory()` | Memory Loading | `agent/how-to/git-workflow.md` |
| `load_writing_memory()` | Memory Loading | `agent/writing-style/*.md` |
| `get_language_standards()` | Memory Loading | `agent/standards/lang-*.md` |
| `read_docs()` | Document Query | `docs/*.md` |

## Documentation Sources

| Source | Purpose |
|--------|---------|
| `agent/how-to/` | Process guides (git workflow, testing, release) |
| `agent/standards/` | Language conventions, feature lifecycle |
| `agent/writing-style/` | Writing quality rules |
| `agent/specs/` | Feature specifications |
| `docs/` | User-facing documentation |

---

*See [agent/instructions/project-conventions.md](../agent/instructions/project-conventions.md) for LLM-specific instructions.*
