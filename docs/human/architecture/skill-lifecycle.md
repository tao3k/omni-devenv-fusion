# Skill Lifecycle

> **Status**: Active | **Version**: v2.0 | **Date**: 2026-01-28

## Overview

This document describes the lifecycle of a skill in Omni-Dev-Fusion - a self-contained module with atomic commands that follows the **scripts/commands.py** pattern.

## Omni Skill Standard (OSS) 2.0 - Directory Structure

```
assets/skills/<skill_name>/
├── SKILL.md              # [REQUIRED] Metadata + YAML Frontmatter + LLM rules
├── README.md             # [REQUIRED] Usage documentation and examples
├── scripts/              # [REQUIRED] Command implementations
│   ├── __init__.py       # Package marker
│   └── commands.py       # @skill_command decorated functions
└── tests/                # [RECOMMENDED] Test files
```

### File Responsibilities

| File                  | Role          | Purpose                                               |
| --------------------- | ------------- | ----------------------------------------------------- |
| `SKILL.md`            | Identity      | YAML frontmatter for routing, command list, LLM rules |
| `README.md`           | Documentation | Usage examples, command reference                     |
| `scripts/commands.py` | Execution     | @skill_command decorated async functions              |
| `tests/`              | Quality       | Unit and integration tests                            |

## Current Git Skill Structure

```
assets/skills/git/
├── SKILL.md              # Skill metadata + LLM rules
├── README.md             # Usage documentation
├── scripts/              # All Git operations (atomic commands)
│   ├── __init__.py
│   └── commands.py       # @skill_command decorated functions
└── tests/                # Test files
```

## @skill_command Pattern

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
```

## Skill Lifecycle

### 1. Discovery

Skills are discovered from `assets/skills/` directories by the skills-scanner crate.

### 2. Loading

Skills are loaded on-demand via SkillContext or MCP server initialization.

### 3. Hot Reload

Skills support hot reload when `scripts/commands.py` is modified:

- Syntax validation (py_compile)
- Inline unload (sys.modules cleanup)
- Load fresh (from disk)
- Update skill commands

### 4. Unloading

Skills can be unloaded when memory pressure requires it (non-pinned skills only).

## Compliance Checklist

A skill is OSS 2.0 compliant when:

- [ ] `SKILL.md` exists with valid YAML frontmatter
- [ ] `README.md` exists with usage documentation
- [ ] `scripts/` directory exists with commands

## Related Documentation

- [Skills Architecture](skills-architecture.md) - Complete skills architecture guide
- [Skill Standard](skill-standard.md) - OSS 2.0 compliance
- [Trinity Architecture](../explanation/system-layering.md)
