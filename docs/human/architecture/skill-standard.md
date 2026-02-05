# OSS 1.0: Omni Skill Standard

> **Status**: Active (2026-01-15)
> **Version**: 1.0.0

## Overview

Omni Skill Standard (OSS) 1.0 defines the canonical structure for all skills in Omni-Dev-Fusion Fusion. Skills are "Living Microservice Units" that can be hot-reloaded, indexed, and invoked via `@omni("skill.command")`.

## Directory Structure

```
assets/skills/<skill_name>/
├── 📄 SKILL.md           # [REQUIRED] Core definition + YAML Frontmatter
├── 📘 README.md          # [REQUIRED] User guide and usage examples
├── 🧪 tests/             # [RECOMMENDED] Test files
└── 📁 scripts/           # [REQUIRED] Command implementations
    ├── __init__.py       # Module loader
    └── commands.py       # @skill_command decorated functions
```

### File Responsibilities

| File                  | Role               | Purpose                                                   |
| --------------------- | ------------------ | --------------------------------------------------------- |
| `SKILL.md`            | Identity + Context | Metadata (YAML frontmatter) + LLM rules + Trinity context |
| `README.md`           | User Guide         | Usage docs, examples, command reference                   |
| `scripts/commands.py` | Execution          | @skill_command decorated async functions                  |
| `tests/`              | Quality            | Unit tests                                                |

## SKILL.md Format

Every skill MUST have a `SKILL.md` with YAML frontmatter using the Anthropic official format:

````markdown
---
name: git
description: Use when working with version control, commits, branches, or Git operations.
metadata:
  author: omni-dev-fusion
  version: "2.0.0"
  source: "https://github.com/tao3k/omni-dev-fusion/tree/main/assets/skills/git"
  routing_keywords:
    - "git"
    - "commit"
    - "push"
    - "pull"
    - "merge"
    - "branch"
  intents:
    - "hotfix"
    - "pr"
    - "branch"
    - "commit"
    - "stash"
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

Commands are defined in `scripts/commands.py` with the `@skill_command` decorator:

```python
from agent.skills.decorators import skill_command

@skill_command(
    name="status",
    category="read",
    description="Show working tree status",
)
async def git_status() -> str:
    """Display the working tree status."""
    import subprocess
    result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
    return result.stdout or "Working tree clean"

@skill_command(
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
@skill_command(name="my_command", category="read", description="...")
async def my_command(param: str) -> str:
    ...

# 4. Add tests in tests/test_my_skill.py

# 5. Run indexer
python scripts/generate_llm_index.py
```

## Compliance Checklist

A skill is OSS 1.0 compliant when:

- [ ] `SKILL.md` exists with valid YAML frontmatter
- [ ] `README.md` exists
- [ ] `scripts/` directory exists with commands

Run compliance check:

```bash
python scripts/generate_llm_index.py
# Check for ✅ marks
```

## Related Documentation

- [Skills Architecture](skills-architecture.md) - Complete skills guide (start here)
- [Skill Lifecycle](skill-lifecycle.md) - LangGraph workflow support
- [Trinity Architecture](trinity-core.md)
- [System Context](../../llm/system_context.xml)
