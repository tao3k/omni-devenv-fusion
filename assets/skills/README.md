# Skills Directory

> **Phase 63+**: @skill_script Pattern - No tools.py Required

This directory contains **Skills** - composable, self-contained packages that provide specific capabilities to the Omni Agent.

## Quick Reference

| Topic             | Documentation                                 |
| ----------------- | --------------------------------------------- |
| Creating a skill  | [Creating a New Skill](#creating-a-new-skill) |
| Architecture      | [Skill Structure](#skill-structure)           |
| Command reference | See individual skill `SKILL.md` files         |

## Skill Structure

```
assets/skills/{skill_name}/
├── SKILL.md           # Metadata + LLM context (YAML frontmatter)
├── scripts/           # Commands (@skill_script decorated functions)
│   ├── __init__.py    # Dynamic module loader (importlib.util)
│   └── commands.py    # All skill commands
├── references/        # Additional documentation
└── tests/             # Test files
```

## Creating a New Skill

### 1. Copy the Template

```bash
cp -r assets/skills/_template assets/skills/my_new_skill
```

### 2. Add Commands in scripts/commands.py

```python
from agent.skills.decorators import skill_script

@skill_script(
    name="my_command",
    category="read",
    description="Brief description of what this command does",
)
async def my_command(param: str) -> str:
    """Detailed docstring explaining the command behavior."""
    return "result"
```

**Note:** Command name is just `my_command`, not `my_new_skill.my_command`. MCP Server auto-prefixes.

## Command Categories

| Category   | Use Case                                      |
| ---------- | --------------------------------------------- |
| `read`     | Read/retrieve data (files, git status, etc.)  |
| `view`     | Visualize or display data (formatted reports) |
| `write`    | Create or modify data (write files, commit)   |
| `workflow` | Multi-step operations (complex tasks)         |
| `general`  | Miscellaneous commands                        |

## @skill_script Decorator

The `@skill_script` decorator registers functions as MCP tools:

```python
@skill_script(
    name="command_name",       # Tool name (required)
    category="read",           # Category from SkillCategory enum
    description="Brief desc",  # Tool description for LLM
)
async def command_name(param: str) -> str:
    """Function docstring becomes detailed description."""
    return "result"
```

## Hot Reload

Skills are automatically reloaded when `scripts/commands.py` is modified. Mtime checks are throttled to once per 100ms.

## Example Skills

| Skill                                           | Features                          |
| ----------------------------------------------- | --------------------------------- |
| [Git](./git/SKILL.md)                           | Status, commit, branch management |
| [Filesystem](./filesystem/SKILL.md)             | Read, write, search files         |
| [Terminal](./terminal/SKILL.md)                 | Shell command execution           |
| [Testing Protocol](./testing_protocol/SKILL.md) | Test runner integration           |

## Related Documentation

- [Skills Documentation](../../docs/skills.md) - Comprehensive skills guide
- [Trinity Architecture](../../docs/explanation/trinity-architecture.md) - Technical deep dive
