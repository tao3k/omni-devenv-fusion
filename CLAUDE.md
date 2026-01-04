# CLAUDE.md - Omni-DevEnv Fusion

> **Quick Reference Index**. Full docs: `agent/skills/*/prompts.md`

---

## Core Philosophy

**Code is Mechanism, Prompt is Policy**

| Layer          | Purpose        | Files                                     |
| -------------- | -------------- | ----------------------------------------- |
| **Brain**      | Rules, routing | `prompts.md` (LLM reads when skill loads) |
| **Muscle**     | Execution      | `tools.py` (blind, stateless)             |
| **Guardrails** | Validation     | Lefthook, Cog, Pre-commit                 |

---

## Essential Commands

- `just validate` - fmt, lint, test
- `just test-mcp` - MCP tools test

---

## Skills (Load with `load_skill()`)

### Always Load First

| Skill       | Purpose                           | Command                                           |
| ----------- | --------------------------------- | ------------------------------------------------- |
| `knowledge` | Project rules, scopes, guardrails | `skill("knowledge", "get_development_context()")` |
| `writer`    | Writing quality                   | `skill("writer", "load_writing_memory()")`        |

### Execution Skills

| Skill              | Purpose      | Command                                               |
| ------------------ | ------------ | ----------------------------------------------------- |
| `git`              | Commit, Push | `skill("git", "git_commit(message='...')")`           |
| `terminal`         | Commands     | `skill("terminal", "execute_command(command='...')")` |
| `filesystem`       | File I/O     | `skill("filesystem", "read_file(path='...')")`        |
| `testing_protocol` | Tests        | `skill("testing_protocol", "smart_test_runner()")`    |

---

## Workflow

### Before Any Work

```python
skill("knowledge", "get_development_context()")
```

### When Writing Docs

```python
skill("writer", "load_writing_memory()")
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
