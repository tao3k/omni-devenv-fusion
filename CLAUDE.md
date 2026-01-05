# CLAUDE.md - Omni-DevEnv Fusion

> **Phase 25: One Tool Architecture**
>
> Single Entry Point: `@omni("skill.command")`
> Only 1 tool registered with MCP - infinite skills, zero context bloat.
>
> Quick Reference: `agent/skills/*/prompts.md`

---

## ⛔ CRITICAL: Git Commit Prohibition

**Direct `git commit` via Terminal is BLOCKED.**

Use: `@omni("git.commit", {"message": "..."})` or call via omni tool.

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

## Phase 25: One Tool Architecture

### Only ONE Tool Registered: `@omni`

Claude sees only ONE tool. All operations go through this gate.

| Old (Phase 24)                          | New (Phase 25)               |
| --------------------------------------- | ---------------------------- |
| `git_status()` (direct function)        | `@omni("git.status")`        |
| `git_commit(message='...')`             | `@omni("git.commit", {...})` |
| 100+ individual tools                   | 1 tool: `omni`               |
| `invoke_skill("git", "git_status", {})` | `@omni("git.status")`        |

### Usage Syntax

```python
# Execute commands
@omni("git.status")                           # Get git status
@omni("git.commit", {"message": "feat: add"}) # Commit with args
@omni("file.read", {"path": "README.md"})     # Read file

# Get help
@omni("help")         # Show all skills
@omni("git")          # Show git commands
```

### Command Syntax Mapping

| Format          | Example      | Dispatches To            |
| --------------- | ------------ | ------------------------ |
| `skill.command` | `git.status` | `git.git_status()`       |
| `skill.command` | `file.read`  | `filesystem.read_file()` |
| `skill`         | `git`        | Shows git help           |
| `help`          | `help`       | Shows all skills         |

### Available Skills (13 total)

| Skill                  | Purpose         | Example Command                         |
| ---------------------- | --------------- | --------------------------------------- |
| `git`                  | Version control | `@omni("git.status")`                   |
| `terminal`             | Shell commands  | `@omni("terminal.execute", {...})`      |
| `filesystem`           | File I/O        | `@omni("filesystem.read", {...})`       |
| `testing_protocol`     | Test runner     | `@omni("testing_protocol.run", {...})`  |
| `file_ops`             | Batch file ops  | `@omni("file_ops.apply", {...})`        |
| `knowledge`            | Project context | `@omni("knowledge.get_context")`        |
| `writer`               | Writing quality | `@omni("writer.lint", {...})`           |
| `memory`               | Vector memory   | `@omni("memory.recall", {...})`         |
| `documentation`        | Doc management  | `@omni("documentation.search", {...})`  |
| `code_insight`         | Code analysis   | `@omni("code_insight.find", {...})`     |
| `software_engineering` | Architecture    | `@omni("software_engineering.analyze")` |
| `advanced_search`      | Semantic search | `@omni("advanced_search.query", {...})` |

---

## Workflow

### Before Any Work

```python
@omni("knowledge.get_development_context")  # Load project rules
```

### When Writing Docs

```python
@omni("writer.load_writing_memory")  # Load writing standards
```

### Git Operations

```python
@omni("git.status_report")  # View formatted status
@omni("git.commit", {"message": "..."})  # Commit with args
@omni("git.plan_hotfix", {"issue_id": "123"})  # Plan hotfix
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

- **Don't** use Claude-native bash for `git commit` - use `@omni("git.commit", {...})`
- **Don't** write docs without `@omni("writer.load_writing_memory")`
- **Don't** skip `start_spec` for new features
