# Design Philosophy

## Three Interaction Patterns

This project defines three clear patterns for how AI agents interact with project knowledge:

| Pattern            | When LLM reads... | Purpose                                            |
| ------------------ | ----------------- | -------------------------------------------------- |
| **Memory Loading** | `agent/skills/`   | Load capability packages to **act**                |
| **Memory Loading** | `agent/` (legacy) | Follow rules to **act** (commit, write code, etc.) |
| **Document Query** | `docs/` directory | Find info to **answer** user questions             |

### Pattern 1: Skill Loading (For LLM Actions - New)

When LLM needs to **perform** a task, it loads a Skill package from `agent/skills/`:

```
User: "Help me commit these changes"
→ LLM loads: agent/skills/git_operations/
→ LLM acts: follows guide.md + uses tools.py
```

A Skill contains everything the LLM needs:

- `manifest.json` - Metadata and capability declaration
- `README.md` - Procedural knowledge (how-to guide)
- `tools.py` - Executable tools
- `prompts/` - Context injection prompts

### Pattern 2: Memory Loading (For LLM Actions - Legacy)

When LLM needs to **perform** a task and no Skill is available, it loads guidelines from `agent/`:

```
User: "Help me commit these changes"
→ LLM loads: agent/how-to/git-workflow.md
→ LLM acts: follows rules to execute smart_commit
```

### Pattern 3: Document Query (For User Questions)

When user asks **questions**, LLM queries `docs/`:

```
User: "What is the git flow?"
→ LLM queries: docs/explanation/vision-skill-centric-os.md
→ LLM answers: explains the workflow
```

## The Evolution: From Agent-Centric to Skill-Centric

### Agent-Centric (Phases 1-12)

```
Orchestrator (The Brain) ← All tools loaded always
     ↓
Hardcoded tool sets (Git + Python + Docker + K8s + ...)
     ↓
Problem: Context bloat as tools increase
```

### Skill-Centric (Phase 13+)

```
Runtime (No fixed personality)
     ↓
Dynamic Skill Loading (load only what's needed)
     ↓
Skills: git_operations, python_engineering, debugging, ...
     ↓
Solution: Constant context cost regardless of skill count
```

**The Shift:**

| Dimension        | Agent-Centric           | Skill-Centric           |
| ---------------- | ----------------------- | ----------------------- |
| **Core Unit**    | Tools (functions)       | Skills (packages)       |
| **Context**      | All tools always loaded | Load on demand          |
| **Extension**    | Add tools to Agent      | Add new Skill directory |
| **Organization** | By server type          | By capability domain    |

## Why This Separation?

| Directory         | Audience     | Content                                       |
| ----------------- | ------------ | --------------------------------------------- |
| `agent/skills/`   | LLM (Claude) | Composable capability packages                |
| `agent/` (legacy) | LLM (Claude) | Rules, protocols, standards - for AI behavior |
| `docs/`           | Users        | Manuals, tutorials, explanations - for humans |

### Design Rationale

LLMs often "hallucinate" by skipping project-specific rules when answering questions.
By separating documentation into three audiences:

- **`agent/skills/`**: Self-contained packages - "load this to do X"
- **`agent/`**: Explicitly tells LLM "this is for you, read before acting"
- **`docs/`**: Clearly marked as "for users", LLM can reference it when answering

This forces the LLM to:

1. Use `load_skill()` when **acting** with a composable capability
2. Use `load_*_memory` tools when **acting** with legacy rules
3. Use `read_docs` tool when **answering** (finds information)

## Key Tools

| Tool                         | Pattern        | Reads                          |
| ---------------------------- | -------------- | ------------------------------ |
| `load_skill()`               | Skill Loading  | `agent/skills/{name}/`         |
| `list_skills()`              | Skill Loading  | `agent/skills/` (discovery)    |
| `load_git_workflow_memory()` | Memory Loading | `agent/how-to/git-workflow.md` |
| `load_writing_memory()`      | Memory Loading | `agent/writing-style/*.md`     |
| `get_language_standards()`   | Memory Loading | `agent/standards/lang-*.md`    |
| `read_docs()`                | Document Query | `docs/*.md`                    |

## The Skill Anatomy

Every skill follows a standardized structure:

```
agent/skills/{skill_name}/
├── manifest.json              # Metadata: name, version, tools, dependencies
├── README.md                  # Procedural knowledge (LLM's "manual")
├── tools.py                   # Executable tools ("hands")
├── prompts/
│   ├── system.md              # Context injection when active
│   └── examples.md            # Few-shot examples
└── tests/                     # Self-contained tests
```

### Manifest Schema

```json
{
  "name": "git_operations",
  "version": "1.0.0",
  "description": "Version control operations using smart commit workflow",
  "category": "development",
  "tools": ["git_status", "git_diff", "smart_commit"],
  "context_files": ["agent/skills/git_operations/README.md"]
}
```

## Documentation Sources

| Source                 | Purpose                                 |
| ---------------------- | --------------------------------------- |
| `agent/skills/`        | Composable capability packages (NEW)    |
| `agent/how-to/`        | Process guides (legacy)                 |
| `agent/standards/`     | Language conventions, feature lifecycle |
| `agent/writing-style/` | Writing quality rules                   |
| `agent/specs/`         | Feature specifications                  |
| `docs/`                | User-facing documentation               |

---

_See [agent/instructions/project-conventions.md](../agent/instructions/project-conventions.md) for LLM-specific instructions._
