# OSS 1.0: Omni Skill Standard

> **Status**: Active (2026-01-15)
> **Version**: 1.0.0

## Overview

Omni Skill Standard (OSS) 1.0 defines the canonical structure for all skills in Omni-DevEnv Fusion. Skills are "Living Microservice Units" that can be hot-reloaded, indexed, and invoked via `@omni("skill.command")`.

## Directory Structure

```
assets/skills/<skill_name>/
├── 📄 SKILL.md           # [REQUIRED] Core definition + YAML Frontmatter
├── 📘 README.md          # [REQUIRED] User guide and usage examples
├── 🧪 tests/             # [RECOMMENDED] Test files
└── 📁 scripts/           # [REQUIRED] Command implementations
    ├── __init__.py       # Module loader
    └── commands.py       # @skill_script decorated functions
```

### File Responsibilities

| File                  | Role               | Purpose                                                   |
| --------------------- | ------------------ | --------------------------------------------------------- |
| `SKILL.md`            | Identity + Context | Metadata (YAML frontmatter) + LLM rules + Trinity context |
| `README.md`           | User Guide         | Usage docs, examples, command reference                   |
| `scripts/commands.py` | Execution          | @skill_script decorated async functions                   |
| `tests/`              | Quality            | Unit tests                                                |

### Legacy Files (Move to references/ if needed)

| File            | Status | Action                                  |
| --------------- | ------ | --------------------------------------- |
| `manifest.json` | Legacy | Remove, use `SKILL.md` YAML frontmatter |
| `tools.py`      | Legacy | Consolidate into `scripts/commands.py`  |
| `workflow.py`   | Legacy | Consolidate into `scripts/commands.py`  |
| `prompts.md`    | Legacy | Move to `references/` if content needed |
| `state.py`      | Legacy | Inline in `scripts/commands.py`         |

## SKILL.md Format

Every skill MUST have a `SKILL.md` with YAML frontmatter:

````markdown
---
name: "git"
version: "2.0.0"
description: "Git integration with Smart Commit V2 and Spec-Awareness"
routing_keywords: ["git", "commit", "push", "pull", "merge", "branch"]
intents: ["hotfix", "pr", "branch", "commit", "stash"]
authors: ["omni-dev-fusion"]
---

# Skill Name

## System Prompt Additions

When this skill is active, add these guidelines to the LLM context:

```markdown
# Git Skill Guidelines

- Use `git.status` for read-only operations
- Use `git.commit` with explicit confirmation
- Never commit sensitive files
```
````

## Trinity Architecture Context

This skill follows the **scripts/commands.py** pattern:

| Component | Description                                           |
| --------- | ----------------------------------------------------- |
| Code      | `scripts/commands.py` - Hot-reloaded via ModuleLoader |
| Context   | `@omni("skill.help")` - Full context via Repomix      |
| State     | `SKILL.md` - YAML frontmatter                         |

## Router Logic

| Operation | Command        | When                       |
| --------- | -------------- | -------------------------- |
| Commit    | `git_commit()` | User says "commit", "save" |
| Status    | `git_status()` | Read-only, always safe     |

## Anti-Patterns

| Wrong                     | Correct                            |
| ------------------------- | ---------------------------------- |
| Use MCP for `git status`  | Use Claude-native bash             |
| Use bash for `git add -A` | Use `git_stage_all()` for security |

````

## Scripts/Commands.py Pattern

Commands are defined in `scripts/commands.py` with the `@skill_script` decorator:

```python
from agent.skills.decorators import skill_script

@skill_script(
    name="status",
    category="read",
    description="Show working tree status",
)
async def git_status() -> str:
    """Display the working tree status."""
    import subprocess
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    return result.stdout or "Working tree clean"

@skill_script(
    name="commit",
    category="write",
    description="Commit staged changes",
)
async def git_commit(message: str) -> str:
    """Commit staged changes with the given message."""
    import subprocess
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr
````

### Decorator Parameters

| Parameter     | Type | Description                                |
| ------------- | ---- | ------------------------------------------ |
| `name`        | str  | Command name (auto-prefixed by skill name) |
| `category`    | str  | "read", "write", "view", "admin"           |
| `description` | str  | Brief description for LLM context          |

## Routing Keywords

Skills declare routing keywords in `SKILL.md` frontmatter for HiveRouter matching:

```yaml
routing_keywords:
  # Core verbs
  - "git"
  - "commit"
  - "push"
  # Phrases
  - "check in"
  - "save changes"
  # Context
  - "branch"
  - "version control"
```

## Skill Index

Skills are automatically indexed by `scripts/generate_llm_index.py`:

```bash
python scripts/generate_llm_index.py
```

This generates `docs/llm/skill_index.json` which provides:

- Skill names and descriptions
- Available commands
- Routing keywords
- OSS compliance status

## Creating a New Skill

```bash
# 1. Copy template
cp -r assets/skills/_template assets/skills/my_skill

# 2. Update SKILL.md frontmatter
# Edit name, version, description, routing_keywords

# 3. Add commands in scripts/commands.py
@skill_script(name="my_command", category="read", description="...")
async def my_command(param: str) -> str:
    ...

# 4. Add tests in tests/test_my_skill.py

# 5. Run indexer
python scripts/generate_llm_index.py
```

## Compliance Checklist

A skill is OSS 1.0 compliant when:

- [ ] `SKILL.md` exists with valid YAML frontmatter
- [ ] `README.md` or `guide.md` exists
- [ ] `scripts/` directory exists with commands
- [ ] No deprecated files (`manifest.json`, `tools.py`, `prompts.md`)

Run compliance check:

```bash
python scripts/generate_llm_index.py
# Check for ✅ marks
```

## Migration from Legacy Skills

For skills using old structure (`manifest.json`, `tools.py`, `prompts.md`):

1. **Extract metadata** from `manifest.json` to `SKILL.md` frontmatter
2. **Move rules** from `prompts.md` to `SKILL.md` under "System Prompt Additions"
3. **Consolidate functions** from `tools.py` into `scripts/commands.py`
4. **Move** `prompts.md` to `references/` if content needed
5. **Remove** `manifest.json`, `tools.py`, `workflow.py`, `state.py`
6. **Run** `python scripts/generate_llm_index.py` to verify

## Related Documentation

- [Skills Architecture](skills-architecture.md) - Complete skills guide (start here)
- [Skill Lifecycle](skill-lifecycle.md) - LangGraph workflow support
- [Trinity Architecture](trinity-core.md)
- [System Context](../../llm/system_context.xml)
