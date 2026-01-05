# CLAUDE.md - Omni-DevEnv Fusion

> **Phase 24: The MiniMax Shift**
>
> Direct tool registration - no `invoke_skill` middleware.
> Tools are registered directly with snake_case names.
>
> Quick Reference: `agent/skills/*/prompts.md`

---

## ⛔ CRITICAL: Git Commit Prohibition

**Direct `git commit` via Terminal is BLOCKED.**

Use: `@omni-orchestrator git_commit` or call `git_commit()` directly.

---

## Core Philosophy

**Code is Mechanism, Prompt is Policy**

| Layer          | Purpose        | Files                                     |
| -------------- | -------------- | ----------------------------------------- |
| **Brain**      | Rules, routing | `prompts.md` (LLM reads when skill loads) |
| **Muscle**     | Execution      | `tools.py` (blind, stateless)             |
| **Guardrails** | Validation     | Lefthook, Cog, Pre-commit                 |

---

## 📍 Working Directory

**Project Root:** `/Users/guangtao/ghq/github.com/tao3k/omni-devenv-fusion`

**Relative paths are relative to Project Root.**

**Do NOT use absolute paths like `/Users/...`** - use relative paths like:

- `agent/main.py` (NOT `/Users/.../agent/main.py`)
- `packages/python/agent/src/agent/` (NOT full absolute path)

---

## Essential Commands

- `just validate` - fmt, lint, test
- `just test-mcp` - MCP tools test

---

## Phase 24: Direct Tool Registration

### Tool Names are snake_case

| Old (Phase 13) | New (Phase 24) |
| -------------- | -------------- |
| `invoke_skill("git", "git_status", {})` | `git_status()` |
| `skill("git", "git_commit(message='...')")` | `git_commit(message='...')` |
| Descriptive text names | Function name = tool name |

### Git Tools (Example)

```python
git_status()              # Get repository status
git_status_report()       # [VIEW] Formatted report with icons
git_plan_hotfix(issue_id) # [WORKFLOW] Hotfix execution plan
git_commit(message)       # Commit changes
git_branch()              # List branches
```

### Available Skills

| Skill | Purpose | Example Tool |
|-------|---------|--------------|
| `git` | Version control | `git_status()`, `git_commit()` |
| `terminal` | Shell commands | `execute_command()` |
| `filesystem` | File I/O | `read_file()`, `write_file()` |
| `testing_protocol` | Test runner | `smart_test_runner()` |
| `file_ops` | Batch file ops | `apply_file_changes()` |
| `knowledge` | Project context | `get_development_context()` |
| `writer` | Writing quality | `load_writing_memory()` |

---

## Workflow

### Before Any Work

```python
get_development_context()  # Load project rules
```

### When Writing Docs

```python
load_writing_memory()  # Load writing standards
```

### Git Operations

```python
git_status_report()    # View formatted status
git_commit(message="...")  # Commit directly
```

### New Feature

```python
start_spec("Feature Name")
```

---

## Directory Structure

| Path                              | Purpose                                           |
| --------------------------------- | ------------------------------------------------- |
| `agent/skills/{skill}/prompts.md` | Rules & router logic (READ THIS when skill loads) |
| `agent/skills/{skill}/tools.py`   | Atomic execution                                  |
| `agent/skills/{skill}/guide.md`   | Procedural reference                              |
| `docs/`                           | User-facing documentation                         |

---

## Anti-Patterns

- **Don't** use Claude-native bash for `git commit` - use `skill("git", "git_commit(...)")`
- **Don't** write docs without `skill("writer", "load_writing_memory()")`
- **Don't** skip `start_spec` for new features
