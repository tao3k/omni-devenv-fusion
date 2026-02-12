# OSS 2.0: Omni Skill Standard

> **Status**: Active (2026-02-09)
> **Version**: 2.0.0
> **Current Architecture**: [Omega Architecture](omega-architecture.md)

## Overview

Omni Skill Standard (OSS) 2.0 defines the canonical structure for all skills in Omni-Dev-Fusion. Skills are "Living Microservice Units" that can be hot-reloaded, indexed, and invoked via the single `@omni("skill.command")` entry point.

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

| File                  | Role               | Purpose                                  |
| --------------------- | ------------------ | ---------------------------------------- |
| `SKILL.md`            | Identity + Context | Metadata (YAML frontmatter) + LLM rules  |
| `README.md`           | User Guide         | Usage docs, examples, command reference  |
| `scripts/commands.py` | Execution          | @skill_command decorated async functions |
| `tests/`              | Quality            | Unit tests                               |

## SKILL.md Format

Every skill MUST have a `SKILL.md` with YAML frontmatter using the Anthropic official format:

```markdown
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
  intents:
    - "commit"
    - "status"
---

# Git Skill Guidelines

- Use `git.status` for read-only operations
- Use `git.commit` with explicit confirmation
- Never commit sensitive files
```

## System Layering Context

This skill follows the **System Layering Architecture**:

| Component | Layer          | Description                                           |
| :-------- | :------------- | :---------------------------------------------------- |
| Code      | L2: Core       | `scripts/commands.py` - Hot-reloaded via ScriptLoader |
| Context   | L4: Agent      | `@omni("skill.help")` - Full context for the LLM      |
| State     | L1: Foundation | `SKILL.md` - Frontmatter parsed into Pydantic models  |

## Related Documentation

- [Skills Architecture](skills-architecture.md)
- [Omega Architecture](omega-architecture.md)
- [System Layering Architecture](../../explanation/system-layering.md)
- [System Context](../../llm/system_context.xml)
