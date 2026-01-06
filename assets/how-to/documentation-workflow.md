# Documentation Workflow

> **TL;DR**: When code changes, docs MUST be updated. Use the Documentation Skill to manage knowledge entries.

---

## Quick Reference

| Task                    | Tool/Command                                 |
| ----------------------- | -------------------------------------------- |
| Create knowledge entry  | `@omni-orchestrator create_knowledge_entry`  |
| Rebuild knowledge index | `@omni-orchestrator rebuild_knowledge_index` |
| Search knowledge base   | `@omni-orchestrator search_knowledge_base`   |

---

## 1. The Documentation Rule

> **Rule**: Feature code cannot be merged until documentation is updated.

| If you modify...       | You must update...                                         |
| ---------------------- | ---------------------------------------------------------- |
| `agent/skills/*.py`    | Skill documentation in `agent/skills/*/guide.md`           |
| `agent/specs/*.md`     | `agent/standards/feature-lifecycle.md` (workflow diagrams) |
| `agent/standards/*.md` | Update the standard itself                                 |
| `docs/*.md`            | User-facing guides (if breaking changes)                   |
| `CLAUDE.md`            | Project conventions                                        |
| `justfile`             | Command documentation in `docs/`                           |

---

## 2. The Documentation Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  Code implementation complete                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Determine doc type                                     │
│  - New knowledge → Documentation Skill (create_knowledge_entry)│
│  - Code changes → Update relevant docs in docs/                │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Create or update documentation                         │
│  - Use create_knowledge_entry for new insights                 │
│  - Update existing docs in docs/                               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Rebuild knowledge index (if creating new entry)       │
│  @omni-orchestrator rebuild_knowledge_index()                  │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Commit with docs                                       │
│  just agent-commit                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Using the Documentation Skill

### Create a Knowledge Entry

```python
@omni-orchestrator create_knowledge_entry(
    title="Fixing Deadlocks",
    category="debugging",
    content="## Problem\n... \n## Solution\n..."
)
```

**Response:**

```
Created knowledge entry: 20260103-debugging-fixing-deadlocks.md
```

### Rebuild Knowledge Index

Call this after adding or deleting knowledge entries:

```python
@omni-orchestrator rebuild_knowledge_index()
```

### Search Knowledge Base

```python
@omni-orchestrator search_knowledge_base(query="deadlock")
```

---

## 4. Knowledge Entry Standards

### Location

- All knowledge goes into `agent/knowledge/harvested/`

### Naming Convention

`YYYYMMDD-category-title.md` (e.g., `20260102-debugging-nested-locks.md`)

### Frontmatter Format

```markdown
# Title

> **Category**: CATEGORY | **Date**: YYYY-MM-DD

Content...
```

### Categories

- `architecture` - Design decisions
- `debugging` - Problem solutions
- `pattern` - Reusable patterns
- `workflow` - Process documentation
- `domain` - Domain-specific knowledge

---

## 5. Document Classification

Understand where to write documentation:

| Directory         | Audience     | Purpose                                            |
| ----------------- | ------------ | -------------------------------------------------- |
| `agent/`          | LLM (Claude) | How-to guides, standards - context for AI behavior |
| `docs/`           | Users        | Human-readable manuals, tutorials                  |
| `agent/skills/*/` | LLM + Devs   | Skill documentation (guide.md, prompts.md)         |
| `agent/specs/`    | LLM + Devs   | Feature specifications                             |

---

## 6. When to Write Documentation

| Scenario               | Write To                                                          |
| ---------------------- | ----------------------------------------------------------------- |
| New skill              | `agent/skills/{skill}/guide.md`                                   |
| New workflow/process   | `agent/how-to/` (for LLM to follow)                               |
| User-facing guide      | `docs/` (for humans)                                              |
| Implementation details | `agent/skills/*/` (for contributors)                              |
| Feature spec           | `agent/specs/` (contract between requirements and implementation) |
| Project convention     | `CLAUDE.md` (quick reference)                                     |
| Captured insight       | `agent/knowledge/harvested/` (Documentation Skill)                |

---

## 7. Anti-Patterns

| Wrong                               | Correct                                                        |
| ----------------------------------- | -------------------------------------------------------------- |
| Commit code without updating README | Check relevant docs first                                      |
| Update docs in a separate commit    | Update docs in the SAME commit as code                         |
| Write user docs in `agent/`         | Write user docs in `docs/`                                     |
| Forget to update CLAUDE.md          | Update CLAUDE.md for new tools/commands                        |
| Store insights without index update | Always call `rebuild_knowledge_index()` after creating entries |

---

## 8. Related Documentation

| Document                               | Purpose                          |
| -------------------------------------- | -------------------------------- |
| `agent/standards/feature-lifecycle.md` | Spec-driven development workflow |
| `agent/how-to/git-workflow.md`         | Commit conventions               |
| `agent/how-to/testing-workflows.md`    | Test requirements                |
| `agent/skills/documentation/guide.md`  | Documentation Skill guide        |

---

_Document everything. Code without docs is debt, not asset._
