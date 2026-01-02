# Documentation Workflow

> **TL;DR**: When code changes, docs MUST be updated. Use `check_doc_sync()` to verify, then update relevant docs before committing.

---

## Quick Reference

| Task                | Tool/Command                               |
| ------------------- | ------------------------------------------ |
| Check docs sync     | `@omni-orchestrator check_doc_sync()`      |
| List available docs | `@omni-orchestrator list_available_docs()` |
| Read doc for action | `@omni-orchestrator read_docs()`           |

---

## 1. The Documentation Rule

> **Rule**: Feature code cannot be merged until documentation is updated.

| If you modify...       | You must update...                                         |
| ---------------------- | ---------------------------------------------------------- |
| `mcp-server/*.py`      | `mcp-server/README.md`, `agent/how-to/*.md`                |
| `agent/specs/*.md`     | `agent/standards/feature-lifecycle.md` (workflow diagrams) |
| `agent/standards/*.md` | Update the standard itself                                 |
| `docs/*.md`            | User-facing guides (if breaking changes)                   |
| `CLAUDE.md`            | Project conventions                                        |
| `justfile`             | Command documentation in `docs/`                           |

---

## 2. The Documentation Sync Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  Code implementation complete                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Detect what docs need updating                         │
│  @omni-orchestrator check_doc_sync(changed_files=[...])        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Update each required doc                               │
│  - mcp-server/*.md → mcp-server/README.md                      │
│  - agent/specs/*.md → agent/standards/feature-lifecycle.md     │
│  - justfile → docs/ or CLI help                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: Verify all docs are in sync                            │
│  @omni-orchestrator check_doc_sync()                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Commit with docs                                       │
│  just agent-commit                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Using check_doc_sync

Call this tool before committing to verify docs are updated:

```python
@omni-orchestrator check_doc_sync(changed_files=["mcp-server/new_tool.py"])
```

**Response:**

```json
{
  "status": "out_of_sync",
  "changed_files": ["mcp-server/new_tool.py"],
  "required_docs": [
    {
      "file": "mcp-server/README.md",
      "reason": "New MCP tool added",
      "action": "Add tool to Tools table"
    }
  ],
  "recommendation": "Update mcp-server/README.md before committing"
}
```

---

## 4. Document Classification

Understand where to write documentation:

| Directory         | Audience     | Purpose                                            |
| ----------------- | ------------ | -------------------------------------------------- |
| `agent/`          | LLM (Claude) | How-to guides, standards - context for AI behavior |
| `docs/`           | Users        | Human-readable manuals, tutorials                  |
| `mcp-server/*.md` | Developers   | Technical implementation docs                      |
| `agent/specs/`    | LLM + Devs   | Feature specifications                             |

---

## 5. When to Write Documentation

| Scenario               | Write To                                                          |
| ---------------------- | ----------------------------------------------------------------- |
| New MCP tool           | `mcp-server/README.md` (tool table), `agent/how-to/*.md`          |
| New workflow/process   | `agent/how-to/` (for LLM to follow)                               |
| User-facing guide      | `docs/` (for humans)                                              |
| Implementation details | `mcp-server/` (for contributors)                                  |
| Feature spec           | `agent/specs/` (contract between requirements and implementation) |
| Project convention     | `CLAUDE.md` (quick reference)                                     |

---

## 6. Anti-Patterns

| Wrong                               | Correct                                 |
| ----------------------------------- | --------------------------------------- |
| Commit code without updating README | Check `check_doc_sync()` first          |
| Update docs in a separate commit    | Update docs in the SAME commit as code  |
| Write user docs in `agent/`         | Write user docs in `docs/`              |
| Forget to update CLAUDE.md          | Update CLAUDE.md for new tools/commands |

---

## 7. Related Documentation

| Document                               | Purpose                          |
| -------------------------------------- | -------------------------------- |
| `agent/standards/feature-lifecycle.md` | Spec-driven development workflow |
| `agent/how-to/git-workflow.md`         | Commit conventions               |
| `agent/how-to/testing-workflows.md`    | Test requirements                |
| `mcp-server/README.md`                 | MCP tools reference              |

---

_Document everything. Code without docs is debt, not asset._
